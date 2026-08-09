import json
import tempfile
import unittest
from pathlib import Path

from utils import config_loader


class ConfigLoaderTests(unittest.TestCase):
    def tearDown(self):
        config_loader._config_cache.clear()

    def test_cache_is_scoped_to_the_requested_config_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.json"
            second = Path(temp_dir) / "second.json"
            first.write_text(json.dumps({"name": "first"}), encoding="utf-8")
            second.write_text(json.dumps({"name": "second"}), encoding="utf-8")

            self.assertEqual(config_loader.load_config(str(first))["name"], "first")
            self.assertEqual(config_loader.load_config(str(second))["name"], "second")

    def test_non_object_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON object"):
                config_loader.load_config(str(path))


if __name__ == "__main__":
    unittest.main()
