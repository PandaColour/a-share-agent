import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.factor_registry import FactorRegistryManager


class FactorRegistryManagerTest(unittest.TestCase):
    def _registry_path(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return Path(temp_dir.name) / "factor_registry.json"

    def test_load_creates_default_registry_when_missing(self):
        path = self._registry_path()
        manager = FactorRegistryManager(path)

        registry = manager.load()

        self.assertEqual(registry["active_factors"], [])
        self.assertEqual(registry["candidate_factors"], [])
        self.assertEqual(registry["disabled_factors"], [])
        self.assertIn("version", registry)
        self.assertTrue(path.exists())

    def test_move_factor_between_candidate_active_and_disabled(self):
        path = self._registry_path()
        path.write_text(json.dumps({
            "active_factors": [],
            "candidate_factors": ["factor_a"],
            "disabled_factors": [],
            "version": "2026-07-08"
        }), encoding="utf-8")
        manager = FactorRegistryManager(path)

        manager.move_factor("factor_a", "active_factors")
        registry = manager.load()
        self.assertEqual(registry["active_factors"], ["factor_a"])
        self.assertEqual(registry["candidate_factors"], [])

        manager.move_factor("factor_a", "disabled_factors")
        registry = manager.load()
        self.assertEqual(registry["disabled_factors"], ["factor_a"])
        self.assertEqual(registry["active_factors"], [])

    def test_save_deduplicates_factor_lists(self):
        path = self._registry_path()
        manager = FactorRegistryManager(path)

        manager.save({
            "active_factors": ["factor_a", "factor_a"],
            "candidate_factors": ["factor_a", "factor_b", "factor_b"],
            "disabled_factors": ["factor_c", "factor_c"],
            "version": "2026-07-08"
        })

        registry = manager.load()
        self.assertEqual(registry["active_factors"], ["factor_a"])
        self.assertEqual(registry["candidate_factors"], ["factor_b"])
        self.assertEqual(registry["disabled_factors"], ["factor_c"])


if __name__ == "__main__":
    unittest.main()
