import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.process.hold_stock_analyzer import HoldStockAnalyzer


class FakeDataProvider:
    def __init__(self, current_price):
        self.current_price = current_price

    def get_stock_data(self, symbol, *args, **kwargs):
        dates = pd.date_range("2026-01-01", periods=5, freq="D")
        data = pd.DataFrame({
            "High": [self.current_price] * 5,
            "Low": [self.current_price] * 5,
            "Close": [self.current_price] * 5,
        }, index=dates)
        price_info = {
            "current_price": self.current_price,
            "daily_high": self.current_price,
            "daily_low": self.current_price,
            "daily_change_percent": 0.0,
        }
        return data, {}, {}, price_info, pd.DataFrame(), {}


class FakeSystem:
    def __init__(self, current_price):
        self.data_provider = FakeDataProvider(current_price)


class HoldStockAnalyzerWatchTest(unittest.TestCase):
    def _analysis(self, buy_flag, current_price, existing_action):
        analyzer = HoldStockAnalyzer(system=FakeSystem(current_price))
        analyzer.today = date(2026, 1, 8)
        stock = {
            "symbol": "000001.SZ",
            "name": "平安银行",
            "purchase_date": "2026-01-02",
            "cost": 10.0,
            "buy_flag": buy_flag,
        }
        existing_result = {
            "操作建议": existing_action,
            "信心度": "80%",
            "决策理由": "AI因子建议买入",
        }

        return analyzer.analyze_position(stock, existing_result=existing_result)

    def test_watch_stock_confirms_buy_when_price_is_higher_after_observation(self):
        analysis = self._analysis("watch", current_price=10.5, existing_action="买入")

        self.assertEqual(analysis["持仓状态"], "watch")
        self.assertEqual(analysis["观察状态"], "确认可以买入")
        self.assertIn("确认可以买入", analysis["操作建议"])
        self.assertEqual(analysis["状态更新"], {})

    def test_watch_stock_resets_observation_when_price_is_not_higher(self):
        analysis = self._analysis("watch", current_price=9.8, existing_action="买入")

        self.assertEqual(analysis["观察状态"], "观察重置")
        self.assertEqual(analysis["状态更新"], {
            "buy_flag": "watch",
            "purchase_date": "2026-01-08",
            "cost": 9.8,
        })

    def test_sell_stock_enters_watch_when_ai_recommends_buy(self):
        analysis = self._analysis("sell", current_price=10.2, existing_action="买入")

        self.assertEqual(analysis["持仓状态"], "sell")
        self.assertEqual(analysis["观察状态"], "进入观察")
        self.assertEqual(analysis["状态更新"], {
            "buy_flag": "watch",
            "purchase_date": "2026-01-08",
            "cost": 10.2,
        })


if __name__ == "__main__":
    unittest.main()
