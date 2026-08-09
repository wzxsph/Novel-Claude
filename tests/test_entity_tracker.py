import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import entity_tracker
from utils import config


class EntityTrackerTests(unittest.TestCase):
    def test_cards_without_names_do_not_break_keyword_matching(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = root / "settings"
            settings.mkdir()
            (settings / "core_blueprint.json").write_text(
                json.dumps(
                    {
                        "character_cards": [{"description": "missing"}, {"name": "林舟"}],
                        "scene_cards": [{}],
                        "organization_cards": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            chapter = root / "chapter.md"
            chapter.write_text("林舟启程。", encoding="utf-8")
            with patch.object(config, "SETTINGS_DIR", str(settings)):
                mentioned = entity_tracker.extract_chapter_entities(chapter)

        self.assertEqual(mentioned["characters"], ["林舟"])
        self.assertEqual(mentioned["scenes"], [])

    def test_dynamic_history_label_includes_volume_and_chapter(self):
        states = {
            "characters": {"林舟": {"dynamic_state": "", "dynamic_info": ""}},
            "scenes": {},
            "organizations": {},
        }
        changes = {
            "character_changes": [
                {"entity_name": "林舟", "description": "负伤", "after_state": "轻伤"}
            ]
        }
        with (
            patch("core.entity_tracker.load_current_entity_states", return_value=states),
            patch("core.entity_tracker.save_entity_states") as save,
        ):
            entity_tracker.apply_entity_changes(2, 3, changes)

        saved_states = save.call_args.args[0]
        self.assertEqual(
            saved_states["characters"]["林舟"]["dynamic_info"],
            "[第2卷第3章] 负伤",
        )


if __name__ == "__main__":
    unittest.main()
