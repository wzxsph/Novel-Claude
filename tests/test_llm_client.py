import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from openai import APIConnectionError

from core.event_bus import event_bus
from utils import config
from utils import llm_client


class _ToolSubscriber:
    name = "test-tool"

    def __init__(self):
        self.calls = []

    def get_llm_tools(self):
        return [{"type": "function", "function": {"name": "demo"}}]

    def execute_tool(self, tool_name, kwargs):
        self.calls.append((tool_name, kwargs))
        return "tool complete"


class LLMClientTests(unittest.TestCase):
    def tearDown(self):
        event_bus.clear()
        llm_client.reset_client()

    def test_clean_response_content(self):
        content = "<think>hidden</think>\n```json\n{\"ok\": true}\n```"
        self.assertEqual(llm_client._clean_response_content(content), '{"ok": true}')
        self.assertEqual(
            llm_client._clean_response_content('```json{"ok": true}```'),
            '{"ok": true}',
        )
        self.assertEqual(
            llm_client._clean_response_content('{"literal": "</think>"}'),
            '{"literal": "</think>"}',
        )
        with self.assertRaises(ValueError):
            llm_client._clean_response_content("")

    def test_missing_key_fails_lazily(self):
        with patch.object(config, "LLM_API_KEY", None):
            llm_client.reset_client()
            with self.assertRaises(llm_client.LLMConfigurationError):
                llm_client.get_client()

    @patch("utils.llm_client.OpenAI")
    def test_client_is_cached(self, openai_class):
        with (
            patch.object(config, "LLM_API_KEY", "test-key"),
            patch.object(config, "LLM_BASE_URL", "https://example.invalid/v1"),
        ):
            llm_client.reset_client()
            first = llm_client.get_client()
            second = llm_client.get_client()
        self.assertIs(first, second)
        openai_class.assert_called_once()

    def test_streamed_tool_calls_are_assembled_and_dispatched(self):
        chunks = [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content="hello",
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call-1",
                                    function=SimpleNamespace(name="demo", arguments='{\"n\":'),
                                )
                            ],
                        )
                    )
                ]
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id=None,
                                    function=SimpleNamespace(name=None, arguments="1}"),
                                )
                            ],
                        )
                    )
                ]
            ),
        ]
        follow_up_chunks = [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content=" world", tool_calls=None)
                    )
                ]
            )
        ]
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = [chunks, follow_up_chunks]
        subscriber = _ToolSubscriber()
        event_bus.register(subscriber)

        live = MagicMock()
        live.__enter__.return_value = live
        with (
            patch("utils.llm_client.get_client", return_value=fake_client),
            patch("utils.llm_client.Live", return_value=live),
        ):
            result = llm_client.ProgressiveWriter().write(
                "prompt",
                tools=[{"type": "function", "function": {"name": "demo"}}],
            )

        self.assertEqual(result, "hello world")
        self.assertEqual(subscriber.calls, [("demo", {"n": 1})])
        follow_up_messages = fake_client.chat.completions.create.call_args_list[1].kwargs[
            "messages"
        ]
        self.assertEqual(follow_up_messages[-1]["role"], "tool")
        self.assertEqual(follow_up_messages[-1]["content"], "tool complete")

    def test_api_connection_error_is_wrapped_after_retry_budget(self):
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = APIConnectionError(
            request=httpx.Request("POST", "https://example.invalid/v1/chat/completions")
        )

        def get_setting(key, default=None):
            return 1 if key == "generation.max_retries" else default

        with (
            patch("utils.llm_client.get_client", return_value=fake_client),
            patch("utils.llm_client.get_config", side_effect=get_setting),
            self.assertRaisesRegex(RuntimeError, "API 中断后重试失败"),
        ):
            llm_client.ProgressiveWriter().write("prompt")


if __name__ == "__main__":
    unittest.main()
