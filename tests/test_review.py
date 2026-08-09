import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cli.commands.agent_commands import perform_multi_file_review_impl, review


class ReviewCommandTests(unittest.TestCase):
    def test_review_rejects_unknown_or_incomplete_arguments(self):
        self.assertIn("error", review(["--unknown"]))
        self.assertIn("error", review(["-f"]))

    def test_model_output_cannot_write_an_unrequested_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            allowed = Path(temp_dir) / "allowed.txt"
            outside = Path(temp_dir) / "outside.txt"
            allowed.write_text("old allowed", encoding="utf-8")
            outside.write_text("old outside", encoding="utf-8")
            response = (
                f"==== BEGIN FILE: {allowed.resolve()} ====\nnew allowed\n"
                f"==== END FILE ====\n"
                f"==== BEGIN FILE: {outside.resolve()} ====\nnew outside\n"
                f"==== END FILE ====\n"
            )

            with patch("utils.llm_client.generate_stream", return_value=response):
                self.assertTrue(
                    perform_multi_file_review_impl([str(allowed)], "update it")
                )

            self.assertEqual(allowed.read_text(encoding="utf-8"), "new allowed\n")
            self.assertEqual(outside.read_text(encoding="utf-8"), "old outside")


if __name__ == "__main__":
    unittest.main()
