import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils import hold_stock_io


class HoldStockStatusTest(unittest.TestCase):
    def _write_config(self, hold_stocks):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "hold_stock.json"
        path.write_text(json.dumps({
            "description": "test",
            "last_updated": "2026-07-01",
            "hold_stocks": hold_stocks,
        }), encoding="utf-8")
        return path

    def test_load_hold_stocks_normalizes_legacy_boolean_statuses(self):
        path = self._write_config([
            {"symbol": "000001.SZ", "name": "平安银行", "buy_flag": True},
            {"symbol": "000002.SZ", "name": "万科A", "buy_flag": False},
            {"symbol": "000003.SZ", "name": "观察股", "buy_flag": "watch"},
            {"symbol": "000004.SZ", "name": "缺省股"},
        ])

        stocks = hold_stock_io.load_hold_stocks(path)

        self.assertEqual(
            [stock["buy_flag"] for stock in stocks],
            ["buy", "sell", "watch", "buy"],
        )

    def test_add_buy_recommendations_to_watch_adds_missing_buy_signals(self):
        path = self._write_config([
            {
                "symbol": "000001.SZ",
                "name": "平安银行",
                "purchase_date": "2026-07-01",
                "cost": 10.0,
                "buy_flag": True,
            }
        ])
        analysis_results = [
            {
                "股票代码": "000001.SZ",
                "股票名称": "平安银行",
                "操作建议": "买入",
                "当前价格": "11.00元",
            },
            {
                "股票代码": "000002.SZ",
                "股票名称": "万科A",
                "操作建议": "买入",
                "当前价格": "12.34元",
            },
            {
                "股票代码": "000003.SZ",
                "股票名称": "非买入",
                "操作建议": "持有",
                "当前价格": "9.99元",
            },
        ]

        summary = hold_stock_io.add_buy_recommendations_to_watch(
            analysis_results,
            as_of_date="2026-07-23",
            hold_stock_path=path,
        )

        config = json.loads(path.read_text(encoding="utf-8"))
        stocks = {stock["symbol"]: stock for stock in config["hold_stocks"]}

        self.assertEqual(summary["added_symbols"], ["000002.SZ"])
        self.assertEqual(stocks["000001.SZ"]["buy_flag"], "buy")
        self.assertEqual(stocks["000002.SZ"]["buy_flag"], "watch")
        self.assertEqual(stocks["000002.SZ"]["purchase_date"], "2026-07-23")
        self.assertEqual(stocks["000002.SZ"]["cost"], 12.34)
        self.assertNotIn("000003.SZ", stocks)

    def test_add_buy_recommendations_to_watch_updates_existing_sell_signal(self):
        path = self._write_config([
            {
                "symbol": "000002.SZ",
                "name": "万科A",
                "purchase_date": "2026-07-01",
                "cost": 10.0,
                "buy_flag": "sell",
            },
            {
                "symbol": "000003.SZ",
                "name": "观察股",
                "purchase_date": "2026-07-01",
                "cost": 9.0,
                "buy_flag": "watch",
            },
        ])

        summary = hold_stock_io.add_buy_recommendations_to_watch(
            [
                {
                    "股票代码": "000002.SZ",
                    "股票名称": "万科A",
                    "操作建议": "买入",
                    "当前价格": "12.34元",
                },
                {
                    "股票代码": "000003.SZ",
                    "股票名称": "观察股",
                    "操作建议": "买入",
                    "当前价格": "10.01元",
                },
            ],
            as_of_date="2026-07-23",
            hold_stock_path=path,
        )

        config = json.loads(path.read_text(encoding="utf-8"))
        stocks = {stock["symbol"]: stock for stock in config["hold_stocks"]}

        self.assertEqual(summary["updated_symbols"], ["000002.SZ"])
        self.assertEqual(stocks["000002.SZ"]["buy_flag"], "watch")
        self.assertEqual(stocks["000002.SZ"]["purchase_date"], "2026-07-23")
        self.assertEqual(stocks["000002.SZ"]["cost"], 12.34)
        self.assertEqual(stocks["000003.SZ"]["buy_flag"], "watch")
        self.assertEqual(stocks["000003.SZ"]["purchase_date"], "2026-07-01")


if __name__ == "__main__":
    unittest.main()
