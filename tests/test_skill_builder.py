import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.agents.skill_builder_agent import SkillBuilderAgent
from utils import config


class SkillBuilderTests(unittest.TestCase):
    def test_generated_skill_directory_cannot_escape_skills_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(config, "PROJECT_ROOT", Path(temp_dir)):
                expected = Path(temp_dir) / "skills" / "ext_demo"
                self.assertEqual(
                    SkillBuilderAgent._resolve_skill_dir("ext_demo"),
                    expected.resolve(),
                )
                for invalid in ("../../escape", "ExtDemo", "bad-name", ""):
                    with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                        SkillBuilderAgent._resolve_skill_dir(invalid)

    def _client_for_generated_skill(self, folder, code):
        arguments = json.dumps(
            {
                "skill_folder_name": folder,
                "python_code": code,
                "readme_content": "# generated",
            }
        )
        message = SimpleNamespace(
            content=None,
            tool_calls=[
                SimpleNamespace(
                    function=SimpleNamespace(
                        name="save_skill_code", arguments=arguments
                    )
                )
            ],
        )
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=message)]
        )
        return client

    def test_invalid_generated_code_is_not_written(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = MagicMock()
            agent = SkillBuilderAgent(MagicMock(), manager)
            client = self._client_for_generated_skill("ext_broken", "def broken(:")
            with (
                patch.object(config, "PROJECT_ROOT", root),
                patch("core.agents.skill_builder_agent.get_client", return_value=client),
            ):
                self.assertFalse(agent.build_skill("broken"))

            self.assertFalse((root / "skills" / "ext_broken").exists())
            manager.hot_reload.assert_not_called()

    def test_failed_generated_skill_reload_restores_previous_files(self):
        valid_code = "from core.base_skill import BaseSkill\nclass Demo(BaseSkill):\n    pass\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = root / "skills" / "ext_demo"
            skill_dir.mkdir(parents=True)
            skill_file = skill_dir / "skill.py"
            skill_file.write_text("# old working code\n", encoding="utf-8")
            manager = MagicMock()
            manager.hot_reload.return_value = False
            agent = SkillBuilderAgent(MagicMock(), manager)
            client = self._client_for_generated_skill("ext_demo", valid_code)
            with (
                patch.object(config, "PROJECT_ROOT", root),
                patch("core.agents.skill_builder_agent.get_client", return_value=client),
            ):
                self.assertFalse(agent.build_skill("replace"))

            self.assertEqual(
                skill_file.read_text(encoding="utf-8"), "# old working code\n"
            )
            self.assertFalse((skill_dir / "README.md").exists())
            self.assertFalse((skill_dir / "__init__.py").exists())


if __name__ == "__main__":
    unittest.main()
