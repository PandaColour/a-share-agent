"""交易日历回归测试，休市日期依据上交所 2026 年休市公告。"""
from datetime import datetime, timedelta
import unittest

from src.utils.trading_calendar import TradingCalendar


class TradingCalendarTests(unittest.TestCase):
    def setUp(self):
        self.calendar = TradingCalendar()

    def test_reported_september_17_summary(self):
        info = self.calendar.get_current_trading_day_info(datetime(2026, 9, 17, 8, 30))
        self.assertTrue(info['is_trading_day'])
        self.assertEqual(info['week_trading_day_num'], 4)
        self.assertFalse(info['holiday_info']['is_holiday_week'])
        self.assertEqual(info['summary_text'], '2026年09月17日（周四），本周第4个交易日')
        self.assertEqual(
            self.calendar.get_previous_trading_day(datetime(2026, 9, 17)),
            datetime(2026, 9, 16),
        )

    def test_all_2026_trading_dates_match_exchange_schedule(self):
        # https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml
        closures = [('01-01', '01-03'), ('02-15', '02-23'), ('04-04', '04-06'),
                    ('05-01', '05-05'), ('06-19', '06-21'), ('09-25', '09-27'),
                    ('10-01', '10-07')]
        day = datetime(2026, 1, 1)
        while day.year == 2026:
            date_key = day.strftime('%m-%d')
            expected = day.weekday() < 5 and not any(
                start <= date_key <= end for start, end in closures
            )
            with self.subTest(date=day):
                self.assertEqual(self.calendar.is_trading_day(day), expected)
            day += timedelta(days=1)

    def test_dates_before_reopening_are_not_post_holiday(self):
        # 2025 年元旦与复市日在同一周，独立验证边界逻辑。
        for day in [datetime(2024, 12, 30), datetime(2024, 12, 31),
                    datetime(2025, 1, 1), datetime(2026, 4, 6),
                    datetime(2026, 5, 4), datetime(2026, 5, 5),
                    datetime(2026, 10, 5), datetime(2026, 10, 7)]:
            with self.subTest(date=day):
                info = self.calendar.get_current_trading_day_info(day)
                self.assertFalse(info['holiday_info']['is_holiday_week'])
                self.assertNotIn('假期后', info['summary_text'])

    def test_first_reopening_day_for_each_2026_holiday(self):
        cases = [('01-05', '元旦'), ('02-24', '春节'), ('04-07', '清明'),
                 ('05-06', '劳动'), ('06-22', '端午'), ('09-28', '中秋'),
                 ('10-08', '国庆')]
        for date_key, name in cases:
            with self.subTest(holiday=name):
                day = datetime.strptime('2026-' + date_key, '%Y-%m-%d')
                info = self.calendar.get_current_trading_day_info(day)['holiday_info']
                self.assertTrue(info['is_holiday_week'])
                self.assertEqual(info['holiday_name'], name)
                self.assertEqual(info['trading_days_after_holiday'], 1)

    def test_mid_autumn_post_holiday_count_and_week_boundary(self):
        info = self.calendar.get_current_trading_day_info(datetime(2026, 9, 30, 15))
        self.assertEqual(info['holiday_info']['trading_days_after_holiday'], 3)
        info = self.calendar.get_current_trading_day_info(datetime(2026, 10, 12))
        self.assertFalse(info['holiday_info']['is_holiday_week'])

    def test_previous_trading_day_across_long_closures(self):
        for current, expected in [('2026-02-24', '2026-02-13'),
                                  ('2026-10-08', '2026-09-30')]:
            with self.subTest(date=current):
                self.assertEqual(
                    self.calendar.get_previous_trading_day(datetime.fromisoformat(current)),
                    datetime.fromisoformat(expected),
                )


if __name__ == '__main__':
    unittest.main()
