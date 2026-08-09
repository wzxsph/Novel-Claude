import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prompt_toolkit.document import Document

from cli.completer import NovelClaudeCompleter
from cli.project_manager import project_manager


class CompleterTests(unittest.TestCase):
    def _complete(self, completer, text):
        document = Document(text, cursor_position=len(text))
        return list(completer.get_completions(document, None))

    def test_multiword_command_completion_uses_the_full_prefix(self):
        completions = self._complete(NovelClaudeCompleter(), "projects sw")
        completed = {
            "projects sw"[: len("projects sw") + item.start_position] + item.text
            for item in completions
        }
        self.assertIn("projects switch", completed)

    def test_project_name_completion_replaces_only_the_argument(self):
        with patch.object(project_manager, "list_projects", return_value=["alpha", "beta"]):
            completions = self._complete(
                NovelClaudeCompleter(), "projects switch al"
            )
        self.assertEqual(len(completions), 1)
        self.assertEqual(completions[0].text, "alpha")
        self.assertEqual(completions[0].start_position, -2)

    def test_path_completion_is_relative_to_repl_current_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "draft.md").write_text("draft", encoding="utf-8")
            with patch.object(project_manager, "current_path", root):
                completions = self._complete(NovelClaudeCompleter(), "cat dra")
        self.assertEqual([item.text for item in completions], ["ft.md"])


if __name__ == "__main__":
    unittest.main()
