import os
import json
import threading
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from `env` file in the project root
load_dotenv(dotenv_path="env")

# Load config.json for workspace settings
_config_path = Path(__file__).parent.parent / "config.json"
_config = {}
if _config_path.exists():
    with open(_config_path, 'r', encoding='utf-8') as f:
        _config = json.load(f)

# Global Settings - Support for both MiniMax and ZhipuAI
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
MODEL_ID = os.getenv("MODEL_ID", "MiniMax-Text-01")
FLASH_MODEL_ID = os.getenv("FLASH_MODEL_ID", "MiniMax-Text-01")

# Legacy aliases for backward compatibility
ANTHROPIC_API_KEY = MINIMAX_API_KEY
ANTHROPIC_BASE_URL = MINIMAX_BASE_URL

# Workspace Settings - read from config.json first, fallback to env
_noval_name_from_config = _config.get("workspace", {}).get("novel_name", "")
NOVEL_NAME = _noval_name_from_config if _noval_name_from_config else os.getenv("NOVEL_NAME", "").strip()
NOVEL_DIR = f".novel_{NOVEL_NAME}" if NOVEL_NAME else ".novel"

SETTINGS_DIR = os.path.join(NOVEL_DIR, "settings")
VOLUMES_DIR = os.path.join(NOVEL_DIR, "volumes")
MANUSCRIPTS_DIR = os.path.join(NOVEL_DIR, "manuscripts")
MEMORY_DIR = os.path.join(NOVEL_DIR, "memory")
BATCH_DIR = os.path.join(NOVEL_DIR, "batch_jobs")

# Ensure base directories exist
for d in [NOVEL_DIR, SETTINGS_DIR, VOLUMES_DIR, MANUSCRIPTS_DIR, MEMORY_DIR, BATCH_DIR]:
    os.makedirs(d, exist_ok=True)


def reload_workspace():
    """Reload workspace settings from config.json (call after modifying config)"""
    global NOVEL_NAME, NOVEL_DIR, SETTINGS_DIR, VOLUMES_DIR, MANUSCRIPTS_DIR, MEMORY_DIR, BATCH_DIR

    # Re-read config.json
    if _config_path.exists():
        with open(_config_path, 'r', encoding='utf-8') as f:
            _config = json.load(f)

    _noval_name_from_config = _config.get("workspace", {}).get("novel_name", "")
    NOVEL_NAME = _noval_name_from_config if _noval_name_from_config else os.getenv("NOVEL_NAME", "").strip()
    NOVEL_DIR = f".novel_{NOVEL_NAME}" if NOVEL_NAME else ".novel"

    SETTINGS_DIR = os.path.join(NOVEL_DIR, "settings")
    VOLUMES_DIR = os.path.join(NOVEL_DIR, "volumes")
    MANUSCRIPTS_DIR = os.path.join(NOVEL_DIR, "manuscripts")
    MEMORY_DIR = os.path.join(NOVEL_DIR, "memory")
    BATCH_DIR = os.path.join(NOVEL_DIR, "batch_jobs")

    # Ensure directories exist
    for d in [NOVEL_DIR, SETTINGS_DIR, VOLUMES_DIR, MANUSCRIPTS_DIR, MEMORY_DIR, BATCH_DIR]:
        os.makedirs(d, exist_ok=True)


# Thread management for graceful shutdown
_active_threads = []

def register_background_task(target, *args, **kwargs):
    """
    Register and start a background thread that will be tracked for graceful shutdown.
    """
    thread = threading.Thread(target=target, args=args, kwargs=kwargs)
    thread.daemon = True
    _active_threads.append(thread)
    thread.start()
    return thread

def wait_for_background_tasks():
    """
    Wait for all registered background threads to finish.
    Useful at the end of the CLI lifecycle to ensure data like ChromaDB embeddings is written.
    """
    if not _active_threads:
        return

    try:
        from rich.console import Console
        console = Console()
        console.print(f"[bold yellow][INFO] 正在同步本地记忆库 (共有 {len(_active_threads)} 个后台任务)，请稍候...[/bold yellow]")
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