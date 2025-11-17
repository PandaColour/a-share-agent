# -*- coding: utf-8 -*-
"""
前日涨幅过滤器
在选股阶段过滤掉前一天涨幅超过阈值的股票，避免追高
"""

import logging
from typing import List, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PreviousDayChangeFilter:
    """前日涨幅过滤器"""

    def __init__(self, config_manager, data_provider, hold_stocks: List[str] = None):
        """
        初始化过滤器

        Args:
            config_manager: 配置管理器
            data_provider: 数据提供者（用于获取历史数据）
            hold_stocks: 持仓股票列表（这些股票将跳过过滤）
        """
        self.config_manager = config_manager
        self.data_provider = data_provider
        self.logger = logging.getLogger(__name__)
        self.hold_stocks = hold_stocks or []

        # 从配置读取阈值
        filter_config = config_manager.get('analysis_settings.filters.previous_day_change', {})
        self.max_increase = filter_config.get('max_increase_percent', 9.0)

        # 初始化交易日历
        try:
            from src.utils.trading_calendar import trading_calendar
            self.trading_calendar = trading_calendar
            self.logger.info("交易日历初始化成功")
        except ImportError as e:
            self.logger.warning(f"交易日历导入失败: {e}，将使用简单逻辑")
            self.trading_calendar = None

        self.logger.info(f"前日涨幅过滤器初始化完成，阈值: {self.max_increase}%")
        if self.hold_stocks:
            self.logger.info(f"持仓股票 {len(self.hold_stocks)} 只将跳过过滤")

    def filter_stocks(self, stock_list: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """
        过滤前日大涨股票

        Args:
            stock_list: 股票列表 [(symbol, name), ...]

        Returns:
            过滤后的股票列表 [(symbol, name), ...]
        """
        if not stock_list:
            return []

        total_count = len(stock_list)
        self.logger.info(f"开始过滤前日大涨股票，共 {total_count} 只，阈值: {self.max_increase}%")

        kept_stocks = []
        filtered_count = 0

        for symbol, name in stock_list:
            try:
                # 获取股票数据（处理不同的返回格式）
                try:
                    result = self.data_provider.get_stock_data(symbol)
                    if isinstance(result, tuple) and len(result) == 4:
                        data, _, _, _ = result  # 期望的4个值格式
                    elif isinstance(result, tuple) and len(result) == 1:
                        data = result[0]  # 只有数据的格式
                    else:
                        data = result  # 直接就是数据
                except Exception as e:
                    self.logger.debug(f"获取数据格式异常 {symbol}: {e}")
                    data = None

                # 数据不足，保留（保守策略）
                if data is None or not hasattr(data, 'iloc') or len(data) < 3:
                    self.logger.debug(f"{symbol} 数据不足，保留")
                    kept_stocks.append((symbol, name))
                    continue

                # 持仓股票直接不过滤
                if symbol in self.hold_stocks:
                    self.logger.debug(f"跳过持仓股票 {name}({symbol}): 不过滤")
                    kept_stocks.append((symbol, name))
                    continue

                # 获取最新交易日期
                latest_date = data.index[-1] if hasattr(data.index[-1], 'date') else data.index[-1]
                if isinstance(latest_date, str):
                    latest_date = datetime.strptime(latest_date, '%Y-%m-%d')
                elif hasattr(latest_date, 'date'):
                    # 处理不同的date对象类型
                    import pandas as pd
                    if isinstance(latest_date, pd.Timestamp):
                        latest_date = latest_date.to_pydatetime()
                    else:
                        latest_date = datetime.combine(latest_date, datetime.min.time())
                else:
                    # 假设是datetime对象
                    latest_date = latest_date if isinstance(latest_date, datetime) else datetime.combine(latest_date, datetime.min.time())

                # 检查是否应该应用过滤器
                if self.trading_calendar:
                    should_filter = self.trading_calendar.should_apply_filter(latest_date)

                    # 如果数据不是前一个交易日，但数据充足，仍然使用最新数据过滤
                    if not should_filter and len(data) >= 3:
                        days_diff = (datetime.now() - latest_date).days
                        # 如果数据是0-3天内的（当日或周末情况），仍然使用最新数据过滤
                        if 0 <= days_diff <= 3:
                            self.logger.info(f"{name}({symbol}): 使用{days_diff}天前数据进行过滤（当前日期: {latest_date.strftime('%Y-%m-%d')}）")
                            should_filter = True
                        else:
                            self.logger.debug(f"跳过 {name}({symbol}): 数据日期 {latest_date.strftime('%Y-%m-%d')} 太旧（{days_diff}天前）")
                else:
                    # 简单逻辑：只有数据是昨天的才应用过滤器
                    yesterday = datetime.now() - timedelta(days=1)
                    should_filter = latest_date.date() == yesterday.date()

                if not should_filter:
                    days_diff = (datetime.now() - latest_date).days
                    self.logger.debug(f"跳过 {name}({symbol}): 数据日期 {latest_date.strftime('%Y-%m-%d')} 不是前一个交易日（{days_diff}天前）")
                    kept_stocks.append((symbol, name))
                    continue

                # 计算涨跌幅（使用最新的两个交易日数据）
                if len(data) < 2:
                    self.logger.debug(f"{symbol} 只有1个交易日数据，保留")
                    kept_stocks.append((symbol, name))
                    continue

                prev_close = data['Close'].iloc[-1]  # 最新收盘价
                prev_prev_close = data['Close'].iloc[-2]  # 前一个交易日收盘价

                prev_change = (prev_close - prev_prev_close) / prev_prev_close * 100

                # 普通股票才进行过滤
                if prev_change > self.max_increase:
                    filtered_count += 1
                    self.logger.info(f"过滤 {name}({symbol}): 前日涨幅 {prev_change:+.2f}% > {self.max_increase}% (数据日期: {latest_date.strftime('%Y-%m-%d')})")
                else:
                    self.logger.debug(f"保留 {name}({symbol}): 前日涨幅 {prev_change:+.2f}% <= {self.max_increase}% (数据日期: {latest_date.strftime('%Y-%m-%d')})")
                    kept_stocks.append((symbol, name))

            except Exception as e:
                # 出错时保留（保守策略）
                self.logger.warning(f"检查 {symbol} 前日涨幅失败: {e}，保留该股票")
                kept_stocks.append((symbol, name))

        kept_count = len(kept_stocks)
        self.logger.info(f"过滤完成: 保留 {kept_count} 只，过滤 {filtered_count} 只")

        return kept_stocks
