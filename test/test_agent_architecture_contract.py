# -*- coding: utf-8 -*-

import inspect
import json
import unittest
from pathlib import Path

import src.agents as agents_package
from src.agents.buy_confirmation_agent import BuyConfirmationAgent


ROOT = Path(__file__).resolve().parents[1]


class AgentArchitectureContractTest(unittest.TestCase):
    def test_agents_package_exports_only_cli_agent_facade(self):
        self.assertEqual(agents_package.__all__, ["Agent"])
        self.assertTrue(hasattr(agents_package, "Agent"))
        self.assertFalse(hasattr(agents_package, "BuyConfirmationAgent"))

    def test_buy_confirmation_agent_documents_cli_agent_reuse(self):
        doc = inspect.getdoc(BuyConfirmationAgent) or ""
        source = inspect.getsource(BuyConfirmationAgent)

        self.assertIn("src.agents.Agent", doc)
        self.assertIn("CLI", doc)
        self.assertIn("JSON", doc)
        self.assertIn("降级", doc)
        self.assertIn("from src.agents import Agent", source)
        self.assertNotIn("AIModelFactory", source)
        self.assertNotIn("create_model", source)

    def test_buy_confirmation_process_uses_cli_agent_type_scope(self):
        source = (ROOT / "src" / "process" / "buy_confirmation_process.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('agent_type="codex"', source)
        self.assertIn("BuyConfirmationAgent(", source)
        self.assertIn("基于公共 CLI Agent 门面", source)
        self.assertNotIn("AIModelFactory", source)
        self.assertNotIn("system_settings.ai_models.models", source)

    def test_prompt_lives_in_config_and_example_config_has_no_confirmation_toggle(self):
        config_path = ROOT / "config" / "unified_config.json.example"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        prompt = (ROOT / "config" / "buy_confirmation_prompt.md").read_text(encoding="utf-8")

        self.assertNotIn("buy_confirmation", config["system_settings"]["ai_models"]["models"])
        self.assertNotIn("buy_confirmation_agent", config["analysis_settings"])
        self.assertIn("{context_json}", prompt)
        self.assertIn("{schema_json}", prompt)

    def test_review_checklist_requires_agent_reuse_conclusion(self):
        agents_doc = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("### Agent Architecture", agents_doc)
        self.assertIn("reuse `src.agents.Agent`", agents_doc)
        self.assertIn("reuse `AIModelInterface`", agents_doc)
        self.assertIn("Review records must include a conclusion", agents_doc)


if __name__ == "__main__":
    unittest.main()
