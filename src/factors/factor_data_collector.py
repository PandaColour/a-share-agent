# -*- coding: utf-8 -*-
"""
因子数据收集模块
用于收集因子值历史和收益率历史，为IC评估提供数据
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
import json
import os
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


class FactorDataCollector:
    """因子数据收集器"""

    def __init__(self, cache_dir: str = "factor_cache/factor_history"):
        """
        初始化数据收集器

        Args:
            cache_dir: 数据缓存目录
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        # 因子值历史 {factor_name: {date: {symbol: value}}}
        self.factor_value_history = {}

        # 收益率历史 {date: {symbol: return}}
        self.returns_history = {}

        # 股票池历史 {date: [symbols]}
        self.stock_pool_history = {}

        logger.info(f"因子数据收集器初始化完成，缓存目录: {cache_dir}")

    def record_factor_values(self,
                            date: str,
                            symbol: str,
                            factor_values: Dict[str, float]):
        """
        记录单日单只股票的因子值

        Args:
            date: 日期 (YYYY-MM-DD)
            symbol: 股票代码
            factor_values: 因子值字典 {factor_name: value}
        """
        for factor_name, value in factor_values.items():
            if factor_name not in self.factor_value_history:
                self.factor_value_history[factor_name] = {}

            if date not in self.factor_value_history[factor_name]:
                self.factor_value_history[factor_name][date] = {}

            self.factor_value_history[factor_name][date][symbol] = value

    def record_returns(self,
                      date: str,
                      symbol: str,
                      return_value: float):
        """
        记录单日单只股票的收益率

        Args:
            date: 日期（这是前一日，收益率是次日的）
            symbol: 股票代码
            return_value: 收益率
        """
        if date not in self.returns_history:
            self.returns_history[date] = {}

        self.returns_history[date][symbol] = return_value

    def batch_record_daily_data(self,
                               date: str,
                               stocks_data: List[Dict]):
        """
        批量记录单日所有股票的数据

        Args:
            date: 日期
            stocks_data: 股票数据列表
                [{
                    'symbol': '000001.SZ',
                    'factors': {'factor1': 0.5, 'factor2': 0.3},
                    'next_day_return': 0.012
                }, ...]
        """
        symbols = []

        for stock_data in stocks_data:
            symbol = stock_data['symbol']
            symbols.append(symbol)

            # 记录因子值
            if 'factors' in stock_data:
                self.record_factor_values(date, symbol, stock_data['factors'])

            # 记录收益率
            if 'next_day_return' in stock_data:
                self.record_returns(date, symbol, stock_data['next_day_return'])

        # 记录股票池
        self.stock_pool_history[date] = symbols

        logger.debug(f"记录 {date} 的数据: {len(symbols)} 只股票")

    def calculate_returns_from_prices(self,
                                     price_data: Dict[str, pd.DataFrame],
                                     start_date: str = None,
                                     end_date: str = None):
        """
        从价格数据计算收益率

        Args:
            price_data: 价格数据字典 {symbol: DataFrame with 'Close'}
            start_date: 开始日期
            end_date: 结束日期
        """
        logger.info(f"开始从价格数据计算收益率...")

        for symbol, df in price_data.items():
            if df.empty or 'Close' not in df.columns:
                continue

            # 计算收益率
            returns = df['Close'].pct_change()

            # 遍历日期
            for i in range(len(df) - 1):
                date = df.index[i].strftime('%Y-%m-%d')
                next_return = returns.iloc[i + 1]

                # 跳过NaN
                if pd.isna(next_return):
                    continue

                # 日期过滤
                if start_date and date < start_date:
                    continue
                if end_date and date > end_date:
                    break

                self.record_returns(date, symbol, float(next_return))

        logger.info(f"收益率计算完成，共 {len(self.returns_history)} 个交易日")

    def load_from_backtest_results(self,
                                   backtest_dir: str = "backtest_results") -> int:
        """
        从回测结果中加载历史数据

        Args:
            backtest_dir: 回测结果目录

        Returns:
            加载的回测次数
        """
        logger.info(f"从回测结果加载历史数据: {backtest_dir}")

        backtest_path = Path(backtest_dir)
        if not backtest_path.exists():
            logger.warning(f"回测目录不存在: {backtest_dir}")
            return 0

        # 查找所有回测子目录
        subdirs = [d for d in backtest_path.iterdir() if d.is_dir()]
        loaded_count = 0

        for subdir in subdirs:
            try:
                # 查找回测结果文件
                result_file = subdir / "backtest_results.json"
                if not result_file.exists():
                    continue

                with open(result_file, 'r', encoding='utf-8') as f:
                    results = json.load(f)

                # 提取交易记录
                trade_history = results.get('trade_history', [])

                # 提取历史数据（如果有）
                if 'historical_data' in results:
                    # historical_data可能包含因子值历史
                    pass

                loaded_count += 1

            except Exception as e:
                logger.error(f"加载回测结果失败 {subdir}: {e}")

        logger.info(f"从回测结果加载完成: {loaded_count} 个回测")
        return loaded_count

    def simulate_data_collection(self,
                                 symbols: List[str],
                                 days: int = 60,
                                 factor_manager=None) -> int:
        """
        模拟运行历史回测来收集数据

        Args:
            symbols: 股票列表
            days: 回测天数
            factor_manager: 因子管理器实例

        Returns:
            收集的交易日数量
        """
        logger.info(f"开始模拟数据收集: {len(symbols)}只股票, {days}天")

        if factor_manager is None:
            logger.error("需要提供factor_manager")
            return 0

        from src.data.multi_source_data_provider import MultiSourceDataProvider

        data_provider = MultiSourceDataProvider()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 30)  # 多取一些数据

        collected_days = 0

        # 获取所有股票的历史数据
        logger.info("获取历史价格数据...")
        price_data = {}
        for symbol in symbols:
            try:
                df = data_provider.get_stock_data(
                    symbol,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )
                if not df.empty and len(df) > 20:
                    price_data[symbol] = df
            except Exception as e:
                logger.warning(f"获取{symbol}数据失败: {e}")

        if not price_data:
            logger.error("没有获取到任何价格数据")
            return 0

        logger.info(f"成功获取 {len(price_data)} 只股票的数据")

        # 计算收益率
        self.calculate_returns_from_prices(price_data)

        # 逐日计算因子值
        logger.info("计算历史因子值...")

        # 获取所有交易日
        all_dates = sorted(set(
            date for df in price_data.values()
            for date in df.index.strftime('%Y-%m-%d')
        ))

        for date_str in all_dates[-days:]:  # 只取最近days天
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')

            stocks_data = []

            for symbol in symbols:
                if symbol not in price_data:
                    continue

                df = price_data[symbol]

                # 获取到该日期为止的数据
                df_to_date = df[df.index <= date_obj]

                if len(df_to_date) < 20:
                    continue

                try:
                    # 计算因子值
                    data_dict = {
                        'price': df_to_date,
                        'volume': df_to_date[['Volume']]
                    }

                    factor_values_obj = factor_manager.calculate_all_factors(symbol, data_dict)

                    # 转换为字典
                    factor_values = {
                        name: fv.value
                        for name, fv in factor_values_obj.items()
                    }

                    # 获取次日收益率（如果有）
                    next_return = None
                    if date_str in self.returns_history:
                        next_return = self.returns_history[date_str].get(symbol)

                    stocks_data.append({
                        'symbol': symbol,
                        'factors': factor_values,
                        'next_day_return': next_return
                    })

                except Exception as e:
                    logger.debug(f"计算{symbol}在{date_str}的因子失败: {e}")

            if stocks_data:
                self.batch_record_daily_data(date_str, stocks_data)
                collected_days += 1

            if collected_days % 10 == 0:
                logger.info(f"  已收集 {collected_days}/{days} 天")

        logger.info(f"数据收集完成: {collected_days} 个交易日")
        return collected_days

    def get_factor_values_by_date(self,
                                  factor_name: str,
                                  date: str) -> Dict[str, float]:
        """
        获取某日所有股票的因子值

        Args:
            factor_name: 因子名称
            date: 日期

        Returns:
            {symbol: value}
        """
        if factor_name not in self.factor_value_history:
            return {}

        return self.factor_value_history[factor_name].get(date, {})

    def get_returns_by_date(self, date: str) -> Dict[str, float]:
        """
        获取某日所有股票的次日收益率

        Args:
            date: 日期

        Returns:
            {symbol: return}
        """
        return self.returns_history.get(date, {})

    def get_available_dates(self) -> List[str]:
        """
        获取所有可用的日期

        Returns:
            日期列表（排序）
        """
        return sorted(self.returns_history.keys())

    def save_to_disk(self):
        """保存数据到磁盘"""
        logger.info("保存因子数据到磁盘...")

        try:
            # 保存因子值历史
            factor_file = os.path.join(self.cache_dir, "factor_values.pkl")
            with open(factor_file, 'wb') as f:
                pickle.dump(self.factor_value_history, f)

            # 保存收益率历史
            returns_file = os.path.join(self.cache_dir, "returns.pkl")
            with open(returns_file, 'wb') as f:
                pickle.dump(self.returns_history, f)

            # 保存统计信息（JSON格式，方便查看）
            stats = {
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'num_factors': len(self.factor_value_history),
                'num_dates': len(self.returns_history),
                'num_stocks': len(self.stock_pool_history),
                'date_range': {
                    'start': min(self.returns_history.keys()) if self.returns_history else None,
                    'end': max(self.returns_history.keys()) if self.returns_history else None
                }
            }

            stats_file = os.path.join(self.cache_dir, "stats.json")
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)

            logger.info(f"✓ 数据保存成功: {stats['num_dates']}天, {stats['num_factors']}个因子")

        except Exception as e:
            logger.error(f"保存数据失败: {e}")

    def load_from_disk(self) -> bool:
        """从磁盘加载数据"""
        logger.info("从磁盘加载因子数据...")

        try:
            # 加载因子值历史
            factor_file = os.path.join(self.cache_dir, "factor_values.pkl")
            if os.path.exists(factor_file):
                with open(factor_file, 'rb') as f:
                    self.factor_value_history = pickle.load(f)

            # 加载收益率历史
            returns_file = os.path.join(self.cache_dir, "returns.pkl")
            if os.path.exists(returns_file):
                with open(returns_file, 'rb') as f:
                    self.returns_history = pickle.load(f)

            if self.factor_value_history or self.returns_history:
                logger.info(f"✓ 数据加载成功: {len(self.returns_history)}天, "
                          f"{len(self.factor_value_history)}个因子")
                return True
            else:
                logger.warning("没有找到缓存数据")
                return False

        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return False

    def get_summary(self) -> Dict:
        """
        获取数据摘要

        Returns:
            数据摘要字典
        """
        summary = {
            'num_factors': len(self.factor_value_history),
            'num_dates': len(self.returns_history),
            'factors': list(self.factor_value_history.keys()),
            'date_range': {
                'start': min(self.returns_history.keys()) if self.returns_history else None,
                'end': max(self.returns_history.keys()) if self.returns_history else None
            }
        }

        # 计算每个因子的样本数
        factor_samples = {}
        for factor_name, dates_data in self.factor_value_history.items():
            total_samples = sum(len(symbols) for symbols in dates_data.values())
            factor_samples[factor_name] = {
                'dates': len(dates_data),
                'total_samples': total_samples
            }

        summary['factor_samples'] = factor_samples

        return summary

    def batch_import_from_backtest(self, backtest_factor_records: List[Dict]) -> int:
        """
        从回测过程中批量导入因子值和收益率

        Args:
            backtest_factor_records: 回测因子记录列表
                [{
                    'date': '2025-12-29',
                    'symbol': '000001.SZ',
                    'factor_values': {'pattern_recognition': 0.65, ...},
                    'next_day_return': 0.012
                }, ...]

        Returns:
            导入的记录数
        """
        logger.info(f"开始从回测数据批量导入: {len(backtest_factor_records)} 条记录")

        imported_count = 0

        for record in backtest_factor_records:
            try:
                date = record['date']
                symbol = record['symbol']
                factor_values = record.get('factor_values', {})
                next_day_return = record.get('next_day_return')

                # 记录因子值
                if factor_values:
                    self.record_factor_values(date, symbol, factor_values)

                # 记录收益率
                if next_day_return is not None:
                    self.record_returns(date, symbol, next_day_return)

                imported_count += 1

            except Exception as e:
                logger.debug(f"导入记录失败: {e}")
                continue

        logger.info(f"✓ 批量导入完成: {imported_count}/{len(backtest_factor_records)} 条记录")

        # 保存到磁盘
        self.save_to_disk()

        return imported_count
