import os
import threading
from dotenv import load_dotenv

# Load environment variables from `env` file in the project root
load_dotenv(dotenv_path="env")

# Global Settings
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://open.bigmodel.cn/api/anthropic")
MODEL_ID = os.getenv("MODEL_ID", "glm-4.6v")
FLASH_MODEL_ID = "glm-4.6v"  # Used for cheap extraction tasks

NOVEL_DIR = ".novel"
SETTINGS_DIR = os.path.join(NOVEL_DIR, "settings")
VOLUMES_DIR = os.path.join(NOVEL_DIR, "volumes")
MANUSCRIPTS_DIR = os.path.join(NOVEL_DIR, "manuscripts")
MEMORY_DIR = os.path.join(NOVEL_DIR, "memory")

# Ensure base directories exist
for d in [SETTINGS_DIR, VOLUMES_DIR, MANUSCRIPTS_DIR, MEMORY_DIR]:
    os.makedirs(d, exist_ok=True)

# Thread management for graceful shutdown
_active_threads = []

def register_background_task(target, *args, **kwargs):
    """
    Register and start a background thread that will be tracked for graceful shutdown.
    """
    thread = threading.Thread(target=target, args=args, kwargs=kwargs)
    thread.daemon = True # Daemon true so it won't block python if not joined, but we will join it manually
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
    
    # We delay loading rich to avoid circular imports or unnecessary overhead if not in TTY
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
