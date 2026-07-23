import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class ClaudeSDKCleanupTest(unittest.TestCase):
    def test_claude_sdk_dependency_and_code_are_removed(self):
        self.assertFalse((PROJECT_ROOT / "src" / "ai_models" / "claude_sdk_client.py").exists())
        self.assertNotIn(
            "claude-agent-sdk",
            (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8"),
        )
        factory_source = (PROJECT_ROOT / "src" / "ai_models" / "factory.py").read_text(encoding="utf-8")
        self.assertNotIn("ClaudeSDKClient", factory_source)
        self.assertNotIn("claude_sdk", factory_source)

        example_config = (PROJECT_ROOT / "config" / "unified_config.json.example").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("claude_sonnet", example_config)
        self.assertNotIn("claude_sdk", example_config)


if __name__ == "__main__":
    unittest.main()
