import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils import config
from utils.chapter_state import ChapterStateManager, STATE_COMPLETED, STATE_PENDING


class ChapterStateTests(unittest.TestCase):
    def test_corrupt_state_file_falls_back_to_empty_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "vol_01_chapter_states.json"
            state_file.write_text("{broken", encoding="utf-8")
            with patch.object(config, "VOLUMES_DIR", temp_dir):
                manager = ChapterStateManager(1)

        self.assertEqual(manager.chapters, {})

    def test_invalid_rows_are_skipped_and_writes_are_atomic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "vol_01_chapter_states.json"
            state_file.write_text(
                json.dumps(
                    {
                        "chapters": [
                            {
                                "volume_id": 1,
                                "chapter_id": 1,
                                "state": STATE_COMPLETED,
                                "generated_chars": 100,
                            },
                            {"volume_id": "bad", "chapter_id": 2},
                            {
                                "volume_id": 1,
                                "chapter_id": 3,
                                "state": "unknown",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(config, "VOLUMES_DIR", temp_dir):
                manager = ChapterStateManager(1)
                manager.mark_completed(3)

            self.assertEqual(manager.chapters[1].state, STATE_COMPLETED)
            self.assertEqual(manager.chapters[3].state, STATE_COMPLETED)
            self.assertEqual(
                json.loads(state_file.read_text(encoding="utf-8"))["chapters"][0][
                    "state"
                ],
                STATE_COMPLETED,
            )
            self.assertFalse(state_file.with_suffix(".json.tmp").exists())

    def test_unknown_saved_state_becomes_pending(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "vol_01_chapter_states.json"
            state_file.write_text(
                json.dumps(
                    {
                        "chapters": [
                            {"volume_id": 1, "chapter_id": 1, "state": "unknown"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(config, "VOLUMES_DIR", temp_dir):
                manager = ChapterStateManager(1)

        self.assertEqual(manager.chapters[1].state, STATE_PENDING)


if __name__ == "__main__":
    unittest.main()
