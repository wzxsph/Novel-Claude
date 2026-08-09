import unittest
from unittest.mock import MagicMock, patch

from cli.repl import REPL


class ReplTests(unittest.TestCase):
    def test_exit_waits_for_background_tasks(self):
        repl = REPL.__new__(REPL)
        repl.session = MagicMock()
        repl.session.prompt.return_value = "/exit"
        repl.dispatcher = MagicMock()
        repl.history = MagicMock()

        with (
            patch("cli.repl.project_manager._save_state") as save_state,
            patch("cli.repl.config.wait_for_background_tasks") as wait,
        ):
            repl.run()

        save_state.assert_called_once_with()
        wait.assert_called_once_with()
        repl.dispatcher.dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
