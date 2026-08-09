from typing import Any, List

class EventBus:
    """
    中央事件总线 (单例模式)
    负责所有的钩子 (Hooks) 派发，并在执行插件代码时包裹严格的容错隔离层。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.subscribers = []
        return cls._instance

    def register(self, skill):
        """注册一个 Skill 到总线"""
        if skill not in self.subscribers:
            self.subscribers.append(skill)
            
    def unregister(self, skill):
        """注销一个 Skill"""
        if skill in self.subscribers:
            self.subscribers.remove(skill)
            
    def clear(self):
        """清空所有订阅者"""
        self.subscribers.clear()

    def emit(self, event_name: str, *args, **kwargs):
        """
        触发所有订阅了此事件的插件。
        【容错隔离】: 如果单个插件崩溃，不会影响主线程和其他插件。
        """
        results = []
        for skill in self.subscribers:
            if hasattr(skill, event_name):
                method = getattr(skill, event_name)
                try:
                    res = method(*args, **kwargs)
                    results.append(res)
                except Exception as e:
                    print(f"\\n[🚨 EventBus 容错警报] 插件 '{skill.name}' 在执行 '{event_name}' 时崩溃: {e}")
                    print("[EventBus] 已自动隔离该错误并跳过此插件，生成进度继续。\\n")
        return results

    def emit_pipeline(self, event_name: str, initial_data: Any, *args, **kwargs) -> Any:
        """
        串行处理模式：将第一个插件的处理结果传给下一个插件。
        用于 `prompt_payload` 这类需要累加处理的场景。
        """
        data = initial_data
        for skill in self.subscribers:
            if hasattr(skill, event_name):
                method = getattr(skill, event_name)
                try:
                    result = method(data, *args, **kwargs)
                    # A hook that only performs a side effect may return None.
                    # Keep the last valid payload instead of poisoning the rest
                    # of the pipeline.
                    if result is not None:
                        data = result
                except Exception as e:
                    print(f"\\n[🚨 EventBus 容错警报] 插件 '{skill.name}' 在执行 '{event_name}' 串行处理时崩溃: {e}")
                    print("[EventBus] 已自动隔离该错误，保留前一次的有效数据并继续。\\n")
        return data

    def collect(self, method_name: str, *args, **kwargs) -> List[Any]:
        """
        按列表收集所有插件的方法返回结果（如收集 active_tools）。
        """
        collected = []
        for skill in self.subscribers:
            if hasattr(skill, method_name):
                method = getattr(skill, method_name)
                try:
                    res = method(*args, **kwargs)
                    if isinstance(res, list):
                        collected.extend(res)
                    elif res is not None:
                        collected.append(res)
                except Exception as e:
                    print(f"\\n[🚨 EventBus 容错警报] 插件 '{skill.name}' 在调用 '{method_name}' 时崩溃: {e}")
        return collected

    def collect_tools(self) -> List[dict]:
        """Collect valid, uniquely named OpenAI tool definitions."""
        tools = []
        owners = {}
        for skill in self.subscribers:
            try:
                definitions = skill.get_llm_tools()
            except Exception as exc:
                print(
                    f"\\n[🚨 EventBus 容错警报] 插件 '{skill.name}' "
                    f"在注册工具时崩溃: {exc}"
                )
                continue
            for definition in definitions or []:
                function = definition.get("function", {}) if isinstance(definition, dict) else {}
                name = function.get("name")
                if not isinstance(name, str) or not name.strip():
                    print(f"[Tool Warning] 插件 '{skill.name}' 提供了无效工具定义，已跳过。")
                    continue
                if name in owners:
                    print(
                        f"[Tool Warning] 工具名 '{name}' 同时由 '{owners[name]}' "
                        f"和 '{skill.name}' 注册，后者已跳过。"
                    )
                    continue
                owners[name] = skill.name
                tools.append(definition)
        return tools

    def dispatch_tool(self, tool_name: str, kwargs: dict) -> str:
        """Execute a tool only on the Skill that declared that tool name."""
        owners = []
        for skill in self.subscribers:
            try:
                definitions = skill.get_llm_tools()
            except Exception as exc:
                print(
                    f"[Tool Warning] 无法读取插件 '{skill.name}' 的工具定义: {exc}"
                )
                continue
            names = {
                item.get("function", {}).get("name")
                for item in definitions or []
                if isinstance(item, dict)
            }
            if tool_name in names:
                owners.append(skill)

        if not owners:
            return f"[Tool Error] 未注册工具: {tool_name}"
        if len(owners) > 1:
            owner_names = ", ".join(skill.name for skill in owners)
            print(
                f"[Tool Warning] 工具名冲突: {tool_name} ({owner_names})；"
                f"使用最先注册的插件。"
            )

        owner = owners[0]
        try:
            result = owner.execute_tool(tool_name, kwargs)
        except Exception as exc:
            print(f"[Tool Error] 插件 '{owner.name}' 执行 '{tool_name}' 失败: {exc}")
            return f"[Tool Error] {tool_name} 执行失败: {exc}"
        return "" if result is None else str(result)

# 创建全局单例暴露供使用
event_bus = EventBus()
