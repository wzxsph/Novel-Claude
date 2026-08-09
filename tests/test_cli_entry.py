import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from cli.commands import novel_commands


def _load_cli_entry():
    path = Path(__file__).resolve().parents[1] / "cli.py"
    spec = importlib.util.spec_from_file_location("novel_cli_entry_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CliEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entry = _load_cli_entry()

    def test_subcommand_help_does_not_initialize_plugins(self):
        with patch.object(self.entry, "_ensure_runtime") as ensure_runtime:
            result = CliRunner().invoke(self.entry.cli, ["plan", "--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Usage:", result.output)
        ensure_runtime.assert_not_called()

    def test_executing_hooked_command_initializes_runtime_once(self):
        with (
            patch.object(self.entry, "_ensure_runtime") as ensure_runtime,
            patch.object(
                novel_commands, "plan", return_value={"message": "planned"}
            ) as plan,
            patch.object(self.entry, "_wait_for_tasks"),
        ):
            result = CliRunner().invoke(self.entry.cli, ["plan", "1"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("planned", result.output)
        ensure_runtime.assert_called_once_with()
        plan.assert_called_once_with(["1"])


if __name__ == "__main__":
    unittest.main()
