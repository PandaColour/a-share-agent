import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ResearchModeUiTest(unittest.TestCase):
    def test_main_window_registers_research_mode_page(self):
        source = (PROJECT_ROOT / "src" / "qt" / "main_window.py").read_text(encoding="utf-8")

        self.assertIn("from src.qt.research_mode_widget import ResearchModeWidget", source)
        self.assertIn("self.research_widget = ResearchModeWidget()", source)
        self.assertIn("self.stacked_widget.addWidget(self.research_widget)", source)
        self.assertIn("self.research_btn = QPushButton(\"🔬 因子研究\")", source)
        self.assertIn("self.research_btn.clicked.connect(lambda: self.switch_page(5))", source)
        self.assertIn("research_action.setShortcut(\"Ctrl+6\")", source)

    def test_research_mode_page_explains_safe_usage(self):
        widget_path = PROJECT_ROOT / "src" / "qt" / "research_mode_widget.py"
        source = widget_path.read_text(encoding="utf-8")

        self.assertIn("class ResearchFactorThread(SubprocessThread):", source)
        self.assertIn("'--mode', 'research'", source)
        self.assertIn("'--research-generate-factors'", source)
        self.assertIn("self.start_btn = QPushButton(\"启动研究模式\")", source)
        self.assertIn("self.stop_btn = QPushButton(\"停止\")", source)
        self.assertIn("self.research_thread.start()", source)
        self.assertIn("class ResearchModeWidget(QWidget):", source)
        self.assertIn("--research-generate-factors", source)
        self.assertNotIn("生产默认行为", source)
        self.assertNotIn("研究模式用途", source)
        self.assertNotIn("启用方式", source)

    def test_research_mode_page_configures_factor_registry(self):
        widget_path = PROJECT_ROOT / "src" / "qt" / "research_mode_widget.py"
        source = widget_path.read_text(encoding="utf-8")

        self.assertIn("FactorRegistryManager", source)
        self.assertIn("self.candidate_list", source)
        self.assertIn("self.active_list", source)
        self.assertIn("self.disabled_list", source)
        self.assertIn("QPushButton(\"加入生产\")", source)
        self.assertIn("QPushButton(\"移到候选\")", source)
        self.assertIn("QPushButton(\"禁用\")", source)
        self.assertIn("QPushButton(\"保存配置\")", source)
        self.assertIn("QPushButton(\"刷新\")", source)

    def test_main_py_supports_research_mode(self):
        source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")

        self.assertIn("choices=['select', 'hold', 'both', 'backtest', 'research']", source)
        self.assertIn("if args.mode == 'research':", source)


if __name__ == "__main__":
    unittest.main()
