import threading
import json
from pathlib import Path

from utils import config

class WorkspaceManager:
    """Provides thread-safe file operations for the .novel workspace to support high concurrency."""
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or config.NOVEL_DIR).resolve()
        self._lock = threading.Lock()
        
        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str | Path) -> Path:
        """Resolve a file path without allowing it to escape the workspace."""
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.base_dir / candidate
        candidate = candidate.resolve()
        try:
            candidate.relative_to(self.base_dir)
        except ValueError as exc:
            raise ValueError(f"路径超出当前工作区: {path}") from exc
        return candidate

    def safe_write_json(self, rel_path: str, data: dict):
        """Thread-safe JSON write."""
        with self._lock:
            target = self._resolve(rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
    def safe_read_json(self, rel_path: str) -> dict:
        """Thread-safe JSON read. Returns empty dict if file is missing."""
        with self._lock:
            target = self._resolve(rel_path)
            if target.exists():
                with open(target, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}

    def safe_write_text(self, rel_path: str, content: str):
        """Thread-safe purely text write."""
        with self._lock:
            target = self._resolve(rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, 'w', encoding='utf-8') as f:
                f.write(content)
                
    def safe_read_text(self, rel_path: str) -> str:
        """Thread-safe text read. Returns empty string if file is missing."""
        with self._lock:
            target = self._resolve(rel_path)
            if target.exists():
                with open(target, 'r', encoding='utf-8') as f:
                    return f.read()
            return ""

def get_workspace() -> WorkspaceManager:
    """Return a manager for the currently active workspace."""
    return WorkspaceManager(config.NOVEL_DIR)
