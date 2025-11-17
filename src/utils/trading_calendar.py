# -*- coding: utf-8 -*-
"""
中国A股交易日历工具
处理交易日判断、节假日检查等
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List
import logging

logger = logging.getLogger(__name__)


class TradingCalendar:
    """中国A股交易日历"""

    def __init__(self):
        """初始化交易日历"""
        self.logger = logging.getLogger(__name__)

        # 中国A股节假日数据（支持多年份）
        self.holidays = {
            # 2024年节假日
            2024: {
                # 元旦: 2024年1月1日
                datetime(2024, 1, 1),

                # 春节: 2024年2月10日-2月17日
                datetime(2024, 2, 10), datetime(2024, 2, 11), datetime(2024, 2, 12), datetime(2024, 2, 13),
                datetime(2024, 2, 14), datetime(2024, 2, 15), datetime(2024, 2, 16), datetime(2024, 2, 17),

                # 清明节: 2024年4月4日-4月6日
                datetime(2024, 4, 4), datetime(2024, 4, 5), datetime(2024, 4, 6),

                # 劳动节: 2024年5月1日-5月5日
                datetime(2024, 5, 1), datetime(2024, 5, 2), datetime(2024, 5, 3), datetime(2024, 5, 4), datetime(2024, 5, 5),

                # 端午节: 2024年6月10日-6月12日
                datetime(2024, 6, 10), datetime(2024, 6, 11), datetime(2024, 6, 12),

                # 中秋节: 2024年9月15日-9月17日
                datetime(2024, 9, 15), datetime(2024, 9, 16), datetime(2024, 9, 17),

                # 国庆节: 2024年10月1日-10月7日
                datetime(2024, 10, 1), datetime(2024, 10, 2), datetime(2024, 10, 3), datetime(2024, 10, 4),
                datetime(2024, 10, 5), datetime(2024, 10, 6), datetime(2024, 10, 7),
            },

            # 2025年节假日
            2025: {
                # 元旦: 2025年1月1日
                datetime(2025, 1, 1),

                # 春节: 2025年1月28日-2月3日
                datetime(2025, 1, 28), datetime(2025, 1, 29), datetime(2025, 1, 30), datetime(2025, 1, 31),
                datetime(2025, 2, 1), datetime(2025, 2, 2), datetime(2025, 2, 3),

                # 清明节: 2025年4月5日-4月7日
                datetime(2025, 4, 5), datetime(2025, 4, 6), datetime(2025, 4, 7),

                # 劳动节: 2025年5月1日-5月5日
                datetime(2025, 5, 1), datetime(2025, 5, 2), datetime(2025, 5, 3), datetime(2025, 5, 4), datetime(2025, 5, 5),

                # 端午节: 2025年5月31日-6月2日
                datetime(2025, 5, 31), datetime(2025, 6, 1), datetime(2025, 6, 2),

                # 中秋节: 2025年10月6日-10月8日
                datetime(2025, 10, 6), datetime(2025, 10, 7), datetime(2025, 10, 8),

                # 国庆节: 2025年10月1日-10月8日
                datetime(2025, 10, 1), datetime(2025, 10, 2), datetime(2025, 10, 3), datetime(2025, 10, 4),
                datetime(2025, 10, 5), datetime(2025, 10, 6), datetime(2025, 10, 7), datetime(2025, 10, 8),
            }
        }

        # 周末（周六、周日）
        self.weekend_days = {5, 6}  # 周六=5, 周日=6

        # 统计总节假日数
        total_holidays = sum(len(holidays) for holidays in self.holidays.values())
        self.logger.info(f"交易日历初始化完成，{len(self.holidays)}个年份，共{total_holidays}个节假日")

    def is_trading_day(self, date: datetime) -> bool:
        """
        判断是否为交易日

        Args:
            date: 日期

        Returns:
            True: 是交易日, False: 非交易日
        """
        # 只保留日期部分，去除时间
        date_only = date.replace(hour=0, minute=0, second=0, microsecond=0)

        # 检查是否是周末
        if date.weekday() in self.weekend_days:
            return False

        # 检查是否是节假日（支持多年份）
        year = date.year
        if year in self.holidays:
            if date_only in self.holidays[year]:
                return False

        return True

    def get_previous_trading_day(self, date: datetime) -> datetime:
        """
        获取前一个交易日

        Args:
            date: 当前日期

        Returns:
            前一个交易日的日期
        """
        current_date = date - timedelta(days=1)

        # 最多向前查找7天（足够跨过周末和短假期）
        for _ in range(7):
            if self.is_trading_day(current_date):
                return current_date
            current_date -= timedelta(days=1)

        # 如果找不到，返回7天前的日期（保守策略）
        self.logger.warning(f"无法找到前一个交易日，使用7天前日期")
        return date - timedelta(days=7)

    def get_days_since_last_trading_day(self, date: datetime) -> int:
        """
        获取距离前一个交易日的天数

        Args:
            date: 当前日期

        Returns:
            距离前一个交易日的天数
        """
        if not self.is_trading_day(date):
            return 0

        prev_trading_day = self.get_previous_trading_day(date)
        return (date - prev_trading_day).days

    def should_apply_filter(self, data_date: datetime, filter_date: datetime = None) -> bool:
        """
        判断是否应该应用过滤器

        逻辑：只有当数据日期是前一个交易日时才应用过滤器
        如果数据日期是更早的日期（比如节假日前），则跳过过滤

        Args:
            data_date: 股票数据的日期
            filter_date: 过滤检查的日期（默认为当前日期）

        Returns:
            True: 应该应用过滤器, False: 跳过过滤
        """
        if filter_date is None:
            filter_date = datetime.now()

        # 如果过滤日期不是交易日，不应用过滤器
        if not self.is_trading_day(filter_date):
            self.logger.debug(f"过滤日期 {filter_date.strftime('%Y-%m-%d')} 不是交易日，跳过过滤")
            return False

        # 获取前一个交易日
        prev_trading_day = self.get_previous_trading_day(filter_date)

        # 检查数据日期是否是前一个交易日
        data_date_only = data_date.replace(hour=0, minute=0, second=0, microsecond=0)
        prev_trading_day_only = prev_trading_day.replace(hour=0, minute=0, second=0, microsecond=0)

        if data_date_only == prev_trading_day_only:
            self.logger.debug(f"数据日期 {data_date.strftime('%Y-%m-%d')} 是前一个交易日，应用过滤器")
            return True
        else:
            days_diff = (filter_date - data_date).days
            self.logger.debug(f"数据日期 {data_date.strftime('%Y-%m-%d')} 不是前一个交易日（{days_diff}天前），跳过过滤")
            return False

    def get_trading_day_info(self, date: datetime = None) -> dict:
        """
        获取交易日信息

        Args:
            date: 日期（默认为当前日期）

        Returns:
            交易日信息字典
        """
        if date is None:
            date = datetime.now()

        is_trading = self.is_trading_day(date)
        days_since_last = self.get_days_since_last_trading_day(date)
        prev_trading_day = self.get_previous_trading_day(date) if is_trading else None

        # 检查是否是节假日（支持多年份）
        date_only = date.replace(hour=0, minute=0, second=0, microsecond=0)
        year = date.year
        is_holiday = False
        if year in self.holidays:
            is_holiday = date_only in self.holidays[year]

        return {
            'date': date,
            'is_trading_day': is_trading,
            'days_since_last_trading_day': days_since_last,
            'previous_trading_day': prev_trading_day,
            'weekday': date.strftime('%A'),
            'is_weekend': date.weekday() in self.weekend_days,
            'is_holiday': is_holiday
        }

    def add_holidays(self, year: int, holidays: List[datetime]) -> None:
        """
        添加指定年份的节假日

        Args:
            year: 年份
            holidays: 节假日列表
        """
        if year not in self.holidays:
            self.holidays[year] = set()

        self.holidays[year].update(holidays)
        self.logger.info(f"添加 {year} 年 {len(holidays)} 个节假日，总计 {len(self.holidays[year])} 个")

    def get_holidays(self, year: int) -> List[datetime]:
        """
        获取指定年份的节假日

        Args:
            year: 年份

        Returns:
            节假日列表
        """
        return list(self.holidays.get(year, set()))

    def get_available_years(self) -> List[int]:
        """
        获取已配置的年份列表

        Returns:
            年份列表
        """
        return sorted(self.holidays.keys())

    def remove_holidays(self, year: int, holidays: List[datetime]) -> None:
        """
        移除指定年份的节假日

        Args:
            year: 年份
            holidays: 要移除的节假日列表
        """
        if year in self.holidays:
            for holiday in holidays:
                self.holidays[year].discard(holiday)
            self.logger.info(f"移除 {year} 年 {len(holidays)} 个节假日，剩余 {len(self.holidays[year])} 个")


# 全局实例
trading_calendar = TradingCalendar()


def is_trading_day(date: datetime) -> bool:
    """判断是否为交易日（快捷函数）"""
    return trading_calendar.is_trading_day(date)


def should_apply_previous_day_filter(data_date: datetime, filter_date: datetime = None) -> bool:
    """判断是否应该应用前日涨幅过滤器（快捷函数）"""
    return trading_calendar.should_apply_filter(data_date, filter_date)


def get_trading_info() -> dict:
    """获取当前交易日信息（快捷函数）"""
    return trading_calendar.get_trading_day_info()