import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cli.commands import novel_commands
from cli.dispatcher import CommandDispatcher


class CommandTests(unittest.TestCase):
    def test_chapter_range_validation(self):
        self.assertEqual(novel_commands.parse_chapter_range("3"), (3, 3))
        self.assertEqual(novel_commands.parse_chapter_range("2-5"), (2, 5))
        for invalid in ("", "0", "5-2", "a-b", "1-2-3"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                novel_commands.parse_chapter_range(invalid)

    def test_repl_batch_subcommand_routes_to_specific_handler(self):
        sentinel = {"message": "routed"}
        with patch.object(novel_commands, "batch_build", return_value=sentinel) as handler:
            dispatcher = CommandDispatcher()
            result = dispatcher.dispatch("batch build --volume 1 --chapters 1-2")
        self.assertEqual(result, sentinel)
        handler.assert_called_once_with(["--volume", "1", "--chapters", "1-2"])

    def test_plan_supports_volume_option(self):
        with (
            patch("volume_planner.run_volume_planner", return_value=True) as planner,
            patch.object(novel_commands.project_manager, "update_context"),
        ):
            result = novel_commands.plan(["--volume", "2"])
        self.assertNotIn("error", result)
        planner.assert_called_once_with(2)

    def test_missing_write_arguments_are_friendly(self):
        result = CommandDispatcher().dispatch("write --volume 1")
        self.assertIn("error", result)
        self.assertNotIn("NoneType", result["error"])

    def test_track_reports_a_missing_manuscript(self):
        with patch.object(novel_commands.config, "MANUSCRIPTS_DIR", "/missing"):
            result = novel_commands.track(["--volume", "1", "--chapter", "2"])
        self.assertIn("找不到章节成稿", result["error"])

    def test_write_reports_generation_failures(self):
        with (
            patch("scene_writer.run_scene_writer", return_value=(1, 2)),
            patch.object(novel_commands.project_manager, "update_context"),
        ):
            result = novel_commands.write(
                ["--volume", "1", "--chapters", "1-3"]
            )
        self.assertIn("失败 2 章", result["error"])

    def test_reindex_fails_when_rag_skill_is_not_loaded(self):
        runtime = SimpleNamespace(
            context=SimpleNamespace(active_skills={})
        )
        with patch("core.runtime.get_runtime", return_value=runtime):
            result = novel_commands.reindex(
                ["--volume", "1", "--chapters", "1"]
            )
        self.assertIn("RAG Skill 未加载", result["error"])

    def test_advertised_stage_commands_are_registered(self):
        dispatcher = CommandDispatcher()
        for command in ("expand", "world", "blueprint", "audit", "track"):
            self.assertIn(command, dispatcher.commands)


if __name__ == "__main__":
    unittest.main()
