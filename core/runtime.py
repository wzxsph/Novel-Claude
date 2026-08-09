"""Shared runtime used by both Click commands and the interactive REPL."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.event_bus import event_bus
from core.novel_context import NovelContext
from core.plugin_manager import PluginManager
from utils import config
from utils.workspace import WorkspaceManager


@dataclass
class Runtime:
    workspace: WorkspaceManager
    context: NovelContext
    plugin_manager: PluginManager
    workspace_path: Path
    plugins_loaded: bool = False


_runtime: Runtime | None = None


def get_runtime(*, load_plugins: bool = True) -> Runtime:
    global _runtime
    workspace_path = Path(config.NOVEL_DIR).resolve()
    if _runtime is None or _runtime.workspace_path != workspace_path:
        if _runtime is not None:
            _runtime.plugin_manager.unload_all()
        config.ensure_workspace_dirs()
        workspace = WorkspaceManager(workspace_path)
        context = NovelContext(workspace)
        manager = PluginManager(context)
        _runtime = Runtime(workspace, context, manager, workspace_path)

    if load_plugins and not _runtime.plugins_loaded:
        _runtime.plugin_manager.scan_and_load()
        _runtime.plugins_loaded = True
    return _runtime


def reset_runtime() -> None:
    global _runtime
    if _runtime is not None:
        _runtime.plugin_manager.unload_all()
    event_bus.clear()
    _runtime = None
