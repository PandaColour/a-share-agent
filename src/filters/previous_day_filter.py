# -*- coding: utf-8 -*-
"""
前日涨幅过滤器
在选股阶段过滤掉前一天涨幅超过阈值的股票，避免追高
"""

import logging
from typing import List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class PreviousDayChangeFilter:
    """前日涨幅过滤器"""

    def __init__(self, config_manager, data_provider):
        """
        初始化过滤器

        Args:
            config_manager: 配置管理器
            data_provider: 数据提供者（用于获取历史数据）
        """
        self.config_manager = config_manager
        self.data_provider = data_provider
        self.logger = logging.getLogger(__name__)

        # 从配置读取阈值
        filter_config = config_manager.get('analysis_settings.filters.previous_day_change', {})
        self.max_increase = filter_config.get('max_increase_percent', 9.0)
        self.logger.info(f"前日涨幅过滤器初始化完成，阈值: {self.max_increase}%")

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
                # 获取股票数据
                data, _, _, _ = self.data_provider.get_stock_data(symbol)

                # 数据不足，保留（保守策略）
                if data is None or len(data) < 3:
                    self.logger.debug(f"{symbol} 数据不足，保留")
                    kept_stocks.append((symbol, name))
                    continue

                # 计算前一日涨跌幅
                # data.iloc[-1] = 当日
                # data.iloc[-2] = 前一日（检查日）
                # data.iloc[-3] = 前两日（基准日）
                prev_close = data['Close'].iloc[-2]  # 前一日收盘
                prev_prev_close = data['Close'].iloc[-3]  # 前两日收盘

                prev_change = (prev_close - prev_prev_close) / prev_prev_close * 100

                # 判断是否过滤
                if prev_change > self.max_increase:
                    filtered_count += 1
                    self.logger.info(f"过滤 {name}({symbol}): 前日涨幅 {prev_change:+.2f}% > {self.max_increase}%")
                else:
                    kept_stocks.append((symbol, name))

            except Exception as e:
                # 出错时保留（保守策略）
                self.logger.warning(f"检查 {symbol} 前日涨幅失败: {e}，保留该股票")
                kept_stocks.append((symbol, name))

        kept_count = len(kept_stocks)
        self.logger.info(f"过滤完成: 保留 {kept_count} 只，过滤 {filtered_count} 只")

        return kept_stocks
