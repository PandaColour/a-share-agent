#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
全局数据管理器
统一管理股票数据，避免重复获取
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .multi_source_data_provider import MultiSourceDataProvider

logger = logging.getLogger(__name__)

# 导入新闻相关模块
try:
    from ..utils.real_news_fetcher import RealNewsFetcher
    from ..utils.news_filter import IntelligentNewsFilter
    NEWS_AVAILABLE = True
except ImportError:
    logger.warning("新闻模块不可用")
    NEWS_AVAILABLE = False


class DataManager:
    """全局数据管理器 - 单例模式"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.data_provider = MultiSourceDataProvider()

        # 初始化新闻获取器
        if NEWS_AVAILABLE:
            self.news_fetcher = RealNewsFetcher()
            self.news_filter = IntelligentNewsFilter()
        else:
            self.news_fetcher = None
            self.news_filter = None

        # 数据缓存
        self.stock_data_cache = {}  # {symbol: DataFrame}
        self.news_data_cache = {}  # {symbol: List[NewsItem]}
        self.cache_timestamps = {}  # {symbol: timestamp}
        self.cache_duration = 1800  # 30分钟缓存

        # 预加载状态
        self.news_loaded = False
        self.current_period = None

        # 数据完整性要求
        self.require_stock_data = True
        self.require_news_data = False  # 新闻数据可选

        logger.info("全局数据管理器初始化完成")
        self._initialized = True

    def get_comprehensive_data(self, symbols: List[str], period: str = "1y") -> Tuple[Dict[str, pd.DataFrame], Dict[str, list]]:
        """
        一次性获取股票数据和新闻数据

        Args:
            symbols: 股票代码列表
            period: 数据周期

        Returns:
            (股票数据字典, 新闻数据字典)
        """
        logger.info(f"获取综合数据：{len(symbols)} 只股票")

        # 1. 并发获取股票数据
        stock_data = self._fetch_stock_data_batch(symbols, period)

        # 2. 获取新闻数据（如果需要）
        news_data = {}
        if self.news_fetcher:
            try:
                news_data = self._fetch_news_data_batch(symbols)
                logger.info(f"✅ 新闻数据获取完成：{len(news_data)} 只股票")
            except Exception as e:
                logger.warning(f"⚠️ 新闻数据获取失败: {e}")

        # 3. 严格数据验证和失败中断
        if self.require_stock_data and not self._validate_stock_data(stock_data, symbols):
            raise RuntimeError("❌ 股票数据获取失败，中断程序执行")

        logger.info(f"✅ 综合数据获取完成：股票 {len(stock_data)}/{len(symbols)}")

        return stock_data, news_data

    def _fetch_stock_data_batch(self, symbols: List[str], period: str, max_workers: int = 8) -> Dict[str, pd.DataFrame]:
        """
        批量获取股票数据（带缓存）

        Args:
            symbols: 股票代码列表
            period: 数据周期
            max_workers: 最大并发数

        Returns:
            股票数据字典
        """
        stock_data = {}
        symbols_to_fetch = []

        # 检查缓存
        current_time = time.time()
        for symbol in symbols:
            cache_key = f"{symbol}_{period}"
            if (cache_key in self.stock_data_cache and
                cache_key in self.cache_timestamps and
                current_time - self.cache_timestamps[cache_key] < self.cache_duration):

                stock_data[symbol] = self.stock_data_cache[cache_key]
                logger.debug(f"✅ 从缓存获取 {symbol} 数据")
            else:
                symbols_to_fetch.append(symbol)

        if not symbols_to_fetch:
            logger.info("所有股票数据都已缓存")
            return stock_data

        logger.info(f"需要获取 {len(symbols_to_fetch)} 只股票的新数据")

        # 并发获取新数据
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {
                executor.submit(self._fetch_single_stock, symbol, period): symbol
                for symbol in symbols_to_fetch
            }

            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    data = future.result(timeout=30)
                    if data is not None and not data.empty:
                        stock_data[symbol] = data
                        # 更新缓存
                        cache_key = f"{symbol}_{period}"
                        self.stock_data_cache[cache_key] = data
                        self.cache_timestamps[cache_key] = current_time
                        logger.debug(f"✅ 成功获取并缓存 {symbol} 数据")
                    else:
                        logger.warning(f"❌ {symbol} 数据为空")
                except Exception as e:
                    logger.error(f"❌ 获取 {symbol} 数据失败: {e}")

        return stock_data

    def _fetch_news_data_batch(self, symbols: List[str], max_workers: int = 4) -> Dict[str, list]:
        """
        批量获取新闻数据（带缓存）

        Args:
            symbols: 股票代码列表
            max_workers: 最大并发数

        Returns:
            新闻数据字典
        """
        if not self.news_fetcher or not self.news_filter:
            logger.warning("新闻模块不可用")
            return {}

        news_data = {}
        symbols_to_fetch = []

        # 检查缓存
        current_time = time.time()
        for symbol in symbols:
            if (symbol in self.news_data_cache and
                symbol in self.cache_timestamps and
                current_time - self.cache_timestamps[symbol] < self.cache_duration):

                news_data[symbol] = self.news_data_cache[symbol]
                logger.debug(f"✅ 从缓存获取 {symbol} 新闻数据")
            else:
                symbols_to_fetch.append(symbol)

        if not symbols_to_fetch:
            logger.info("所有新闻数据都已缓存")
            return news_data

        logger.info(f"需要获取 {len(symbols_to_fetch)} 只股票的新闻数据")

        # 并发获取新数据
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {
                executor.submit(self._fetch_single_news, symbol): symbol
                for symbol in symbols_to_fetch
            }

            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    news_list = future.result(timeout=30)
                    if news_list:
                        news_data[symbol] = news_list
                        # 更新缓存
                        self.news_data_cache[symbol] = news_list
                        self.cache_timestamps[symbol] = current_time
                        logger.debug(f"✅ 成功获取并缓存 {symbol} 新闻数据: {len(news_list)} 条")
                    else:
                        logger.warning(f"❌ {symbol} 新闻数据为空")
                except Exception as e:
                    logger.error(f"❌ 获取 {symbol} 新闻数据失败: {e}")

        return news_data

    def _fetch_single_news(self, symbol: str) -> list:
        """获取单只股票新闻数据"""
        try:
            # 检查新闻模块是否可用
            if not self.news_fetcher or not self.news_filter:
                logger.warning(f"新闻模块不可用，跳过 {symbol} 的新闻获取")
                return []

            # 获取原始新闻
            # RealNewsFetcher需要公司名称，这里用股票代码作为公司名称的简化处理
            company_name = symbol.replace('.SZ', '').replace('.SH', '')
            raw_news = self.news_fetcher.fetch_stock_news(symbol, company_name)
            if not raw_news:
                return []

            # 过滤新闻
            filtered_news = self.news_filter.filter_news(raw_news)
            return filtered_news
        except Exception as e:
            logger.error(f"获取 {symbol} 新闻数据失败: {e}")
            return []

    def _fetch_single_stock(self, symbol: str, period: str) -> Optional[pd.DataFrame]:
        """获取单只股票数据"""
        try:
            return self.data_provider.get_stock_data(symbol, period=period)
        except Exception as e:
            logger.error(f"获取 {symbol} 数据失败: {e}")
            return None

    def get_stock_data(self, symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """
        获取单只股票数据

        Args:
            symbol: 股票代码
            period: 数据周期

        Returns:
            股票数据DataFrame
        """
        stock_data, _ = self.get_comprehensive_data([symbol], period)
        return stock_data.get(symbol)

    def _validate_stock_data(self, stock_data: Dict[str, pd.DataFrame], symbols: List[str]) -> bool:
        """
        验证股票数据完整性

        Args:
            stock_data: 股票数据字典
            symbols: 期望的股票代码列表

        Returns:
            是否通过验证
        """
        if not stock_data:
            logger.error("❌ 没有获取到任何股票数据")
            return False

        # 检查数据覆盖率
        success_count = len(stock_data)
        required_count = len(symbols)
        coverage_rate = success_count / required_count if required_count > 0 else 0

        logger.info(f"📊 股票数据覆盖率: {success_count}/{required_count} ({coverage_rate:.1%})")

        # 严格模式：要求至少80%的数据获取成功
        min_coverage = 0.8
        if coverage_rate < min_coverage:
            logger.error(f"❌ 股票数据覆盖率 {coverage_rate:.1%} 低于最低要求 {min_coverage:.1%}")
            return False

        # 检查数据质量
        invalid_data_count = 0
        for symbol, data in stock_data.items():
            if data is None or data.empty:
                logger.error(f"❌ {symbol} 数据为空")
                invalid_data_count += 1
                continue

            # 检查必要列
            required_columns = ['Close', 'Open', 'High', 'Low', 'Volume']
            missing_columns = [col for col in required_columns if col not in data.columns]
            if missing_columns:
                logger.error(f"❌ {symbol} 缺少必要列: {missing_columns}")
                invalid_data_count += 1
                continue

            # 检查数据量
            if len(data) < 10:
                logger.warning(f"⚠️ {symbol} 数据量不足: {len(data)} 条")

        if invalid_data_count > 0:
            logger.error(f"❌ 发现 {invalid_data_count} 个无效股票数据")
            return False

        logger.info("✅ 股票数据验证通过")
        return True

    def set_data_requirements(self, require_stock_data: bool = True,
                            require_news_data: bool = False):
        """
        设置数据完整性要求

        Args:
            require_stock_data: 是否要求股票数据必须获取成功
            require_news_data: 是否要求新闻数据必须获取成功
        """
        self.require_stock_data = require_stock_data
        self.require_news_data = require_news_data

        logger.info(f"数据要求设置: 股票={require_stock_data}, 新闻={require_news_data}")

    def clear_cache(self):
        """清空所有缓存"""
        self.stock_data_cache.clear()
        self.news_data_cache.clear()
        self.cache_timestamps.clear()
        self.current_period = None
        logger.info("数据缓存已清空")

    def get_cache_status(self) -> Dict:
        """获取缓存状态"""
        current_time = time.time()
        valid_cache_count = sum(
            1 for timestamp in self.cache_timestamps.values()
            if current_time - timestamp < self.cache_duration
        )

        return {
            "stock_cache_count": len(self.stock_data_cache),
            "news_cache_count": len(self.news_data_cache),
            "valid_cache_count": valid_cache_count,
            "current_period": self.current_period,
            "cache_duration": self.cache_duration
        }


# 全局实例
_data_manager = None

def get_data_manager() -> DataManager:
    """获取全局数据管理器实例"""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager


def get_comprehensive_stock_data(symbols: List[str], period: str = "1y") -> Tuple[Dict[str, pd.DataFrame], Dict[str, list]]:
    """
    获取综合股票和新闻数据的便捷函数

    Args:
        symbols: 股票代码列表
        period: 数据周期

    Returns:
        (股票数据字典, 新闻数据字典)
    """
    manager = get_data_manager()
    return manager.get_comprehensive_data(symbols, period)