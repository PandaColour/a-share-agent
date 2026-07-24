import sys
import tempfile
import types
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import pandas as pd
except ImportError:
    pd = None

if pd is None and "pandas" not in sys.modules:
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

    def test_plain_text_copy_removes_inline_markdown_bullets_and_bold(self):
        generator = XiaohongshuContentGenerator()
        markdown_content = (
            "- 当前收益率：**-3.71%**  - 模型策略：AI建议 **持有(冷)**，"
            "信心度 **31.64%**，主要问题是高波动率达到52.4%。"
        )

        plain_text = generator._convert_markdown_to_plain_text(markdown_content)

        self.assertIn("当前收益率：-3.71%", plain_text)
        self.assertIn("模型策略：AI建议 持有(冷)，信心度 31.64%", plain_text)
        self.assertNotIn("**", plain_text)
        self.assertNotIn("  - 模型策略", plain_text)
        self.assertNotRegex(plain_text, r"(?m)^- ")

    def test_prompt_disallows_markdown_bold_and_dash_bullets_for_wechat(self):
        prompt = (PROJECT_ROOT / "config" / "xiaohongshu_prompt.md").read_text(encoding="utf-8")

        self.assertIn("不要使用 Markdown 加粗语法", prompt)
        self.assertIn("不要使用以 `-`、`*`、`+` 开头的项目符号", prompt)
        self.assertNotIn("可以使用 `**加粗**`", prompt)

    @unittest.skipIf(pd is None, "pandas is required for holdings data preparation")
    def test_prepare_holdings_data_keeps_watch_status_and_observation_action(self):
        generator = XiaohongshuContentGenerator()
        holdings_df = pd.DataFrame([
            {
                "股票代码": "000002.SZ",
                "股票名称": "万科A",
                "持仓天数": 3,
                "持仓收益率": "+2.10%",
                "操作建议": "确认可以买入-观察达标",
                "系统建议": "确认可以买入(85%)",
                "建议理由": "观察期收盘价高于观察点",
                "持仓状态": "watch",
                "观察状态": "确认可以买入",
            }
        ])
        analysis_df = pd.DataFrame([
            {
                "股票代码": "000002.SZ",
                "操作建议": "买入",
                "信心度": "90%",
                "决策理由": "普通策略输出买入信号",
            }
        ])

        holdings = generator._prepare_holdings_data(holdings_df, analysis_df)

        self.assertEqual(holdings[0]["position_status"], "watch")
        self.assertEqual(holdings[0]["holding_status"], "watch")
        self.assertEqual(holdings[0]["observation_status"], "确认可以买入")
        self.assertEqual(holdings[0]["analysis_action"], "确认可以买入-观察达标")
        self.assertEqual(holdings[0]["reason"], "观察期收盘价高于观察点")

    def test_template_describes_watch_stock_as_observation_instead_of_holding(self):
        generator = XiaohongshuContentGenerator()
        content = generator._generate_with_template(
            [
                {
                    "symbol": "000002.SZ",
                    "name": "万科A",
                    "holding_days": 3,
                    "profit_rate": "+2.10%",
                    "position_status": "watch",
                    "observation_status": "确认可以买入",
                    "analysis_action": "确认可以买入-观察达标",
                    "confidence": "85%",
                    "reason": "观察期收盘价高于观察点",
                }
            ],
            [],
            [],
        )

        self.assertIn("我的持仓与观察清单", content)
        self.assertIn("观察股", content)
        self.assertIn("观察3天", content)
        self.assertIn("观察状态：确认可以买入", content)
        self.assertNotIn("持有3天", content)


if __name__ == "__main__":
    unittest.main()
