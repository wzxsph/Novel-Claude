"""
LLM Client with progressive saving support
"""

import json
import time
from openai import OpenAI
from openai import APIError, APITimeoutError
from pydantic import ValidationError
from rich.live import Live
from rich.markdown import Markdown
from utils.config import MINIMAX_API_KEY, MINIMAX_BASE_URL, MODEL_ID, FLASH_MODEL_ID
from utils.config_loader import get_config

# Handle ConnectionError properly
try:
    from openai import ConnectionError as OpenAIConnectionError
except ImportError:
    OpenAIConnectionError = Exception

client = None

def _get_client():
    global client
    if client is None:
        client = OpenAI(
            api_key=MINIMAX_API_KEY,
            base_url=MINIMAX_BASE_URL,
            timeout=get_config("generation.timeout", 120)
        )
    return client


def _clean_response_content(content: str) -> str:
    if "" in content:
        content = content.split("")[-1].strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


def generate_json(prompt: str, schema_model, system_message: str = "你是一个专业的数据结构化助手。") -> dict:
    """模式 A: JSON 结构化输出，带重试机制"""
    max_retries = get_config("generation.max_retries", 3)
    for attempt in range(max_retries):
        try:
            messages = [
                {"role": "system", "content": system_message + "\n请严格输出 JSON 格式，不要包含任何额外的 explanations。遵循以下 JSON Schema:\n" + json.dumps(schema_model.model_json_schema(), ensure_ascii=False)},
                {"role": "user", "content": prompt}
            ]
            response = _get_client().chat.completions.create(
                model=MODEL_ID,
                messages=messages,
                temperature=0.1
            )
            content = _clean_response_content(response.choices[0].message.content)
            parsed_data = json.loads(content)
            schema_model.model_validate(parsed_data)
            return parsed_data

        except (json.JSONDecodeError, ValidationError) as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed to generate valid JSON after {max_retries} attempts. Error: {str(e)}")
            prompt += f"\n\n上一次的输出存在格式错误：{str(e)}。请修正后重新输出纯净的 JSON。"
        except (APIError, APITimeoutError, OpenAIConnectionError) as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"API中断后重试失败: {str(e)}")
            print(f"\n[⚠️ API 中断] 第 {attempt + 1}/{max_retries} 次尝试失败，等待重试...")
            time.sleep(get_config("generation.retry_delay", 5) * (attempt + 1))


class ProgressiveWriter:
    """
    流式生成器，支持渐进式保存。
    每生成一定字数就调用回调函数保存。
    """

    def __init__(self, on_progress=None, chunk_size: int = 1000):
        """
        Args:
            on_progress: 回调函数 (chapter_id, accumulated_content, char_count)
            chunk_size: 每生成多少字调用一次回调
        """
        self.on_progress = on_progress
        self.chunk_size = chunk_size
        self.accumulated = []
        self.last_callback_count = 0

    def write(self, prompt, system_message: str = "你是一个顶尖的网络小说执笔打字机。", chapter_id: int = None):
        """
        执行渐进式写作。
        Returns: 完整内容
        """
        max_retries = get_config("generation.max_retries", 3)
        retry_delay = get_config("generation.retry_delay", 5)

        for attempt in range(max_retries):
            try:
                return self._write_impl(prompt, system_message, chapter_id)
            except (APIError, APITimeoutError, OpenAIConnectionError) as e:
                print(f"\n[⚠️ API 中断] 第 {attempt + 1}/{max_retries} 次尝试失败: {str(e)[:100]}")
                if attempt < max_retries - 1:
                    print(f"[⏳] 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print(f"[🚨] 已达到最大重试次数 {max_retries}，放弃本次生成")
                    raise RuntimeError(f"API中断后重试失败: {str(e)}")

    def _write_impl(self, prompt, system_message: str, chapter_id: int = None):
        """内部实现"""
        if isinstance(prompt, list):
            prompt_content = "\n".join(prompt)
        else:
            prompt_content = str(prompt)

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt_content}
        ]

        kwargs = {
            "model": MODEL_ID,
            "messages": messages,
            "temperature": get_config("generation.temperature", 0.85),
            "stream": True
        }

        response = _get_client().chat.completions.create(**kwargs)

        self.accumulated = []
        self.last_callback_count = 0

        with Live(auto_refresh=False, vertical_overflow="visible") as live:
            for chunk in response:
                delta = chunk.choices[0].delta

                if hasattr(delta, 'content') and delta.content:
                    self.accumulated.append(delta.content)
                    accumulated_text = "".join(self.accumulated)

                    # 调用进度回调（每chunk_size字）
                    if self.on_progress and len(accumulated_text) - self.last_callback_count >= self.chunk_size:
                        self.last_callback_count = len(accumulated_text)
                        self.on_progress(chapter_id, accumulated_text, len(accumulated_text))

                    live.update(Markdown(accumulated_text), refresh=True)

        final_result = "".join(self.accumulated)
        if "" in final_result:
            final_result = final_result.split("")[-1].strip()

        # 最终回调
        if self.on_progress:
            self.on_progress(chapter_id, final_result, len(final_result))

        return final_result


# 兼容旧接口
def generate_stream(prompt, system_message: str = "你是一个顶尖的网络小说执笔打字机。", tools: list = None):
    """兼容旧接口的流式生成"""
    writer = ProgressiveWriter()
    return writer.write(prompt, system_message, None)


def extract_entities(prompt: str) -> list[str]:
    """模式 C: 实体提取"""
    messages = [
        {"role": "system", "content": "你是一个轻量级的实体提取引擎。请提取用户文本中的人名、特殊功法名、重要法宝名、核心地名。直接输出 JSON 列表，结构如 [\"林动\", \"玄重尺\"]。不要解释，不要额外输出！"},
        {"role": "user", "content": f"提取以下网文大纲中的核心实体：\n{prompt}"}
    ]

    try:
        response = _get_client().chat.completions.create(
            model=FLASH_MODEL_ID,
            messages=messages,
            temperature=0.1
        )
        content = _clean_response_content(response.choices[0].message.content)
    except Exception as e:
        if "1301" in str(e):
            return []
        print(f"[WARN] 实体提取失败: {e}")
        return []

    try:
        entities = json.loads(content)
        if isinstance(entities, list):
            return entities
        return []
    except json.JSONDecodeError:
        return [e.strip() for e in content.split(",") if e.strip()]