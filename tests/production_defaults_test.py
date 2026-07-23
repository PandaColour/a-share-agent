import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.config_manager import ConfigManager


def load_a_share_data_provider_class():
    if "pandas" not in sys.modules:
        pandas_stub = types.ModuleType("pandas")
        pandas_stub.DataFrame = type("DataFrame", (), {})
        sys.modules["pandas"] = pandas_stub

    if "numpy" not in sys.modules:
        sys.modules["numpy"] = types.ModuleType("numpy")

    module_path = PROJECT_ROOT / "src" / "data" / "data_provider.py"
    spec = importlib.util.spec_from_file_location("data_provider_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AShareDataProvider


class ProductionDefaultsTest(unittest.TestCase):
    def _write_config(self, data):
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name) / "unified_config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.addCleanup(temp_dir.cleanup)
        return path

    def test_factor_auto_generation_is_disabled_by_default(self):
        config_path = self._write_config({"system_settings": {}})
        config = ConfigManager(str(config_path))

        self.assertFalse(config.is_factor_auto_generation_enabled())

    def test_factor_auto_generation_can_be_enabled_for_research(self):
        config_path = self._write_config({
            "system_settings": {
                "factor_system": {
                    "mode": "research",
                    "auto_generation_enabled": True
                }
            }
        })
        config = ConfigManager(str(config_path))

        self.assertTrue(config.is_factor_auto_generation_enabled())

    def test_intraday_data_is_disabled_by_default(self):
        config_path = self._write_config({"system_settings": {}})
        config = ConfigManager(str(config_path))

        self.assertFalse(config.get_include_intraday())

    def test_data_provider_passes_intraday_flag_to_multi_provider(self):
        AShareDataProvider = load_a_share_data_provider_class()
        calls = []

        class FakeMultiProvider:
            def get_complete_stock_data(self, symbol, start_date, end_date, period, include_intraday):
                calls.append(include_intraday)
                return None, {}, {}, {}, None, {}

        provider = AShareDataProvider.__new__(AShareDataProvider)
        provider._multi_provider = FakeMultiProvider()

        provider.get_stock_data("000001.SZ", include_intraday=False)
        provider.get_stock_data("000001.SZ", include_intraday=True)

        self.assertEqual(calls, [False, True])


if __name__ == "__main__":
    unittest.main()
