import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cli.permissions import PermissionLevel, PermissionManager
from utils import config


class PermissionTests(unittest.TestCase):
    def test_permission_state_and_workspace_checks_use_project_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / ".novel_demo"
            workspace.mkdir()
            with (
                patch.object(config, "PROJECT_ROOT", root),
                patch.object(config, "NOVEL_DIR", str(workspace)),
            ):
                manager = PermissionManager()
                manager.set_level(PermissionLevel.WRITE)

                self.assertEqual(
                    manager.config_file,
                    root / ".novel_cli_config" / "permissions.json",
                )
                self.assertTrue(manager.can_write(workspace / "settings" / "x.json"))
                self.assertFalse(manager.can_write(root / ".novel_demo_escape" / "x"))
                self.assertFalse(manager.can_write(root / "README.md"))


if __name__ == "__main__":
    unittest.main()
