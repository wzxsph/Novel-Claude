import tempfile
import unittest
import json
from pathlib import Path

from core.event_bus import event_bus
from core.novel_context import NovelContext
from core.plugin_manager import PluginManager
from skills.ext_gold_finger.skill import GoldFingerSkill
from utils.workspace import WorkspaceManager


GOOD_SKILL = """
from core.base_skill import BaseSkill
class GoodSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = 'GoodSkill'
"""

BAD_SKILL = """
from core.base_skill import BaseSkill
from core.event_bus import event_bus
class BadSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = 'BadSkill'
    def on_init(self):
        event_bus.register(self)
        raise RuntimeError('broken init')
"""


class PluginManagerTests(unittest.TestCase):
    def tearDown(self):
        event_bus.clear()

    def test_failed_init_rolls_back_and_scan_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skills = root / "skills"
            for name, source in (("good", GOOD_SKILL), ("bad", BAD_SKILL)):
                folder = skills / name
                folder.mkdir(parents=True)
                (folder / "skill.py").write_text(source, encoding="utf-8")

            context = NovelContext(WorkspaceManager(root / "workspace"))
            manager = PluginManager(context, skills)
            manager.scan_and_load()
            manager.scan_and_load()
            self.assertTrue(manager.hot_reload("good"))

            self.assertEqual(set(context.active_skills), {"good"})
            self.assertEqual(len(event_bus.subscribers), 1)
            self.assertNotIn("bad", manager.loaded_modules)

    def test_gold_finger_migrates_legacy_nested_workspace_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / ".novel_demo"
            legacy = workspace / ".novel" / "skills_data" / "gold_finger.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(json.dumps({"money": 9}), encoding="utf-8")
            context = NovelContext(WorkspaceManager(workspace))

            skill = GoldFingerSkill(context)
            skill.on_init()

            preferred = workspace / "skills_data" / "gold_finger.json"
            self.assertEqual(skill.state_path, preferred)
            self.assertEqual(json.loads(preferred.read_text(encoding="utf-8")), {"money": 9})

    def test_failed_hot_reload_preserves_last_working_skill(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = root / "skills" / "good"
            skill_dir.mkdir(parents=True)
            skill_file = skill_dir / "skill.py"
            skill_file.write_text(GOOD_SKILL, encoding="utf-8")

            context = NovelContext(WorkspaceManager(root / "workspace"))
            manager = PluginManager(context, root / "skills")
            manager.scan_and_load()
            working_skill = context.active_skills["good"]

            skill_file.write_text("def broken(:\n", encoding="utf-8")
            self.assertFalse(manager.hot_reload("good"))
            self.assertIs(context.active_skills["good"], working_skill)
            self.assertEqual(event_bus.subscribers, [working_skill])

    def test_plugin_with_multiple_skill_classes_is_rejected(self):
        source = """
from core.base_skill import BaseSkill
class FirstSkill(BaseSkill):
    pass
class SecondSkill(BaseSkill):
    pass
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = root / "skills" / "ambiguous"
            skill_dir.mkdir(parents=True)
            (skill_dir / "skill.py").write_text(source, encoding="utf-8")
            context = NovelContext(WorkspaceManager(root / "workspace"))
            manager = PluginManager(context, root / "skills")

            manager.scan_and_load()

            self.assertNotIn("ambiguous", context.active_skills)
            self.assertEqual(event_bus.subscribers, [])


if __name__ == "__main__":
    unittest.main()
