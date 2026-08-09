import tempfile
import unittest
from unittest.mock import patch

import world_builder
from utils import config


class WorldBuilderStageTests(unittest.TestCase):
    def test_rerun_stages_require_their_input_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(config, "SETTINGS_DIR", temp_dir),
                patch("world_builder.generate_json") as generate,
            ):
                self.assertFalse(world_builder.run_expand())
                self.assertFalse(world_builder.run_world())
                self.assertFalse(world_builder.run_blueprint())

        generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
