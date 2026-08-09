"""OpenAI-compatible LLM client with retries and progressive streaming."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI
from pydantic import ValidationError
from rich.live import Live
from rich.markdown import Markdown

from utils import config
from utils.config_loader import get_config


class LLMConfigurationError(RuntimeError):
    """Raised when a network command is used without valid LLM settings."""


_client: OpenAI | None = None
_client_signature: tuple[str, str] | None = None


def get_client() -> OpenAI:
    """Return a lazily-created client for the effective chat configuration."""
    global _client, _client_signature
    if not config.LLM_API_KEY:
        raise LLMConfigurationError(
            "缺少 LLM API 密钥。请在 env 中设置 LLM_API_KEY "
            "（也兼容 MINIMAX_API_KEY 或 ANTHROPIC_API_KEY）。"
        )

    signature = (config.LLM_API_KEY, config.LLM_BASE_URL or "")
    if _client is None or _client_signature != signature:
        _client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL,
            timeout=get_config("generation.timeout", 120),
        )
        _client_signature = signature
    return _client


def reset_client() -> None:
    """Drop the cached client, primarily for configuration reloads and tests."""
    global _client, _client_signature
    _client = None
    _client_signature = None


class _LazyClientProxy:
    """Compatibility proxy for third-party skills that import `client`."""

    def __getattr__(self, name: str):
        return getattr(get_client(), name)


client = _LazyClientProxy()


def _strip_reasoning_prefix(content: str) -> str:
    """Remove a completed `<think>...</think>` prefix when providers return one."""
    stripped = content.strip()
    marker = "</think>"
    if stripped.startswith("<think>") and marker in stripped:
        return stripped.split(marker, 1)[1].strip()
    if stripped.startswith(marker):
        return stripped[len(marker) :].strip()
    return stripped


def _clean_response_content(content: str | None) -> str:
    """Normalize reasoning prefixes and optional Markdown code fences."""
    if not content or not content.strip():
        raise ValueError("模型返回了空内容")

    cleaned = _strip_reasoning_prefix(content)
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1)
    return cleaned.strip()


def _network_errors():
    return (APIError, APITimeoutError, APIConnectionError)


def generate_json(
    prompt: str,
    schema_model,
    system_message: str = "你是一个专业的数据结构化助手。",
) -> dict:
    """Generate and validate strict JSON, retrying format and network failures."""
    max_retries = max(1, int(get_config("generation.max_retries", 3)))
    current_prompt = prompt
    for attempt in range(max_retries):
        try:
            messages = [
                {
                    "role": "system",
                    "content": system_message
                    + "\n请严格输出 JSON 格式，不要包含任何额外说明。遵循以下 JSON Schema:\n"
                    + json.dumps(schema_model.model_json_schema(), ensure_ascii=False),
                },
                {"role": "user", "content": current_prompt},
            ]
            response = get_client().chat.completions.create(
                model=config.MODEL_ID,
                messages=messages,
                temperature=0.1,
            )
            content = _clean_response_content(response.choices[0].message.content)
            parsed_data = json.loads(content)
            schema_model.model_validate(parsed_data)
            return parsed_data
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            if attempt == max_retries - 1:
                raise RuntimeError(
                    f"连续 {max_retries} 次未得到有效 JSON: {exc}"
                ) from exc
            current_prompt += f"\n\n上一次输出格式错误：{exc}。请仅返回修正后的 JSON。"
        except _network_errors() as exc:
            if attempt == max_retries - 1:
                raise RuntimeError(f"API 中断后重试失败: {exc}") from exc
            print(f"\n[⚠️ API 中断] 第 {attempt + 1}/{max_retries} 次失败，等待重试...")
            time.sleep(int(get_config("generation.retry_delay", 5)) * (attempt + 1))

    raise RuntimeError("JSON 生成未完成")


class ProgressiveWriter:
    """Stream text while periodically persisting accumulated content."""

    def __init__(self, on_progress=None, chunk_size: int = 1000):
        self.on_progress = on_progress
        self.chunk_size = chunk_size
        self.accumulated: list[str] = []
        self.last_callback_count = 0

    def write(
        self,
        prompt,
        system_message: str = "你是一个顶尖的网络小说执笔打字机。",
        chapter_id: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        max_retries = max(1, int(get_config("generation.max_retries", 3)))
        retry_delay = int(get_config("generation.retry_delay", 5))

        for attempt in range(max_retries):
            try:
                return self._write_impl(prompt, system_message, chapter_id, tools)
            except _network_errors() as exc:
                print(
                    f"\n[⚠️ API 中断] 第 {attempt + 1}/{max_retries} 次失败: "
                    f"{str(exc)[:100]}"
                )
                if attempt == max_retries - 1:
                    raise RuntimeError(f"API 中断后重试失败: {exc}") from exc
                print(f"[⏳] 等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
                retry_delay *= 2

        raise RuntimeError("流式生成未完成")

    def _write_impl(self, prompt, system_message, chapter_id, tools) -> str:
        prompt_content = "\n".join(prompt) if isinstance(prompt, list) else str(prompt)
        kwargs: dict[str, Any] = {
            "model": config.MODEL_ID,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt_content},
            ],
            "temperature": get_config("generation.temperature", 0.85),
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        response = get_client().chat.completions.create(**kwargs)
        self.accumulated = []
        self.last_callback_count = 0
        tool_calls: dict[int, dict[str, str | None]] = {}

        with Live(auto_refresh=False, vertical_overflow="visible") as live:
            for chunk in response:
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    self.accumulated.append(delta.content)
                    accumulated_text = "".join(self.accumulated)
                    if (
                        self.on_progress
                        and len(accumulated_text) - self.last_callback_count >= self.chunk_size
                    ):
                        self.last_callback_count = len(accumulated_text)
                        self.on_progress(chapter_id, accumulated_text, len(accumulated_text))
                    live.update(Markdown(accumulated_text), refresh=True)

                for tool_chunk in getattr(delta, "tool_calls", None) or []:
                    index = int(tool_chunk.index)
                    current = tool_calls.setdefault(
                        index, {"id": None, "name": None, "arguments": ""}
                    )
                    if getattr(tool_chunk, "id", None):
                        current["id"] = tool_chunk.id
                    function = getattr(tool_chunk, "function", None)
                    if function and getattr(function, "name", None):
                        current["name"] = function.name
                    if function and getattr(function, "arguments", None):
                        current["arguments"] = str(current["arguments"]) + function.arguments

        self._dispatch_tool_calls(tool_calls)
        final_result = _strip_reasoning_prefix("".join(self.accumulated))
        if self.on_progress:
            self.on_progress(chapter_id, final_result, len(final_result))
        return final_result

    @staticmethod
    def _dispatch_tool_calls(tool_calls: dict[int, dict[str, str | None]]) -> None:
        if not tool_calls:
            return
        from core.event_bus import event_bus

        for call in tool_calls.values():
            name = call.get("name")
            if not name:
                continue
            try:
                arguments = json.loads(str(call.get("arguments") or "{}"))
                event_bus.emit("execute_tool", name, arguments)
            except (json.JSONDecodeError, TypeError) as exc:
                print(f"[Tool Error] 无法解析或执行 {name}: {exc}")


def generate_stream(
    prompt,
    system_message: str = "你是一个顶尖的网络小说执笔打字机。",
    tools: list[dict[str, Any]] | None = None,
):
    """Backward-compatible streaming helper."""
    return ProgressiveWriter().write(prompt, system_message, None, tools)


def extract_entities(prompt: str) -> list[str]:
    messages = [
        {
            "role": "system",
            "content": "提取文本中的人名、功法、法宝和地名，仅返回 JSON 字符串列表。",
        },
        {"role": "user", "content": prompt},
    ]
    try:
        response = get_client().chat.completions.create(
            model=config.FLASH_MODEL_ID,
            messages=messages,
            temperature=0.1,
        )
        content = _clean_response_content(response.choices[0].message.content)
    except Exception as exc:
        if "1301" not in str(exc):
            print(f"[WARN] 实体提取失败: {exc}")
        return []

    try:
        entities = json.loads(content)
    except json.JSONDecodeError:
        return [item.strip() for item in content.split(",") if item.strip()]
    return [str(item) for item in entities] if isinstance(entities, list) else []
