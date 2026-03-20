import json
from zhipuai import ZhipuAI
from pydantic import ValidationError
from rich.live import Live
from rich.markdown import Markdown
from utils.config import ANTHROPIC_API_KEY, MODEL_ID, FLASH_MODEL_ID

# Initialize ZhipuAI client
client = ZhipuAI(api_key=ANTHROPIC_API_KEY)

def generate_json(prompt: str, schema_model, system_message: str = "你是一个专业的数据结构化助手。") -> dict:
    """
    模式 A: 专供 s01 和 s02 使用。
    利用 ZhipuAI 的 GLM 模型输出结构化 JSON，并使用 Pydantic 进行失败重试。
    schema_model: A Pydantic BaseModel class used for validation.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # We use a tool calling approach to force the model to output matching the schema
            # Or simpler: ask the model to output strict JSON and validate.
            messages = [
                {"role": "system", "content": system_message + "\n请严格输出 JSON 格式，不要包含任何额外的 explanations。遵循以下 JSON Schema:\n" + json.dumps(schema_model.model_json_schema(), ensure_ascii=False)},
                {"role": "user", "content": prompt}
            ]
            response = client.chat.completions.create(
                model=MODEL_ID,
                messages=messages,
                temperature=0.1
            )
            content = response.choices[0].message.content.strip()
            
            # Remove Markdown JSON wrapper if exists
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
                
            parsed_data = json.loads(content)
            
            # Validate with Pydantic
            schema_model.model_validate(parsed_data)
            return parsed_data
            
        except (json.JSONDecodeError, ValidationError) as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed to generate valid JSON after {max_retries} attempts. Error: {str(e)}")
            # Retry with error feedback
            prompt += f"\n\n上一次的输出存在格式错误：{str(e)}。请修正后重新输出纯净的 JSON。"

def generate_stream(prompt, system_message: str = "你是一个顶尖的网络小说执笔打字机。", tools: list = None):
    """
    模式 B: 专供 s03 执笔使用。
    支持接收 tools 列表；并在流式输出完成或遇到 tool_calls 时，通过事件总线分发。
    """
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
        "temperature": 0.85,
        "stream": True
    }
    if tools:
        kwargs["tools"] = tools

    response = client.chat.completions.create(**kwargs)
    
    collected_messages = []
    tool_calls_data = {}  # 记录流式返回的 tool_calls
    
    with Live(auto_refresh=False, vertical_overflow="visible") as live:
        for chunk in response:
            delta = chunk.choices[0].delta
            
            # Content accumulation
            if hasattr(delta, 'content') and delta.content:
                collected_messages.append(delta.content)
                live.update(Markdown("".join(collected_messages)), refresh=True)
                
            # Tool calls accumulation (stream mode returns fragments)
            if hasattr(delta, 'tool_calls') and delta.tool_calls:
                for tc_chunk in delta.tool_calls:
                    idx = tc_chunk.index
                    if idx not in tool_calls_data:
                        tool_calls_data[idx] = {"id": tc_chunk.id, "name": tc_chunk.function.name, "arguments": ""}
                    if tc_chunk.function.arguments:
                        tool_calls_data[idx]["arguments"] += tc_chunk.function.arguments

    # 如果有 tool_calls，触发 EventBus
    if tool_calls_data:
        from core.event_bus import event_bus
        for idx, call in tool_calls_data.items():
            try:
                args = json.loads(call["arguments"])
                print(f"\\n[⚙️ Model Calling Tool] {call['name']} -> {args}")
                event_bus.emit("execute_tool", call["name"], args)
            except Exception as e:
                print(f"\\n[🚨 Tool Error] 解析或执行工具 {call['name']} 失败: {e}")
                
    return "".join(collected_messages)

def extract_entities(prompt: str) -> list[str]:
    """
    模式 C: 专供 s04 提取实体使用。
    使用最便宜且极速的模型（glm-4-flash），要求其仅输出逗号分隔的实体词。
    """
    messages = [
        {"role": "system", "content": "你是一个轻量级的实体提取引擎。请提取用户文本中的人名、特殊功法名、重要法宝名、核心地名。直接输出 JSON 列表，结构如 [\"林动\", \"玄重尺\"]。不要解释，不要额外输出！"},
        {"role": "user", "content": f"提取以下网文大纲中的核心实体：\n{prompt}"}
    ]
    
    try:
        response = client.chat.completions.create(
            model=FLASH_MODEL_ID,
            messages=messages,
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
    except Exception as e:
        # User feedback: Safe handling of content filters (Error 1301)
        if "1301" in str(e):
            return [] # Safely skip if content filter triggers
        print(f"[WARN] 实体提取失败: {e}")
        return []
    
    # Clean possible markdown format
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    try:
        entities = json.loads(content)
        if isinstance(entities, list):
            return entities
        return []
    except json.JSONDecodeError:
        # Fallback if json parsing fails but it's comma separated
        return [e.strip() for e in content.split(",") if e.strip()]
