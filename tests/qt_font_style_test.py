import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QtFontStyleTest(unittest.TestCase):
    def test_runtime_qt_styles_do_not_reference_missing_consolas_font(self):
        qt_files = [
            PROJECT_ROOT / "src" / "qt" / "analysis_widget.py",
            PROJECT_ROOT / "src" / "qt" / "backtest_widget.py",
            PROJECT_ROOT / "src" / "qt" / "media_widget.py",
            PROJECT_ROOT / "src" / "qt" / "research_mode_widget.py",
        ]

        for qt_file in qt_files:
            source = qt_file.read_text(encoding="utf-8")
            self.assertNotIn("Consolas", source, str(qt_file))

    def test_win_main_configures_real_application_font(self):
        source = (PROJECT_ROOT / "win_main.py").read_text(encoding="utf-8")

        self.assertIn("configure_application_font(app)", source)
        self.assertIn("QFontDatabase.families()", source)
        self.assertNotIn('QFont("Sans Serif"', source)


if __name__ == "__main__":
    unittest.main()
