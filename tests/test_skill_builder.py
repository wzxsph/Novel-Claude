import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
