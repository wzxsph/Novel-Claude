import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cli import project_manager as project_manager_module
from utils import config


class ProjectManagerTests(unittest.TestCase):
    def test_create_and_switch_use_root_level_workspaces(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / ".novel_cli_config"
            state_file = state_dir / "state.json"
            with (
                patch.object(project_manager_module, "PROJECT_ROOT", root),
                patch.object(project_manager_module, "CONFIG_DIR", state_dir),
                patch.object(project_manager_module, "CONFIG_FILE", state_file),
                patch.object(config, "NOVEL_NAME", ""),
                patch.dict(os.environ, {"NOVEL_NAME": ""}, clear=False),
                patch.object(config, "set_active_novel") as activate,
                patch("core.context_assembler.reset_assembler") as reset_assembler,
                patch("core.runtime.reset_runtime") as reset_runtime,
            ):
                manager = project_manager_module.ProjectManager()
                self.assertTrue(manager.create_project("alpha", "logline words"))
                self.assertEqual(manager.get_project_dir(), root / ".novel_alpha")
                self.assertTrue((root / ".novel_alpha" / "settings").is_dir())
                self.assertTrue(state_file.is_file())
                activate.assert_called_with("alpha", ensure=True)

                beta = root / ".novel_beta"
                beta.mkdir()
                (root / ".novel").mkdir()
                manager.current_volume = 4
                manager.current_chapter = 9
                self.assertTrue(manager.switch_project("beta"))
                self.assertEqual(manager.current_project, "beta")
                self.assertEqual(manager.current_volume, 1)
                self.assertEqual(manager.current_chapter, 1)
                self.assertEqual(manager.list_projects(), ["default", "alpha", "beta"])

                self.assertTrue(manager.switch_project("default"))
                self.assertIsNone(manager.current_project)
                self.assertEqual(manager.get_project_dir(), root / ".novel")
                self.assertEqual(reset_assembler.call_count, 3)
                self.assertEqual(reset_runtime.call_count, 3)

    def test_project_name_rejects_path_traversal(self):
        for invalid in ("../escape", "line\nbreak", "cli_config", "projects"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                project_manager_module._validate_project_name(invalid)

    def test_default_name_is_reserved_for_the_default_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (
                patch.object(project_manager_module, "PROJECT_ROOT", root),
                patch.object(
                    project_manager_module,
                    "CONFIG_DIR",
                    root / ".novel_cli_config",
                ),
                patch.object(
                    project_manager_module,
                    "CONFIG_FILE",
                    root / ".novel_cli_config" / "state.json",
                ),
                patch.object(config, "NOVEL_NAME", ""),
                patch.dict(os.environ, {"NOVEL_NAME": ""}, clear=False),
            ):
                manager = project_manager_module.ProjectManager()
                with self.assertRaises(ValueError):
                    manager.create_project("default")
                with self.assertRaises(ValueError):
                    manager.delete_project("default")

    def test_corrupt_state_values_fall_back_to_safe_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / ".novel_cli_config"
            state_dir.mkdir()
            state_file = state_dir / "state.json"
            state_file.write_text(
                json.dumps(
                    {
                        "current_project": "../escape",
                        "current_volume": "not-a-number",
                        "current_chapter": -4,
                        "current_path": str(root.parent),
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(project_manager_module, "PROJECT_ROOT", root),
                patch.object(project_manager_module, "CONFIG_DIR", state_dir),
                patch.object(project_manager_module, "CONFIG_FILE", state_file),
                patch.object(config, "NOVEL_NAME", ""),
                patch.dict(os.environ, {"NOVEL_NAME": ""}, clear=False),
                patch.object(config, "set_active_novel"),
            ):
                manager = project_manager_module.ProjectManager()

            self.assertIsNone(manager.current_project)
            self.assertEqual(manager.current_volume, 1)
            self.assertEqual(manager.current_chapter, 1)
            self.assertEqual(manager.current_path, root / ".novel")
            with self.assertRaises(ValueError):
                manager.update_context(volume=0)


if __name__ == "__main__":
    unittest.main()
