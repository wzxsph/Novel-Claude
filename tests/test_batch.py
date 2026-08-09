import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from cli.commands import novel_commands
from scene_writer import process_batch_results
from utils import batch_client


class BatchWorkflowTests(unittest.TestCase):
    def tearDown(self):
        batch_client.reset_batch_client()

    def test_batch_client_is_lazy_and_reports_a_missing_key(self):
        with patch.object(batch_client.config, "ZHIPU_API_KEY", None):
            batch_client.reset_batch_client()
            with self.assertRaises(batch_client.BatchConfigurationError):
                batch_client.get_batch_client()

    @patch("utils.batch_client.ZhipuAI")
    def test_batch_client_is_cached(self, client_class):
        with patch.object(batch_client.config, "ZHIPU_API_KEY", "test-key"):
            batch_client.reset_batch_client()
            first = batch_client.get_batch_client()
            second = batch_client.get_batch_client()

        self.assertIs(first, second)
        client_class.assert_called_once_with(api_key="test-key")

    def test_submit_uploads_jsonl_and_creates_batch(self):
        fake_client = MagicMock()
        fake_client.files.create.return_value = SimpleNamespace(id="file-1")
        fake_client.batches.create.return_value = SimpleNamespace(id="batch-1")

        with tempfile.TemporaryDirectory() as temp_dir:
            request_path = Path(temp_dir) / "request.jsonl"
            request_path.write_text("{}\n", encoding="utf-8")
            with patch("utils.batch_client.get_batch_client", return_value=fake_client):
                batch_id = batch_client.submit_batch_task(
                    str(request_path), desc="smoke test"
                )

        self.assertEqual(batch_id, "batch-1")
        fake_client.files.create.assert_called_once()
        fake_client.batches.create.assert_called_once_with(
            input_file_id="file-1",
            endpoint="/v4/chat/completions",
            auto_delete_input_file=True,
            metadata={"description": "smoke test"},
        )

    def test_batch_sync_polls_downloads_and_processes(self):
        statuses = [
            SimpleNamespace(status="in_progress"),
            SimpleNamespace(status="completed"),
        ]
        with (
            patch("utils.batch_client.get_batch_status", side_effect=statuses) as status,
            patch("utils.batch_client.download_batch_results", return_value=True) as download,
            patch("scene_writer.process_batch_results") as process,
            patch("cli.commands.novel_commands.time.sleep") as sleep,
        ):
            result = novel_commands.batch_sync(["batch-1"])

        self.assertNotIn("error", result)
        self.assertEqual(status.call_count, 2)
        sleep.assert_called_once_with(60)
        download.assert_called_once()
        process.assert_called_once()

    def test_result_parser_maps_success_and_failed_rows(self):
        rows = [
            {
                "custom_id": "v01_ch001",
                "response": {
                    "body": {"choices": [{"message": {"content": "chapter one"}}]}
                },
            },
            {"custom_id": "v01_ch002", "response": {"body": {}}},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            result_path = Path(temp_dir) / "results.jsonl"
            result_path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
            with patch("scene_writer.save_chapter_content") as save:
                process_batch_results(str(result_path))

        self.assertEqual(
            save.call_args_list,
            [
                call(1, 1, "chapter one"),
                call(1, 2, "（该段场景生成失败）"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
