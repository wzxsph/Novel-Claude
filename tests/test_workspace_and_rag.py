import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core import context_assembler
from core.novel_context import NovelContext
from scene_writer import generate_batch_jsonl
from skills.core_memory_rag.skill import CoreMemoryRagSkill
from utils import config
from utils.workspace import WorkspaceManager


class WorkspaceAndRagTests(unittest.TestCase):
    def tearDown(self):
        context_assembler.reset_assembler()

    def test_context_assembler_cache_changes_with_workspace(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with patch.object(config, "NOVEL_DIR", first):
                assembler_one = context_assembler.get_assembler()
            with patch.object(config, "NOVEL_DIR", second):
                assembler_two = context_assembler.get_assembler()
            self.assertIsNot(assembler_one, assembler_two)

    def test_rag_uses_event_chapter_id_and_upsert(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context = NovelContext(WorkspaceManager(temp_dir))
            skill = CoreMemoryRagSkill(context)
            with patch.object(config, "register_background_task") as register:
                skill.on_after_scene_write({"chapter_id": 7}, "content")
            self.assertEqual(register.call_args.args[1:], (7, "content"))

            skill.collection = MagicMock()
            skill.chunk_text = MagicMock(return_value=["chunk"])
            skill._extract_entities_fast = MagicMock(return_value=[])
            skill._background_update_task(7, "content")
            skill.collection.upsert.assert_called_once()

    def test_batch_jsonl_uses_configured_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            volumes = root / "volumes"
            settings = root / "settings"
            chapters = volumes / "vol_01_chapters"
            chapters.mkdir(parents=True)
            settings.mkdir()
            (chapters / "ch_001_outline.json").write_text(
                json.dumps({"title": "T", "overview": "O", "entity_list": []}),
                encoding="utf-8",
            )
            output = root / "batch" / "request.jsonl"
            with (
                patch.object(config, "VOLUMES_DIR", str(volumes)),
                patch.object(config, "SETTINGS_DIR", str(settings)),
                patch.object(config, "BATCH_MODEL_ID", "glm-test"),
            ):
                request_count = generate_batch_jsonl(1, 1, 1, str(output))
            self.assertEqual(request_count, 1)
            body = json.loads(output.read_text(encoding="utf-8").strip())["body"]
            self.assertEqual(body["model"], "glm-test")


if __name__ == "__main__":
    unittest.main()
