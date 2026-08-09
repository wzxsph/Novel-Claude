import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils import config


class ConfigTests(unittest.TestCase):
    def test_generic_and_legacy_env_precedence(self):
        with patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "generic",
                "MINIMAX_API_KEY": "minimax",
                "ANTHROPIC_API_KEY": "legacy",
            },
            clear=False,
        ):
            self.assertEqual(
                config._first_env("LLM_API_KEY", "MINIMAX_API_KEY", "ANTHROPIC_API_KEY"),
                "generic",
            )

    def test_legacy_minimax_anthropic_url_is_normalized(self):
        self.assertEqual(
            config._normalize_openai_base_url("https://api.minimaxi.com/anthropic/"),
            "https://api.minimaxi.com/v1",
        )
        self.assertEqual(
            config._normalize_openai_base_url("https://gateway.example/v1/"),
            "https://gateway.example/v1",
        )

    def test_zhipu_key_fallback_is_provider_scoped(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                config._resolve_zhipu_api_key("zhipu", "chat-key"), "chat-key"
            )
            self.assertIsNone(
                config._resolve_zhipu_api_key("minimax", "chat-key")
            )
        with patch.dict(os.environ, {"ZHIPU_API_KEY": "dedicated"}, clear=True):
            self.assertEqual(
                config._resolve_zhipu_api_key("zhipu", "chat-key"), "dedicated"
            )

    def test_workspace_priority_env_then_state_then_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_file = root / "state.json"
            config_file = root / "config.json"
            state_file.write_text(json.dumps({"current_project": "state"}), encoding="utf-8")
            config_file.write_text(
                json.dumps({"workspace": {"novel_name": "configured"}}),
                encoding="utf-8",
            )
            with (
                patch.object(config, "CLI_STATE_FILE", state_file),
                patch.object(config, "CONFIG_FILE", config_file),
                patch.dict(os.environ, {"NOVEL_NAME": "explicit"}, clear=False),
            ):
                self.assertEqual(config._resolve_initial_novel_name(), "explicit")
                os.environ["NOVEL_NAME"] = ""
                self.assertEqual(config._resolve_initial_novel_name(), "state")
                state_file.write_text(
                    json.dumps({"current_project": None}), encoding="utf-8"
                )
                self.assertEqual(config._resolve_initial_novel_name(), "")
                state_file.unlink()
                self.assertEqual(config._resolve_initial_novel_name(), "configured")

    def test_set_active_novel_uses_project_root(self):
        original_root = config.PROJECT_ROOT
        original_name = config.NOVEL_NAME
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(config, "PROJECT_ROOT", Path(temp_dir)):
                workspace = config.set_active_novel("demo", ensure=True)
                self.assertEqual(workspace, Path(temp_dir) / ".novel_demo")
                self.assertTrue((workspace / "batch_jobs").is_dir())
        config.PROJECT_ROOT = original_root
        config.set_active_novel(original_name, ensure=False)

    def test_workspace_name_cannot_escape_the_project_root(self):
        for invalid in ("../escape", "line\nbreak", "cli_config", "projects"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                config._normalize_novel_name(invalid)
        self.assertEqual(config._normalize_novel_name("default"), "")


if __name__ == "__main__":
    unittest.main()
