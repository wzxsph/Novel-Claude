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
                skill.on_after_scene_write(
                    {"volume_id": 3, "chapter_id": 7}, "content"
                )
            self.assertEqual(register.call_args.args[1:], (3, 7, "content"))

            skill.collection = MagicMock()
            skill.collection.get.return_value = {
                "ids": ["v03_ch007_chunk_0", "v03_ch007_chunk_1"]
            }
            skill.chunk_text = MagicMock(return_value=["chunk"])
            skill._extract_entities_fast = MagicMock(return_value=[])
            skill._background_update_task(3, 7, "content")
            skill.collection.upsert.assert_called_once()
            upsert = skill.collection.upsert.call_args.kwargs
            self.assertEqual(upsert["ids"], ["v03_ch007_chunk_0"])
            self.assertEqual(upsert["metadatas"][0]["volume_id"], 3)
            skill.collection.delete.assert_called_once_with(
                ids=["v03_ch007_chunk_1"]
            )

    def test_workspace_manager_rejects_paths_outside_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = WorkspaceManager(root / "workspace")
            with self.assertRaisesRegex(ValueError, "超出当前工作区"):
                workspace.safe_write_text("../outside.txt", "no")
            with self.assertRaisesRegex(ValueError, "超出当前工作区"):
                workspace.safe_read_json(root / "outside.json")
            self.assertFalse((root / "outside.txt").exists())

    def test_context_dsl_reads_current_blueprint_card_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Path(temp_dir) / "settings"
            settings.mkdir()
            (settings / "core_blueprint.json").write_text(
                json.dumps(
                    {
                        "character_cards": [{"name": "林舟"}],
                        "scene_cards": [{"name": "云港"}],
                        "organization_cards": [{"name": "观星阁"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            assembler = context_assembler.ContextAssembler(temp_dir)
            result = assembler.assemble(
                "@type:角色卡\n@type:场景卡\n@type:组织卡"
            )
            self.assertIn("林舟", result)
            self.assertIn("云港", result)
            self.assertIn("观星阁", result)

    def test_rag_entity_automaton_reads_current_core_blueprint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Path(temp_dir)
            (settings / "core_blueprint.json").write_text(
                json.dumps(
                    {
                        "content": {
                            "character_cards": [{"name": "林舟"}],
                            "scene_cards": [{"name": "云港"}],
                            "organization_cards": [{"name": "观星阁"}],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            context = NovelContext(WorkspaceManager(settings / "workspace"))
            skill = CoreMemoryRagSkill(context)
            with patch.object(config, "SETTINGS_DIR", str(settings)):
                skill.automaton = skill._build_entity_automaton()
            self.assertEqual(
                set(skill._extract_entities_fast("林舟抵达云港，拜访观星阁。")),
                {"林舟", "云港", "观星阁"},
            )

    def test_missing_embedding_key_does_not_create_chroma_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context = NovelContext(WorkspaceManager(Path(temp_dir) / "workspace"))
            skill = CoreMemoryRagSkill(context)
            with (
                patch.object(config, "ZHIPU_API_KEY", None),
                patch("skills.core_memory_rag.skill.chromadb.PersistentClient") as client,
                self.assertRaisesRegex(RuntimeError, "ZHIPU_API_KEY"),
            ):
                skill.on_init()
            client.assert_not_called()

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
