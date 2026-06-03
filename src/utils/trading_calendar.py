# -*- coding: utf-8 -*-
"""
中国A股交易日历工具
处理交易日判断、节假日检查、持仓分析等
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
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
            },

            # 2026年节假日
            2026: {
                # 元旦: 2026年1月1日
                datetime(2026, 1, 1),

                # 春节: 2026年2月11日-2月17日
                datetime(2026, 2, 11), datetime(2026, 2, 12), datetime(2026, 2, 13), datetime(2026, 2, 14),
                datetime(2026, 2, 15), datetime(2026, 2, 16), datetime(2026, 2, 17),

                # 清明节: 2026年4月4日-4月6日
                datetime(2026, 4, 4), datetime(2026, 4, 5), datetime(2026, 4, 6),

                # 劳动节: 2026年5月1日-5月5日
                datetime(2026, 5, 1), datetime(2026, 5, 2), datetime(2026, 5, 3), datetime(2026, 5, 4), datetime(2026, 5, 5),

                # 端午节: 2026年6月9日-6月11日
                datetime(2026, 6, 9), datetime(2026, 6, 10), datetime(2026, 6, 11),

                # 中秋节: 2026年9月15日-9月17日
                datetime(2026, 9, 15), datetime(2026, 9, 16), datetime(2026, 9, 17),

                # 国庆节: 2026年10月1日-10月8日
                datetime(2026, 10, 1), datetime(2026, 10, 2), datetime(2026, 10, 3), datetime(2026, 10, 4),
                datetime(2026, 10, 5), datetime(2026, 10, 6), datetime(2026, 10, 7), datetime(2026, 10, 8),
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

    def calculate_holding_days(self, purchase_date: datetime, end_date: datetime = None) -> int:
        """
        计算持股天数（仅计算交易日）

        Args:
            purchase_date: 买入日期
            end_date: 结束日期（默认为当前日期）

        Returns:
            持股交易日天数
        """
        if end_date is None:
            end_date = datetime.now()

        trading_days = 0
        check_date = purchase_date + timedelta(days=1)  # 从买入后第一天开始计算

        while check_date <= end_date:
            if self.is_trading_day(check_date):
                trading_days += 1
            check_date = check_date + timedelta(days=1)

        return trading_days

    def calculate_position_metrics(self,
                                 cost_price: float,
                                 current_price: float,
                                 purchase_date: datetime,
                                 end_date: datetime = None,
                                 stop_loss_percent: float = 0.1,
                                 profit_target_percent: float = 0.05) -> Dict:
        """
        计算持仓分析指标

        Args:
            cost_price: 成本价
            current_price: 当前价格
            purchase_date: 买入日期
            end_date: 结束日期（默认为当前日期）
            stop_loss_percent: 止损百分比（默认10%）
            profit_target_percent: 盈利目标百分比（默认5%）

        Returns:
            包含所有分析指标的字典
        """
        # 计算持股天数
        holding_days = self.calculate_holding_days(purchase_date, end_date)

        # 计算盈亏
        profit = current_price - cost_price
        profit_percent = (profit / cost_price * 100) if cost_price > 0 else 0

        # 计算止损价格和盈利目标
        stop_loss_price = cost_price * (1 - stop_loss_percent)
        profit_target = cost_price * (1 + profit_target_percent)

        # 计算平均日盈利
        avg_daily_profit = profit / holding_days if holding_days > 0 else 0

        # 风险提示
        if current_price <= stop_loss_price:
            risk_warning = '[警告] 已破止损'
            risk_level = 'danger'
        elif current_price >= profit_target:
            risk_warning = '[目标] 已达目标'
            risk_level = 'success'
        else:
            risk_warning = '[正常] 持续持有'
            risk_level = 'normal'

        return {
            'holding_days': holding_days,
            'profit': profit,
            'profit_percent': profit_percent,
            'stop_loss_price': stop_loss_price,
            'profit_target': profit_target,
            'avg_daily_profit': avg_daily_profit,
            'risk_warning': risk_warning,
            'risk_level': risk_level,
            'purchase_date': purchase_date,
            'current_date': end_date or datetime.now()
        }

    def get_position_summary(self, stocks: List[Dict]) -> Dict:
        """
        计算持仓汇总信息

        Args:
            stocks: 持股列表，每只股票应包含 cost, current_price, purchase_date

        Returns:
            持仓汇总信息
        """
        if not stocks:
            return {
                'total_stocks': 0,
                'total_cost': 0.0,
                'total_value': 0.0,
                'total_profit': 0.0,
                'total_profit_percent': 0.0,
                'total_holding_days': 0,
                'avg_holding_days': 0.0,
                'profitable_stocks': 0,
                'loss_stocks': 0,
                'risk_summary': {'danger': 0, 'warning': 0, 'normal': 0, 'success': 0}
            }

        total_cost = 0.0
        total_value = 0.0
        total_profit = 0.0
        total_holding_days = 0
        profitable_stocks = 0
        loss_stocks = 0
        risk_summary = {'danger': 0, 'warning': 0, 'normal': 0, 'success': 0}

        for stock in stocks:
            cost = stock.get('cost', 0.0)
            current_price = stock.get('current_price', cost)
            purchase_date_str = stock.get('purchase_date', '')

            if purchase_date_str:
                try:
                    purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d')
                except ValueError:
                    purchase_date = datetime.now()
            else:
                purchase_date = datetime.now()

            # 计算单股指标
            metrics = self.calculate_position_metrics(cost, current_price, purchase_date)

            total_cost += cost
            total_value += current_price
            total_profit += metrics['profit']
            total_holding_days += metrics['holding_days']

            if metrics['profit'] > 0:
                profitable_stocks += 1
            elif metrics['profit'] < 0:
                loss_stocks += 1

            # 风险汇总
            risk_level = metrics['risk_level']
            risk_summary[risk_level] = risk_summary.get(risk_level, 0) + 1

        total_profit_percent = (total_profit / total_cost * 100) if total_cost > 0 else 0
        avg_holding_days = total_holding_days / len(stocks) if stocks else 0

        return {
            'total_stocks': len(stocks),
            'total_cost': total_cost,
            'total_value': total_value,
            'total_profit': total_profit,
            'total_profit_percent': total_profit_percent,
            'total_holding_days': total_holding_days,
            'avg_holding_days': avg_holding_days,
            'profitable_stocks': profitable_stocks,
            'loss_stocks': loss_stocks,
            'risk_summary': risk_summary
        }

    def get_current_trading_day_info(self, date: datetime = None) -> Dict:
        """
        获取当前交易日详细信息（用于小红书文案生成）

        包括：当前日期、星期几、本周第几个交易日、是否为假期后第一周等

        Args:
            date: 日期（默认为当前日期）

        Returns:
            包含详细信息的字典
        """
        if date is None:
            date = datetime.now()

        # 基础日期信息
        date_only = date.replace(hour=0, minute=0, second=0, microsecond=0)
        weekday_name = date.strftime('%A')  # 英文星期名
        weekday_cn = self._get_chinese_weekday(date.weekday())  # 中文星期名
        date_str = date.strftime('%Y年%m月%d日')

        # 检查是否为交易日
        is_trading = self.is_trading_day(date)

        # 计算本周第几个交易日
        week_trading_day_num = self._get_week_trading_day_number(date)

        # 检查是否为假期后第一周及假期名称
        holiday_info = self._check_holiday_week(date)

        return {
            'current_date': date_str,
            'weekday_cn': weekday_cn,
            'weekday_num': date.weekday(),  # 0=周一, 6=周日
            'is_trading_day': is_trading,
            'week_trading_day_num': week_trading_day_num,
            'holiday_info': holiday_info,
            'summary_text': self._generate_date_summary_text(
                date_str, weekday_cn, week_trading_day_num, holiday_info
            )
        }

    def _get_chinese_weekday(self, weekday_num: int) -> str:
        """将星期数转换为中文"""
        weekday_map = {
            0: '周一',
            1: '周二',
            2: '周三',
            3: '周四',
            4: '周五',
            5: '周六',
            6: '周日'
        }
        return weekday_map.get(weekday_num, '未知')

    def _get_week_trading_day_number(self, date: datetime) -> int:
        """
        获取本周第几个交易日

        Args:
            date: 日期

        Returns:
            本周第几个交易日（1-5）
        """
        # 获取本周一（周一=0）
        monday = date - timedelta(days=date.weekday())

        # 计算从周一到当前日期有多少个交易日
        trading_days = 0
        current = monday

        while current <= date:
            if self.is_trading_day(current):
                trading_days += 1
            current += timedelta(days=1)

        return trading_days

    def _check_holiday_week(self, date: datetime) -> Dict:
        """
        检查是否为假期后的第一周

        Args:
            date: 日期

        Returns:
            包含假期信息的字典
        """
        # 获取本周一
        monday = date - timedelta(days=date.weekday())
        monday_only = monday.replace(hour=0, minute=0, second=0, microsecond=0)

        # 假期名称映射
        holiday_ranges = {
            '元旦': [
                (datetime(2025, 1, 1), datetime(2025, 1, 1)),
                (datetime(2026, 1, 1), datetime(2026, 1, 1)),
            ],
            '春节': [
                (datetime(2025, 1, 28), datetime(2025, 2, 3)),
                (datetime(2026, 2, 11), datetime(2026, 2, 17)),
            ],
            '清明': [
                (datetime(2025, 4, 5), datetime(2025, 4, 7)),
                (datetime(2026, 4, 4), datetime(2026, 4, 6)),
            ],
            '劳动': [
                (datetime(2025, 5, 1), datetime(2025, 5, 5)),
                (datetime(2026, 5, 1), datetime(2026, 5, 5)),
            ],
            '端午': [
                (datetime(2025, 5, 31), datetime(2025, 6, 2)),
                (datetime(2026, 6, 9), datetime(2026, 6, 11)),
            ],
            '中秋': [
                (datetime(2025, 10, 6), datetime(2025, 10, 8)),
                (datetime(2026, 9, 15), datetime(2026, 9, 17)),
            ],
            '国庆': [
                (datetime(2025, 10, 1), datetime(2025, 10, 8)),
                (datetime(2026, 10, 1), datetime(2026, 10, 8)),
            ],
        }

        # 检查本周一是否在任何假期后的一周内
        for holiday_name, ranges in holiday_ranges.items():
            for start_date, end_date in ranges:
                # 计算假期结束后的下一个交易日
                next_trading_day = end_date + timedelta(days=1)
                for _ in range(7):
                    if self.is_trading_day(next_trading_day):
                        break
                    next_trading_day += timedelta(days=1)

                # 获取该交易日所在周的周一
                holiday_week_monday = next_trading_day - timedelta(days=next_trading_day.weekday())

                # 检查本周一是否等于假期后第一周的周一
                if monday_only == holiday_week_monday:
                    # 计算这是假期后第几个交易日
                    days_after_holiday = (date - end_date).days
                    trading_days_after = 0
                    check_date = end_date + timedelta(days=1)

                    while check_date <= date:
                        if self.is_trading_day(check_date):
                            trading_days_after += 1
                        check_date += timedelta(days=1)

                    return {
                        'is_holiday_week': True,
                        'holiday_name': holiday_name,
                        'trading_days_after_holiday': trading_days_after,
                        'days_after_holiday': days_after_holiday
                    }

        # 不是假期后的第一周
        return {
            'is_holiday_week': False,
            'holiday_name': None,
            'trading_days_after_holiday': 0,
            'days_after_holiday': 0
        }

    def _generate_date_summary_text(self, date_str: str, weekday_cn: str,
                                    week_trading_day_num: int, holiday_info: Dict) -> str:
        """
        生成日期摘要文本（用于小红书文案）

        Args:
            date_str: 日期字符串（中文格式）
            weekday_cn: 中文星期名
            week_trading_day_num: 本周第几个交易日
            holiday_info: 假期信息

        Returns:
            摘要文本
        """
        summary = f"{date_str}（{weekday_cn}），本周第{week_trading_day_num}个交易日"

        if holiday_info['is_holiday_week'] and holiday_info['holiday_name']:
            holiday_name = holiday_info['holiday_name']
            trading_days = holiday_info['trading_days_after_holiday']
            summary += f"，{holiday_name}假期后第{trading_days}个交易日"

        return summary


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


def calculate_holding_days(purchase_date: datetime, end_date: datetime = None) -> int:
    """计算持股天数（快捷函数）"""
    return trading_calendar.calculate_holding_days(purchase_date, end_date)


def calculate_position_metrics(cost_price: float,
                            current_price: float,
                            purchase_date: datetime,
                            end_date: datetime = None,
                            stop_loss_percent: float = 0.1,
                            profit_target_percent: float = 0.05) -> Dict:
    """计算持仓分析指标（快捷函数）"""
    return trading_calendar.calculate_position_metrics(
        cost_price, current_price, purchase_date, end_date,
        stop_loss_percent, profit_target_percent
    )


def get_position_summary(stocks: List[Dict]) -> Dict:
    """计算持仓汇总信息（快捷函数）"""
    return trading_calendar.get_position_summary(stocks)


def get_current_trading_day_info(date: datetime = None) -> Dict:
    """获取当前交易日详细信息（快捷函数）"""
    return trading_calendar.get_current_trading_day_info(date)