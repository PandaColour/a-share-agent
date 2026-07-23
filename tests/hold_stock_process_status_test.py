import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.process.hold_stock_process import HoldStockProcess


class HoldStockProcessStatusTest(unittest.TestCase):
    def _temp_dir(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return Path(temp_dir.name)

    def _write_config(self, directory):
        path = directory / "hold_stock.json"
        path.write_text(json.dumps({
            "description": "test",
            "last_updated": "2026-07-01",
            "hold_stocks": [
                {"symbol": "000001.SZ", "name": "买入股", "buy_flag": True},
                {"symbol": "000002.SZ", "name": "卖出股", "buy_flag": False},
                {"symbol": "000003.SZ", "name": "观察股", "buy_flag": "watch"},
            ],
        }), encoding="utf-8")
        return path

    def test_load_hold_stocks_excludes_sell_status_from_holdings_analysis(self):
        directory = self._temp_dir()
        path = self._write_config(directory)
        process = HoldStockProcess(hold_stock_path=path)

        stocks = process.load_hold_stocks()

        self.assertEqual([stock["symbol"] for stock in stocks], [
            "000001.SZ",
            "000003.SZ",
        ])
        self.assertEqual([stock["buy_flag"] for stock in stocks], [
            "buy",
            "watch",
        ])

    def test_apply_state_updates_writes_observation_changes(self):
        directory = self._temp_dir()
        path = self._write_config(directory)
        process = HoldStockProcess(hold_stock_path=path)

        summary = process.apply_state_updates([
            {
                "股票代码": "000002.SZ",
                "状态更新": {
                    "buy_flag": "watch",
                    "purchase_date": "2026-07-23",
                    "cost": 12.34,
                },
            },
            {
                "股票代码": "000003.SZ",
                "状态更新": {
                    "buy_flag": "sell",
                },
            },
        ])

        config = json.loads(path.read_text(encoding="utf-8"))
        stocks = {stock["symbol"]: stock for stock in config["hold_stocks"]}
        self.assertEqual(summary["updated_symbols"], ["000002.SZ", "000003.SZ"])
        self.assertEqual(stocks["000002.SZ"]["buy_flag"], "watch")
        self.assertEqual(stocks["000002.SZ"]["purchase_date"], "2026-07-23")
        self.assertEqual(stocks["000002.SZ"]["cost"], 12.34)
        self.assertEqual(stocks["000003.SZ"]["buy_flag"], "sell")

    def test_save_analysis_to_csv_includes_status_and_observation_columns(self):
        directory = self._temp_dir()
        process = HoldStockProcess(output_dir=directory)

        csv_file = process.save_analysis_to_csv([
            {
                "股票代码": "000002.SZ",
                "股票名称": "卖出股",
                "持仓状态": "watch",
                "观察状态": "确认可以买入",
                "成本价": 10.0,
                "当前价格": 10.5,
                "持仓天数": 4,
                "持仓收益": 0.5,
                "持仓收益率": 5.0,
                "止损价格": None,
                "距离止损": "N/A",
                "系统建议": "买入",
                "系统信心度": "80%",
                "操作建议": "确认可以买入-观察达标",
                "建议理由": ["观察达标"],
            }
        ])

        with open(csv_file, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        self.assertEqual(rows[0]["持仓状态"], "watch")
        self.assertEqual(rows[0]["观察状态"], "确认可以买入")


if __name__ == "__main__":
    unittest.main()
