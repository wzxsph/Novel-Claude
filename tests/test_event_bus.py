import unittest

from core.event_bus import event_bus


class _PipelineSkill:
    def __init__(self, name, callback):
        self.name = name
        self.callback = callback

    def transform(self, payload):
        return self.callback(payload)


class _ToolSkill:
    def __init__(self, name, tool_name, result):
        self.name = name
        self.tool_name = tool_name
        self.result = result
        self.calls = []

    def get_llm_tools(self):
        return [
            {
                "type": "function",
                "function": {"name": self.tool_name, "parameters": {}},
            }
        ]

    def execute_tool(self, tool_name, kwargs):
        self.calls.append((tool_name, kwargs))
        return self.result


class EventBusTests(unittest.TestCase):
    def tearDown(self):
        event_bus.clear()

    def test_pipeline_keeps_last_payload_when_hook_returns_none(self):
        first = _PipelineSkill("first", lambda payload: payload + ["first"])
        side_effect_only = _PipelineSkill("side-effect", lambda payload: None)
        last = _PipelineSkill("last", lambda payload: payload + ["last"])
        for skill in (first, side_effect_only, last):
            event_bus.register(skill)

        result = event_bus.emit_pipeline("transform", [])

        self.assertEqual(result, ["first", "last"])

    def test_tools_are_deduplicated_and_routed_to_the_first_owner(self):
        first = _ToolSkill("first", "demo", "first result")
        duplicate = _ToolSkill("duplicate", "demo", "duplicate result")
        other = _ToolSkill("other", "other", "other result")
        for skill in (first, duplicate, other):
            event_bus.register(skill)

        tools = event_bus.collect_tools()
        result = event_bus.dispatch_tool("demo", {"value": 1})

        self.assertEqual(
            [tool["function"]["name"] for tool in tools], ["demo", "other"]
        )
        self.assertEqual(result, "first result")
        self.assertEqual(first.calls, [("demo", {"value": 1})])
        self.assertEqual(duplicate.calls, [])
        self.assertEqual(other.calls, [])

    def test_unknown_tool_returns_a_model_visible_error(self):
        self.assertIn("未注册工具", event_bus.dispatch_tool("missing", {}))


if __name__ == "__main__":
    unittest.main()
