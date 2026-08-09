import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

from scene_writer import (
    count_chinese_words,
    deep_review_chapter,
    review_chapter_content,
    run_scene_writer,
)
from utils import config


def _review_setting(key, default=None):
    values = {
        "review.auto_fix_title": True,
        "review.word_count_check": False,
    }
    return values.get(key, default)


class SceneWriterReviewTests(unittest.TestCase):
    def test_chinese_word_count_excludes_full_width_punctuation(self):
        self.assertEqual(count_chinese_words("中文，。！？　Ａ hello-world 42"), 5)

    def test_colon_style_chapter_header_is_recognized(self):
        content = "# 第1章：风\n\n正文\n第二行"
        with patch("scene_writer.get_config", side_effect=_review_setting):
            reviewed, needs_rewrite, issues = review_chapter_content(
                1, 1, content, {"title": "风"}
            )

        self.assertEqual(reviewed, content)
        self.assertFalse(needs_rewrite)
        self.assertFalse(any("缺少章节标题" in issue for issue in issues))

    def test_auto_title_does_not_repeat_chapter_number_from_outline(self):
        content = "正文第一行\n正文第二行\n正文第三行"
        with patch("scene_writer.get_config", side_effect=_review_setting):
            reviewed, _, _ = review_chapter_content(
                1, 1, content, {"title": "第1章 风起"}
            )

        self.assertTrue(reviewed.startswith("# 第1章 风起\n"))
        self.assertNotIn("第1章 第1章", reviewed)

    def test_wrong_chapter_number_is_replaced_instead_of_nested(self):
        content = "# 第1章 旧标题\n\n正文"
        with patch("scene_writer.get_config", side_effect=_review_setting):
            reviewed, _, _ = review_chapter_content(
                1, 2, content, {"title": "第2章 新标题"}
            )

        self.assertTrue(reviewed.startswith("# 第2章 新标题\n"))
        self.assertNotIn("# 第1章", reviewed)

    def test_empty_body_is_rejected_even_when_word_count_check_is_disabled(self):
        with patch("scene_writer.get_config", side_effect=_review_setting):
            _, needs_rewrite, issues = review_chapter_content(
                1, 1, "# 第1章 空章", {"title": "空章"}
            )

        self.assertTrue(needs_rewrite)
        self.assertTrue(any("正文内容为空" in issue for issue in issues))

    def test_deep_review_handles_a_missing_outline(self):
        expected = {
            "needs_rewrite": False,
            "issues": [],
            "guidance": "",
            "missing_events": [],
            "wrong_events": [],
        }
        with (
            patch("scene_writer.get_config", return_value=True),
            patch("utils.llm_client.generate_json", return_value=expected),
        ):
            self.assertEqual(deep_review_chapter("正文", None, []), expected)

    def test_entity_tracking_failure_does_not_fail_a_saved_chapter(self):
        state_manager = MagicMock()
        state_manager.get_state.return_value = SimpleNamespace(state="pending")
        runtime = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(config, "MANUSCRIPTS_DIR", str(Path(temp_dir))),
                patch.object(config, "ensure_workspace_dirs"),
                patch("scene_writer.get_runtime", return_value=runtime),
                patch("scene_writer.get_state_manager", return_value=state_manager),
                patch("scene_writer.generate_chapter_content", return_value="正文"),
                patch(
                    "scene_writer.save_chapter_content",
                    return_value=("chapter.md", False, ""),
                ),
                patch("scene_writer.event_bus.emit"),
                patch(
                    "core.entity_tracker.track_chapter_entities",
                    side_effect=RuntimeError("tracker unavailable"),
                ),
            ):
                result = run_scene_writer(1, 1, 1)

        self.assertEqual(result, (1, 0))
        state_manager.mark_completed.assert_called_once_with(1)
        state_manager.mark_failed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
