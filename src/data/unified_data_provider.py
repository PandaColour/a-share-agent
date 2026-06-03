# -*- coding: utf-8 -*-
"""
统一数据提供者实现
整合数据源管理器、指标计算器，提供高层数据访问接口
"""

import logging
from typing import Dict, Tuple, Optional, List
import pandas as pd

from .interfaces import (
    IDataProvider, DataRequest, DataSourceType, TimeFrame, StockInfo,
    DataSourceUnavailableException, DataNotFoundException
)
from .source_manager import DataSourceManager
from .source_factory import DataSourceFactory
from .indicators.technical_indicators import TechnicalIndicatorCalculator

logger = logging.getLogger(__name__)


class UnifiedDataProvider(IDataProvider):
    """统一数据提供者"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.source_manager = DataSourceManager()
        self.indicator_calculator = TechnicalIndicatorCalculator()
        self._initialize_sources()

    def _initialize_sources(self):
        """初始化数据源"""
        try:
            # 从配置加载数据源
            data_sources_config = self.config.get('system_settings', {}).get('data_sources', {})

            if not data_sources_config:
                # 使用默认配置
                data_sources_config = {
                    'akshare': {'enabled': True},
                    'yfinance': {'enabled': True}
                }

            # 创建并注册数据源
            sources = DataSourceFactory.create_from_config(data_sources_config)

            for source_type, source in sources.items():
                self.source_manager.register_source(source)

            # 设置主数据源
            primary_source = data_sources_config.get('primary_source', 'akshare')
            try:
                source_type = DataSourceType(primary_source.lower())
                self.source_manager.set_primary_source(source_type)
            except (ValueError, DataSourceUnavailableException):
                logger.warning(f"无法设置主数据源 {primary_source}，使用默认顺序")

            # 设置故障转移顺序
            fallback_sources = data_sources_config.get('fallback_sources', ['yfinance'])
            try:
                fallback_order = [DataSourceType(name.lower()) for name in fallback_sources
                                if name.lower() in [ds.value for ds in DataSourceType]]
                if fallback_order:
                    self.source_manager.set_fallback_order(fallback_order)
            except ValueError:
                logger.warning("故障转移配置无效，使用默认顺序")

            logger.info(f"统一数据提供者初始化完成，可用数据源: {len(sources)}")

        except Exception as e:
            logger.error(f"初始化数据源失败: {e}")

    def get_stock_data(
        self,
        symbol: str,
        timeframe: TimeFrame = TimeFrame.DAILY,
        start_date: str = None,
        end_date: str = None,
        period: str = "1y"
    ) -> pd.DataFrame:
        """获取股票数据"""
        request = DataRequest(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            period=period
        )

        try:
            data, source_type = self.source_manager.get_data_with_fallback(request)
            logger.debug(f"从 {source_type.value} 获取数据成功: {symbol}")
            return data
        except DataNotFoundException as e:
            logger.error(f"获取股票数据失败 {symbol}: {e}")
            return pd.DataFrame()

    def get_complete_stock_data(
        self,
        symbol: str,
        timeframe: TimeFrame = TimeFrame.DAILY,
        start_date: str = None,
        end_date: str = None,
        period: str = "1y"
    ) -> Tuple[pd.DataFrame, StockInfo, Dict, Dict]:
        """获取完整股票数据"""
        try:
            # 获取股票数据
            data = self.get_stock_data(symbol, timeframe, start_date, end_date, period)

            if data.empty:
                return pd.DataFrame(), StockInfo(symbol=symbol), {}, {}

            # 获取股票信息
            stock_info = self.get_stock_info(symbol)

            # 计算技术指标
            indicators = self.indicator_calculator.calculate_indicators(data, stock_info)

            # 计算价格信息
            price_info = self._calculate_price_info(data)

            return data, stock_info, indicators, price_info

        except Exception as e:
            logger.error(f"获取完整股票数据失败 {symbol}: {e}")
            return pd.DataFrame(), StockInfo(symbol=symbol), {}, {}

    def get_stock_info(self, symbol: str) -> StockInfo:
        """获取股票基本信息"""
        available_sources = self.source_manager.get_available_sources()

        for source_info in available_sources:
            try:
                source = self.source_manager.get_source(source_info.source_type)
                if source:
                    stock_info = source.get_stock_info(symbol)
                    if stock_info.name:  # 如果获取到有效信息
                        return stock_info
            except Exception as e:
                logger.debug(f"从 {source_info.source_type.value} 获取股票信息失败: {e}")
                continue

        return StockInfo(symbol=symbol)

    def _calculate_price_info(self, data: pd.DataFrame) -> Dict:
        """计算价格信息"""
        if data.empty:
            return {
                "current_price": 0.0,
                "daily_high": 0.0,
                "daily_low": 0.0,
                "daily_change": 0.0,
                "daily_change_percent": 0.0
            }

        try:
            latest_data = data.iloc[-1]
            current_price = float(latest_data['Close'])
            daily_high = float(latest_data['High'])
            daily_low = float(latest_data['Low'])

            # 计算日涨跌
            if len(data) >= 2:
                prev_close = float(data.iloc[-2]['Close'])
                daily_change = current_price - prev_close
                daily_change_percent = (daily_change / prev_close) * 100 if prev_close != 0 else 0.0
            else:
                daily_change = 0.0
                daily_change_percent = 0.0

            return {
                "current_price": round(current_price, 2),
                "daily_high": round(daily_high, 2),
                "daily_low": round(daily_low, 2),
                "daily_change": round(daily_change, 2),
                "daily_change_percent": round(daily_change_percent, 2)
            }

        except Exception as e:
            logger.error(f"计算价格信息失败: {e}")
            return {
                "current_price": 0.0,
                "daily_high": 0.0,
                "daily_low": 0.0,
                "daily_change": 0.0,
                "daily_change_percent": 0.0
            }

    def get_minute_data(self, symbol: str, timeframe: TimeFrame = TimeFrame.MINUTE_5) -> pd.DataFrame:
        """获取分钟级数据"""
        if timeframe not in [TimeFrame.MINUTE_1, TimeFrame.MINUTE_5,
                           TimeFrame.MINUTE_15, TimeFrame.MINUTE_30, TimeFrame.HOUR_1]:
            raise ValueError(f"不支持的分钟时间框架: {timeframe}")

        return self.get_stock_data(symbol, timeframe)

    def get_available_sources(self) -> List[str]:
        """获取可用数据源列表"""
        available_sources = self.source_manager.get_available_sources()
        return [source.source_type.value for source in available_sources]

    def set_primary_source(self, source_name: str) -> bool:
        """设置主数据源"""
        try:
            source_type = DataSourceType(source_name.lower())
            self.source_manager.set_primary_source(source_type)
            return True
        except (ValueError, DataSourceUnavailableException) as e:
            logger.error(f"设置主数据源失败: {e}")
            return False

    def get_stats(self) -> Dict:
        """获取数据提供者统计信息"""
        stats = self.source_manager.get_stats()
        stats.update({
            "supported_indicators": self.indicator_calculator.get_supported_indicators(),
            "supported_timeframes": [tf.value for tf in TimeFrame]
        })
        return stats

    def health_check(self) -> Dict:
        """健康检查"""
        available_sources = self.source_manager.get_available_sources()

        health_status = {
            "status": "healthy" if available_sources else "unhealthy",
            "available_sources": len(available_sources),
            "total_sources": len(self.source_manager._sources),
            "primary_source": self.source_manager._primary_source.value if self.source_manager._primary_source else None,
            "sources_status": {}
        }

        for source_type, source in self.source_manager._sources.items():
            health_status["sources_status"][source_type.value] = {
                "available": source.is_available(),
                "name": source.get_info().name
            }

        return health_status


# 兼容性别名
DataProvider = UnifiedDataProvider