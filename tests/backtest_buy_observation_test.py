import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.advanced_backtest_engine import AdvancedBacktestEngine


class FakeConfig:
    def get_backtest_config(self):
        return {
            "capital_management": {
                "initial_capital": 100000.0,
                "max_position_size": 1.0,
            },
            "transaction_costs": {
                "commission_rate": 0.0,
                "min_commission": 0.0,
                "stamp_duty_rate": 0.0,
            },
        }

    def get_analysis_config(self):
        return {
            "risk_management": {
                "max_holding_days": 10,
                "enable_forced_exit": False,
            }
        }


class BacktestBuyObservationTest(unittest.TestCase):
    def _engine(self):
        return AdvancedBacktestEngine(config_manager=FakeConfig())

    def _recommendation(self, date, recommendation):
        return {
            "id": f"{date}-{recommendation}",
            "symbol": "000001.SZ",
            "stock_name": "平安银行",
            "analysis_time": f"{date} 15:00:00",
            "recommendation": recommendation,
            "confidence": 1.0,
        }

    def _market_data(self, closes):
        index = pd.to_datetime(list(closes.keys()))
        return {
            "000001.SZ": pd.DataFrame(
                {
                    "Open": list(closes.values()),
                    "High": list(closes.values()),
                    "Low": list(closes.values()),
                    "Close": list(closes.values()),
                },
                index=index,
            )
        }

    def _buy_trades(self, engine):
        return [
            trade for trade in engine.trade_history
            if trade["action"] == "买入"
        ]

    def test_buy_signal_buys_after_three_trading_days_when_close_is_higher(self):
        engine = self._engine()
        recommendations = [self._recommendation("2026-01-02", "买入")]
        market_data = self._market_data({
            "2026-01-02": 10.0,
            "2026-01-05": 9.8,
            "2026-01-06": 10.0,
            "2026-01-07": 10.5,
        })

        engine.run_strategy_backtest(recommendations, market_data)

        buy_trades = self._buy_trades(engine)
        self.assertEqual(len(buy_trades), 1)
        self.assertEqual(buy_trades[0]["date"], "2026-01-07")
        self.assertEqual(buy_trades[0]["price"], 10.5)

    def test_buy_observation_resets_when_third_day_close_is_not_higher(self):
        engine = self._engine()
        recommendations = [self._recommendation("2026-01-02", "买入")]
        market_data = self._market_data({
            "2026-01-02": 10.0,
            "2026-01-05": 9.9,
            "2026-01-06": 9.8,
            "2026-01-07": 9.7,
            "2026-01-08": 9.7,
            "2026-01-09": 9.8,
            "2026-01-12": 10.0,
        })

        engine.run_strategy_backtest(recommendations, market_data)

        buy_trades = self._buy_trades(engine)
        self.assertEqual(len(buy_trades), 1)
        self.assertEqual(buy_trades[0]["date"], "2026-01-12")
        self.assertEqual(buy_trades[0]["price"], 10.0)

    def test_sell_signal_cancels_pending_buy_observation(self):
        engine = self._engine()
        recommendations = [
            self._recommendation("2026-01-02", "买入"),
            self._recommendation("2026-01-06", "卖出"),
        ]
        market_data = self._market_data({
            "2026-01-02": 10.0,
            "2026-01-05": 10.1,
            "2026-01-06": 10.2,
            "2026-01-07": 10.5,
        })

        engine.run_strategy_backtest(recommendations, market_data)

        self.assertEqual(self._buy_trades(engine), [])


if __name__ == "__main__":
    unittest.main()
