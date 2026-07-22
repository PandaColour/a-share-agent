# -*- coding: utf-8 -*-

import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

from src.agents.buy_confirmation_agent import (
    BUY_ACTION,
    HOLD_ACTION,
    SELL_ACTION,
    BuyConfirmationAgent,
)


class FakeCliAgent:
    def __init__(self, output):
        self.output = output
        self.calls = 0
        self.last_prompt = ""

    def send_message(self, prompt):
        self.calls += 1
        self.last_prompt = prompt
        return self.output


def load_process_module_with_stubs():
    """Load process module while stubbing external provider dependencies."""
    data_module = types.ModuleType("src.data.multi_source_data_provider")
    news_module = types.ModuleType("src.utils.real_news_fetcher")

    class StubDataProvider:
        pass

    class StubNewsFetcher:
        pass

    data_module.MultiSourceDataProvider = StubDataProvider
    news_module.RealNewsFetcher = StubNewsFetcher

    sys.modules["src.data.multi_source_data_provider"] = data_module
    sys.modules["src.utils.real_news_fetcher"] = news_module
    sys.modules.pop("src.process.buy_confirmation_process", None)
    return importlib.import_module("src.process.buy_confirmation_process")


class BuyConfirmationAgentTest(unittest.TestCase):
    def setUp(self):
        self.context = {
            "symbol": "600519.SH",
            "stock_name": "贵州茅台",
            "original_action": BUY_ACTION,
            "data_quality": {
                "fundamental_data_available": True,
                "sentiment_data_available": True,
                "news_count": 2,
            },
        }

    def _raw(self, final_action=BUY_ACTION, original_action=BUY_ACTION, confidence=0.78, reason="复核通过"):
        return json.dumps(
            {
                "symbol": "600519.SH",
                "stock_name": "贵州茅台",
                "original_action": original_action,
                "final_action": final_action,
                "confidence": confidence,
                "fundamental_view": "positive",
                "sentiment_view": "neutral",
                "risk_flags": ["估值偏高"],
                "reason": reason,
                "evidence": [{"type": "fundamental", "source": "mock"}],
                "data_quality": self.context["data_quality"],
            },
            ensure_ascii=False,
        )

    def test_valid_json_keeps_buy_action(self):
        agent_backend = FakeCliAgent(self._raw())
        result = BuyConfirmationAgent(agent=agent_backend).review(self.context)

        self.assertEqual(result["final_action"], BUY_ACTION)
        self.assertEqual(result["agent_parse_status"], "success")
        self.assertEqual(agent_backend.calls, 1)

    def test_hold_candidate_can_upgrade_to_buy(self):
        context = dict(self.context, original_action=HOLD_ACTION)
        result = BuyConfirmationAgent(agent=FakeCliAgent(self._raw(original_action=HOLD_ACTION))).review(context)

        self.assertEqual(result["original_action"], HOLD_ACTION)
        self.assertEqual(result["final_action"], BUY_ACTION)
        self.assertEqual(result["agent_parse_status"], "success")

    def test_hold_candidate_can_change_to_sell(self):
        context = dict(self.context, original_action=HOLD_ACTION)
        result = BuyConfirmationAgent(
            agent=FakeCliAgent(self._raw(final_action=SELL_ACTION, original_action=HOLD_ACTION))
        ).review(context)

        self.assertEqual(result["final_action"], SELL_ACTION)
        self.assertEqual(result["agent_parse_status"], "success")

    def test_buy_candidate_can_change_to_sell(self):
        result = BuyConfirmationAgent(agent=FakeCliAgent(self._raw(final_action=SELL_ACTION))).review(self.context)

        self.assertEqual(result["final_action"], SELL_ACTION)
        self.assertEqual(result["agent_parse_status"], "success")

    def test_invalid_json_falls_back_to_hold_by_default(self):
        result = BuyConfirmationAgent(agent=FakeCliAgent("not-json")).review(self.context)

        self.assertEqual(result["final_action"], HOLD_ACTION)
        self.assertEqual(result["agent_parse_status"], "failed")
        self.assertIn("Agent输出解析或校验失败", result["reason"])

    def test_invalid_action_empty_reason_and_bad_confidence_fall_back(self):
        cases = [
            self._raw(final_action="加仓"),
            self._raw(reason=""),
            self._raw(confidence=1.2),
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                result = BuyConfirmationAgent(agent=FakeCliAgent(raw)).review(self.context)
                self.assertEqual(result["final_action"], HOLD_ACTION)
                self.assertEqual(result["agent_parse_status"], "failed")

    def test_keep_original_policy_only_applies_to_parse_failure(self):
        result = BuyConfirmationAgent(
            agent=FakeCliAgent("not-json"),
            on_parse_failure="keep_original",
        ).review(self.context)

        self.assertEqual(result["final_action"], BUY_ACTION)
        self.assertEqual(result["agent_parse_status"], "failed")


class BuyConfirmationProcessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.process_module = load_process_module_with_stubs()
        cls.BuyConfirmationProcess = cls.process_module.BuyConfirmationProcess

    def test_execute_skips_when_no_buy_or_hold_candidates(self):
        process = self.BuyConfirmationProcess()
        result = process.execute(
            [{"股票代码": "000001.SZ", "股票名称": "平安银行", "操作建议": SELL_ACTION}]
        )

        self.assertEqual(result["processed_count"], 0)
        self.assertEqual(result["review_results"], [])

    def test_execute_includes_hold_candidates(self):
        process = self.BuyConfirmationProcess()
        candidates = process._find_buy_candidates(
            [
                {"股票代码": "000001.SZ", "操作建议": BUY_ACTION},
                {"股票代码": "000002.SZ", "操作建议": HOLD_ACTION},
                {"股票代码": "000003.SZ", "操作建议": SELL_ACTION},
            ]
        )

        self.assertEqual([item["股票代码"] for item in candidates], ["000001.SZ", "000002.SZ"])

    def test_execute_merges_hold_to_sell_and_writes_audit_file(self):
        review = {
            "symbol": "000001.SZ",
            "stock_name": "平安银行",
            "original_action": HOLD_ACTION,
            "final_action": SELL_ACTION,
            "confidence": 0.66,
            "fundamental_view": "negative",
            "sentiment_view": "negative",
            "risk_flags": ["新闻偏负面"],
            "reason": "基本面和情绪面均转弱。",
            "evidence": [],
            "data_quality": {"fundamental_data_available": True, "sentiment_data_available": True, "news_count": 1},
            "agent_parse_status": "success",
            "raw_output": "{}",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            process = self.BuyConfirmationProcess(
                output_dir=Path(temp_dir),
            )
            process._review_one = lambda candidate: review.copy()

            results = [
                {
                    "股票代码": "000001.SZ",
                    "股票名称": "平安银行",
                    "操作建议": HOLD_ACTION,
                    "置信度": "70.00%",
                    "风险等级": "中",
                    "当前价格": "10.00元",
                    "决策理由": "技术信号持有",
                }
            ]
            outcome = process.execute(results)
            audit_path = Path(temp_dir) / "agent_review_results.json"

            self.assertEqual(outcome["processed_count"], 1)
            self.assertEqual(results[0]["原操作建议"], HOLD_ACTION)
            self.assertEqual(results[0]["操作建议"], SELL_ACTION)
            self.assertEqual(results[0]["Agent复核建议"], SELL_ACTION)
            self.assertEqual(results[0]["Agent复核置信度"], "66.00%")
            self.assertEqual(results[0]["Agent解析状态"], "success")
            self.assertEqual(results[0]["决策理由"], "技术信号持有")
            self.assertTrue(audit_path.exists())

    def test_execute_uses_agent_even_when_external_data_missing_by_default(self):
        process = self.BuyConfirmationProcess()
        process.data_provider = type(
            "NoFundamentalProvider",
            (),
            {"get_fundamental_data": lambda self, symbol: {}},
        )()
        process.news_fetcher = type(
            "NoNewsFetcher",
            (),
            {"fetch_stock_news": lambda self, symbol, stock_name: []},
        )()
        process.agent = type(
            "ReviewAgent",
            (),
            {"review": lambda self, context: {
                "symbol": context["symbol"],
                "final_action": BUY_ACTION,
                "confidence": 0.7,
                "fundamental_view": "unknown",
                "sentiment_view": "unknown",
                "risk_flags": [],
                "reason": "外部数据缺失，但原始技术信号仍可复核。",
                "data_quality": context["data_quality"],
                "agent_parse_status": "success",
            }},
        )()
        results = [{"股票代码": "000001.SZ", "股票名称": "平安银行", "操作建议": BUY_ACTION}]

        outcome = process.execute(results)

        self.assertEqual(outcome["processed_count"], 1)
        self.assertEqual(results[0]["操作建议"], BUY_ACTION)
        self.assertEqual(results[0]["Agent解析状态"], "success")

    def test_execute_keeps_original_when_collector_initialization_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            process = self.BuyConfirmationProcess(
                output_dir=Path(temp_dir),
            )
            process._ensure_collectors = lambda: (_ for _ in ()).throw(
                ModuleNotFoundError("No module named 'pandas'")
            )
            results = [
                {
                    "股票代码": "000001.SZ",
                    "股票名称": "PingAn",
                    "操作建议": BUY_ACTION,
                }
            ]

            outcome = process.execute(results)
            audit_path = Path(temp_dir) / "agent_review_results.json"

            self.assertEqual(outcome["processed_count"], 1)
            self.assertEqual(results[0]["操作建议"], BUY_ACTION)
            self.assertNotIn("Agent解析状态", results[0])
            self.assertTrue(audit_path.exists())

            reviews = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertFalse(reviews[0]["data_quality"]["fundamental_data_available"])
            self.assertFalse(reviews[0]["data_quality"]["sentiment_data_available"])

    def test_build_context_records_external_data_failure_reasons(self):
        process = self.BuyConfirmationProcess()
        process.data_provider = type(
            "NoFundamentalProvider",
            (),
            {"get_fundamental_data": lambda self, symbol: {}},
        )()
        process.news_fetcher = type(
            "NoNewsFetcher",
            (),
            {"fetch_stock_news": lambda self, symbol, stock_name: []},
        )()

        context = process._build_context({"股票代码": "000001.SZ", "股票名称": "平安银行", "操作建议": BUY_ACTION})

        quality = context["data_quality"]
        self.assertFalse(quality["fundamental_data_available"])
        self.assertFalse(quality["sentiment_data_available"])
        self.assertEqual(quality["sources"]["fundamental"]["failure_reason"], "未获取到可用基本面数据")
        self.assertEqual(quality["sources"]["sentiment"]["failure_reason"], "未获取到可用新闻/情绪数据")

    def test_review_candidates_falls_back_when_future_raises(self):
        process = self.BuyConfirmationProcess()

        def raise_error(candidate):
            raise RuntimeError("boom")

        process._review_one = raise_error
        reviews = process._review_candidates(
            [
                {"股票代码": "000001.SZ", "股票名称": "平安银行", "操作建议": BUY_ACTION},
                {"股票代码": "000002.SZ", "股票名称": "万科A", "操作建议": HOLD_ACTION},
            ]
        )

        self.assertEqual(len(reviews), 2)
        self.assertEqual({review["agent_parse_status"] for review in reviews}, {"failed"})
        self.assertTrue(all(review["final_action"] == HOLD_ACTION for review in reviews))

    def test_confirmation_settings_are_internal_defaults(self):
        process = self.BuyConfirmationProcess()

        self.assertEqual(process.settings["candidate_actions"], [BUY_ACTION, HOLD_ACTION])
        self.assertEqual(process.settings["allowed_final_actions"], [BUY_ACTION, HOLD_ACTION, SELL_ACTION])
        self.assertEqual(process.settings["max_workers"], 2)
        self.assertEqual(process.settings["max_news"], 6)


if __name__ == "__main__":
    unittest.main()
