"""Runtime configuration and workspace path management."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / "env"
CONFIG_FILE = PROJECT_ROOT / "config.json"
CLI_STATE_FILE = PROJECT_ROOT / ".novel_cli_config" / "state.json"

load_dotenv(dotenv_path=ENV_FILE)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _first_env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return default


def _normalize_openai_base_url(value: str | None) -> str | None:
    """Translate known legacy MiniMax Anthropic endpoints to OpenAI format."""
    if not value:
        return value
    parsed = urlsplit(value.strip())
    if (
        parsed.netloc.lower() in {"api.minimaxi.com", "api.minimax.io"}
        and parsed.path.rstrip("/") == "/anthropic"
    ):
        return urlunsplit((parsed.scheme, parsed.netloc, "/v1", parsed.query, parsed.fragment))
    return value.strip().rstrip("/")


LLM_PROVIDER = (_first_env("LLM_PROVIDER", default="minimax") or "minimax").lower()
LLM_API_KEY = _first_env("LLM_API_KEY", "MINIMAX_API_KEY", "ANTHROPIC_API_KEY")
LLM_BASE_URL = _normalize_openai_base_url(
    _first_env(
        "LLM_BASE_URL",
        "MINIMAX_BASE_URL",
        "ANTHROPIC_BASE_URL",
        default="https://api.minimaxi.com/v1",
    )
)
MODEL_ID = _first_env("MODEL_ID", default="MiniMax-M2.7") or "MiniMax-M2.7"
FLASH_MODEL_ID = _first_env("FLASH_MODEL_ID", default=MODEL_ID) or MODEL_ID
BATCH_MODEL_ID = _first_env("BATCH_MODEL_ID", default="glm-4") or "glm-4"


def _resolve_zhipu_api_key(provider: str, chat_key: str | None) -> str | None:
    dedicated = _first_env("ZHIPU_API_KEY")
    if dedicated:
        return dedicated
    return chat_key if provider.lower() == "zhipu" else None


ZHIPU_API_KEY = _resolve_zhipu_api_key(LLM_PROVIDER, LLM_API_KEY)

# Backward-compatible names used by existing plugins and third-party skills.
MINIMAX_API_KEY = _first_env("MINIMAX_API_KEY") or LLM_API_KEY
MINIMAX_BASE_URL = _first_env("MINIMAX_BASE_URL") or LLM_BASE_URL
ANTHROPIC_API_KEY = _first_env("ANTHROPIC_API_KEY") or LLM_API_KEY
ANTHROPIC_BASE_URL = _first_env("ANTHROPIC_BASE_URL") or LLM_BASE_URL


def _resolve_initial_novel_name() -> str:
    explicit = (os.getenv("NOVEL_NAME") or "").strip()
    if explicit:
        return explicit

    state = _read_json(CLI_STATE_FILE)
    if "current_project" in state:
        return str(state.get("current_project") or "").strip()

    config_name = str(
        _read_json(CONFIG_FILE).get("workspace", {}).get("novel_name") or ""
    ).strip()
    return config_name


def _normalize_novel_name(name: str | None) -> str:
    cleaned = (name or "").strip()
    if cleaned.lower() == "default":
        return ""
    if cleaned in {".", ".."} or any(
        separator in cleaned for separator in ("/", "\\", "\x00")
    ):
        raise ValueError("NOVEL_NAME 不能包含路径分隔符")
    if any(ord(character) < 32 for character in cleaned):
        raise ValueError("NOVEL_NAME 不能包含控制字符")
    if len(cleaned) > 80:
        raise ValueError("NOVEL_NAME 不能超过 80 个字符")
    if cleaned.lower() in {"cli_config", "projects"}:
        raise ValueError(f"NOVEL_NAME={cleaned} 与本地状态目录冲突")
    return cleaned


def _workspace_path(name: str) -> Path:
    return PROJECT_ROOT / (f".novel_{name}" if name else ".novel")


NOVEL_NAME = ""
NOVEL_DIR = ""
SETTINGS_DIR = ""
VOLUMES_DIR = ""
MANUSCRIPTS_DIR = ""
MEMORY_DIR = ""
BATCH_DIR = ""


def set_active_novel(name: str | None, *, ensure: bool = False) -> Path:
    """Update in-process workspace paths and optionally create their directories."""
    global NOVEL_NAME, NOVEL_DIR, SETTINGS_DIR, VOLUMES_DIR
    global MANUSCRIPTS_DIR, MEMORY_DIR, BATCH_DIR

    NOVEL_NAME = _normalize_novel_name(name)
    workspace = _workspace_path(NOVEL_NAME)
    NOVEL_DIR = str(workspace)
    SETTINGS_DIR = str(workspace / "settings")
    VOLUMES_DIR = str(workspace / "volumes")
    MANUSCRIPTS_DIR = str(workspace / "manuscripts")
    MEMORY_DIR = str(workspace / "memory")
    BATCH_DIR = str(workspace / "batch_jobs")

    if ensure:
        ensure_workspace_dirs()
    return workspace


def ensure_workspace_dirs() -> Path:
    """Create the active workspace's standard directory structure."""
    for directory in (
        NOVEL_DIR,
        SETTINGS_DIR,
        VOLUMES_DIR,
        MANUSCRIPTS_DIR,
        MEMORY_DIR,
        BATCH_DIR,
    ):
        Path(directory).mkdir(parents=True, exist_ok=True)
    return Path(NOVEL_DIR)


def reload_workspace(*, ensure: bool = True) -> Path:
    """Re-resolve workspace selection from env, REPL state, and config.json."""
    return set_active_novel(_resolve_initial_novel_name(), ensure=ensure)


try:
    set_active_novel(_resolve_initial_novel_name(), ensure=False)
except ValueError:
    # A hand-edited or partially written local state file must not make even
    # `cli.py --help` unusable. Fall back to the default workspace.
    set_active_novel(None, ensure=False)


_active_threads: list[threading.Thread] = []


def register_background_task(target, *args, **kwargs):
    """Start and track a daemon background task for graceful shutdown."""
    thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
    _active_threads.append(thread)
    thread.start()
    return thread


def wait_for_background_tasks():
    """Wait for registered background tasks before process exit."""
    if not _active_threads:
        return

    try:
        from rich.console import Console

        Console().print(
            f"[bold yellow][INFO] 正在同步本地记忆库 "
            f"(共有 {len(_active_threads)} 个后台任务)，请稍候...[/bold yellow]"
        )
    except ImportError:
        print(f"[INFO] 正在同步本地记忆库 (共有 {len(_active_threads)} 个后台任务)，请稍候...")

    for thread in _active_threads:
        if thread.is_alive():
            thread.join()
    _active_threads.clear()

    try:
        from rich.console import Console

        Console().print("[bold green][✓] 所有后台任务同步完毕，系统安全退出。[/bold green]")
    except ImportError:
        print("[✓] 所有后台任务同步完毕，系统安全退出。")
