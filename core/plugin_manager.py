"""Dynamic Skill discovery, loading, and hot reload."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

from core.base_skill import BaseSkill
from core.event_bus import event_bus
from core.novel_context import NovelContext
from utils import config


class PluginManager:
    """Load Skills with initialization rollback and duplicate protection."""

    def __init__(self, context: NovelContext, skills_dir: str | Path | None = None):
        self.context = context
        self.skills_dir = Path(skills_dir or (config.PROJECT_ROOT / "skills"))
        self.loaded_modules: Dict[str, ModuleType] = {}

    def scan_and_load(self):
        if not self.skills_dir.exists():
            return

        print(f"[PluginManager] 正在扫描 {self.skills_dir.name} 目录下的插件...")
        for plugin_path in sorted(self.skills_dir.iterdir()):
            if not plugin_path.is_dir() or plugin_path.name.startswith(("__", ".")):
                continue
            skill_file = plugin_path / "skill.py"
            if not skill_file.exists() or (plugin_path / ".disabled").exists():
                continue
            if plugin_path.name in self.context.active_skills:
                continue
            self._load_skill(plugin_path.name, skill_file)

    def _find_skill_class(self, module: ModuleType):
        for attr_name in dir(module):
            attr: Any = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseSkill) and attr is not BaseSkill:
                return attr
        return None

    def _load_skill(self, module_name: str, file_path: str | Path) -> bool:
        file_path = Path(file_path)
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"无法创建模块规范: {file_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            skill_class = self._find_skill_class(module)
            if skill_class is None:
                raise TypeError(f"未找到继承 BaseSkill 的类: {file_path}")

            skill_instance = skill_class(self.context)
            # Initialization happens before registration so a broken plugin cannot
            # remain active on the global event bus.
            skill_instance.on_init()

            self.loaded_modules[module_name] = module
            self.context.active_skills[module_name] = skill_instance
            event_bus.register(skill_instance)
            print(f"  [✓] 加载插件成功: {skill_instance.name}")
            return True
        except Exception as exc:
            self._unload_skill(module_name)
            try:
                print(f"  [🚨] 加载插件 {module_name} 失败: {exc}")
            except UnicodeEncodeError:
                safe = f"  [ERROR] 加载插件 {module_name} 失败: {exc}"
                print(safe.encode("gbk", "replace").decode("gbk"))
            return False

    def _unload_skill(self, module_name: str):
        old_skill = self.context.active_skills.pop(module_name, None)
        if old_skill is not None:
            event_bus.unregister(old_skill)
        self.loaded_modules.pop(module_name, None)
        sys.modules.pop(module_name, None)

    def unload_all(self):
        for module_name in list(self.context.active_skills):
            self._unload_skill(module_name)

    def hot_reload(self, module_name: str) -> bool:
        print(f"[PluginManager] 正在热更新插件 {module_name}...")
        self._unload_skill(module_name)

        plugin_path = self.skills_dir / module_name
        skill_file = plugin_path / "skill.py"
        disabled_file = plugin_path / ".disabled"
        if not skill_file.exists():
            print(f"[ERROR] 找不到此插件文件: {skill_file}")
            return False
        if disabled_file.exists():
            print(f"[PluginManager] {module_name} 已处于禁用状态，已卸载。")
            return True

        loaded = self._load_skill(module_name, skill_file)
        if loaded:
            print(f"[PluginManager] {module_name} 热更新完毕！")
        return loaded

    def disable_skill(self, module_name: str) -> bool:
        plugin_path = self.skills_dir / module_name
        if not plugin_path.exists():
            print(f"[ERROR] 找不到插件目录: {plugin_path}")
            return False
        (plugin_path / ".disabled").write_text("disabled", encoding="utf-8")
        return self.hot_reload(module_name)

    def enable_skill(self, module_name: str) -> bool:
        plugin_path = self.skills_dir / module_name
        if not plugin_path.exists():
            print(f"[ERROR] 找不到插件目录: {plugin_path}")
            return False
        (plugin_path / ".disabled").unlink(missing_ok=True)
        return self.hot_reload(module_name)
