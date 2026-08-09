import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import volume_planner
from utils import config


class VolumePlannerTests(unittest.TestCase):
    def test_volume_planning_hook_receives_and_returns_an_object(self):
        generated = {
            "volumes": [
                {
                    "volume_id": 1,
                    "volume_name": "before",
                }
            ]
        }

        def transform(event_name, payload):
            self.assertEqual(event_name, "on_volume_planning")
            self.assertIsInstance(payload, dict)
            payload["volumes"][0]["volume_name"] = "after"
            return payload

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(config, "VOLUMES_DIR", temp_dir),
                patch("volume_planner.generate_json", return_value=generated),
                patch("volume_planner.get_core_blueprint", return_value={}),
                patch("volume_planner.get_world_context", return_value=""),
                patch("volume_planner.event_bus_emit_pipeline", side_effect=transform),
            ):
                volume_planner.plan_macro_outlines(total_volumes=1)

            saved = json.loads(
                (Path(temp_dir) / "vol_01_outline.json").read_text(encoding="utf-8")
            )
        self.assertEqual(saved["volume_name"], "after")


if __name__ == "__main__":
    unittest.main()
