import unittest
from unittest.mock import patch

from cli.commands import settings_commands
from utils import config


class SettingsCommandTests(unittest.TestCase):
    def test_show_reports_presence_without_exposing_keys(self):
        with (
            patch.object(config, "LLM_API_KEY", "chat-super-secret"),
            patch.object(config, "ZHIPU_API_KEY", "zhipu-super-secret"),
        ):
            message = settings_commands.show([])["message"]

        self.assertIn("CHAT_KEY_CONFIGURED: yes", message)
        self.assertIn("ZHIPU_KEY_CONFIGURED: yes", message)
        self.assertNotIn("chat-super-secret", message)
        self.assertNotIn("zhipu-super-secret", message)

    def test_setting_a_secret_masks_the_echo(self):
        with patch("cli.commands.settings_commands.set_key") as set_key:
            result = settings_commands.set_value(
                ["LLM_API_KEY", "chat-super-secret"]
            )

        set_key.assert_called_once_with(
            str(config.ENV_FILE), "LLM_API_KEY", "chat-super-secret"
        )
        self.assertNotIn("chat-super-secret", result["message"])
        self.assertIn("<updated>", result["message"])


if __name__ == "__main__":
    unittest.main()
