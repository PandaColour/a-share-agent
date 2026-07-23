import sys
import tempfile
import types
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if "pandas" not in sys.modules:
    pandas_stub = types.ModuleType("pandas")
    sys.modules["pandas"] = pandas_stub

from src.content.xiaohongshu_generator import XiaohongshuContentGenerator


class XiaohongshuAgentTest(unittest.TestCase):
    def test_generate_content_uses_codex_agent_in_output_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            created_agents = []
            sent_messages = []

            class FakeDataFrame:
                empty = False

            class FakeAgent:
                def __init__(self, **kwargs):
                    created_agents.append(kwargs)

                def send_message(self, message):
                    sent_messages.append(message)
                    return "生成的文案"

            generator = XiaohongshuContentGenerator(agent_factory=FakeAgent)
            generator._load_holdings_data = lambda *_args: None
            generator._load_analysis_data = lambda *_args: FakeDataFrame()
            generator._prepare_holdings_data = lambda *_args: []
            generator._prepare_buy_recommendations = lambda *_args: [
                {"symbol": "000001.SZ", "name": "平安银行", "confidence": "80%", "reason": "趋势向上"}
            ]
            generator._prepare_sell_warnings = lambda *_args: []
            generator._extract_recent_buys_from_backtest = lambda *_args, **_kwargs: []
            generator._build_ai_input = lambda *_args: "请为 000001.SZ 生成小红书文案"

            content = generator.generate_content(str(output_dir))

            self.assertEqual(content, "生成的文案")
            self.assertEqual(created_agents[0]["agent_type"], "codex")
            self.assertEqual(created_agents[0]["work_dir"], str(output_dir))
            self.assertIn("000001.SZ", sent_messages[0])
            self.assertEqual(
                (output_dir / "xiaohongshu_content.md").read_text(encoding="utf-8"),
                "生成的文案",
            )
            self.assertEqual(
                (output_dir / "xiaohongshu_content.txt").read_text(encoding="utf-8"),
                "生成的文案",
            )

    def test_save_content_keeps_markdown_file_and_creates_plain_text_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            generator = XiaohongshuContentGenerator()
            markdown_content = (
                "# 标题\n\n"
                "## 持仓\n\n"
                "- 当前收益率：**-33.83%**\n"
                "- 参考来源：[证券时报](https://www.stcn.com/example)\n"
            )

            generator._save_content(temp_dir, markdown_content)

            markdown_file = Path(temp_dir) / "xiaohongshu_content.md"
            text_file = Path(temp_dir) / "xiaohongshu_content.txt"

            self.assertEqual(markdown_file.read_text(encoding="utf-8"), markdown_content)
            plain_text = text_file.read_text(encoding="utf-8")
            self.assertIn("标题", plain_text)
            self.assertIn("当前收益率：-33.83%", plain_text)
            self.assertIn("参考来源：证券时报", plain_text)
            self.assertNotIn("#", plain_text)
            self.assertNotRegex(plain_text, r"(?m)^- ")
            self.assertNotIn("**", plain_text)
            self.assertNotIn("https://", plain_text)


if __name__ == "__main__":
    unittest.main()
