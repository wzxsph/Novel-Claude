import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cli.commands import file_commands


class FileCommandTests(unittest.TestCase):
    def test_absolute_paths_cannot_escape_the_active_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / ".novel_demo"
            workspace.mkdir()
            inside = workspace / "inside.txt"
            outside = root / "outside.txt"
            inside.write_text("inside", encoding="utf-8")
            outside.write_text("outside", encoding="utf-8")

            with (
                patch.object(file_commands.project_manager, "current_path", workspace),
                patch.object(
                    file_commands.project_manager,
                    "get_project_dir",
                    return_value=workspace,
                ),
            ):
                self.assertEqual(file_commands.cat([str(inside)])["output"], "inside")
                result = file_commands.cat([str(outside)])

            self.assertIn("inside the active novel workspace", result["error"])


if __name__ == "__main__":
    unittest.main()
