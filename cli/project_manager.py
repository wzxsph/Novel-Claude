"""Project management for the interactive CLI."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from utils import config


PROJECT_ROOT = config.PROJECT_ROOT
CONFIG_DIR = PROJECT_ROOT / ".novel_cli_config"
CONFIG_FILE = CONFIG_DIR / "state.json"
DEFAULT_PROJECT_NAME = "default"


def _validate_project_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("项目名不能为空")
    if any(separator in cleaned for separator in ("/", "\\", "\x00")):
        raise ValueError("项目名不能包含路径分隔符")
    return cleaned


class ProjectManager:
    """Manage `.novel_<name>` workspaces and persisted REPL context."""

    def __init__(self):
        self.current_project: Optional[str] = config.NOVEL_NAME or None
        self.current_volume: int = 1
        self.current_chapter: int = 1
        self.current_path: Path = self.get_project_dir(self.current_project)
        self._load_state()

    def _load_state(self):
        if not CONFIG_FILE.exists():
            return
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return

        # An explicit NOVEL_NAME environment variable remains authoritative.
        if not (os.getenv("NOVEL_NAME") or "").strip():
            stored_project = str(state.get("current_project") or "").strip()
            self.current_project = stored_project or self.current_project
        self.current_volume = int(state.get("current_volume") or 1)
        self.current_chapter = int(state.get("current_chapter") or 1)

        project_root = self.get_project_dir(self.current_project)
        stored_path = Path(str(state.get("current_path") or project_root))
        try:
            stored_path.resolve().relative_to(project_root.resolve())
            self.current_path = stored_path
        except (OSError, ValueError):
            self.current_path = project_root

        config.set_active_novel(self.current_project, ensure=False)

    def _save_state(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        state = {
            "current_project": self.current_project,
            "current_volume": self.current_volume,
            "current_chapter": self.current_chapter,
            "current_path": str(self.current_path),
        }
        with CONFIG_FILE.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)

    def _activate(self, name: Optional[str]):
        self.current_project = name or None
        self.current_volume = 1
        self.current_chapter = 1
        self.current_path = self.get_project_dir(self.current_project)
        config.set_active_novel(self.current_project, ensure=True)
        self._save_state()

        # These imports are delayed to avoid startup cycles.
        from core.context_assembler import reset_assembler
        from core.runtime import reset_runtime

        reset_assembler()
        reset_runtime()

    def create_project(self, name: str, logline: str = "") -> bool:
        name = _validate_project_name(name)
        if name.lower() == DEFAULT_PROJECT_NAME:
            raise ValueError("项目名 default 为默认工作区保留名称")
        project_dir = self.get_project_dir(name)
        if project_dir.exists():
            return False

        for subdir in ("settings", "volumes", "manuscripts", "memory", "batch_jobs"):
            (project_dir / subdir).mkdir(parents=True, exist_ok=True)

        metadata = {
            "name": name,
            "logline": logline,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with (project_dir / "project.json").open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)

        self._activate(name)
        return True

    def switch_project(self, name: str) -> bool:
        name = _validate_project_name(name)
        if name.lower() == DEFAULT_PROJECT_NAME:
            self._activate(None)
            return True
        if not self.get_project_dir(name).exists():
            return False
        self._activate(name)
        return True

    def list_projects(self) -> List[str]:
        projects = []
        for directory in PROJECT_ROOT.glob(".novel_*"):
            if not directory.is_dir() or directory.name in {
                ".novel_cli_config",
                ".novel_projects",
            }:
                continue
            projects.append(directory.name.removeprefix(".novel_"))
        prefix = [DEFAULT_PROJECT_NAME] if (PROJECT_ROOT / ".novel").is_dir() else []
        return prefix + sorted(projects)

    def delete_project(self, name: str) -> bool:
        name = _validate_project_name(name)
        if name.lower() == DEFAULT_PROJECT_NAME:
            raise ValueError("不能删除默认工作区")
        project_dir = self.get_project_dir(name)
        if not project_dir.exists():
            return False
        shutil.rmtree(project_dir)
        if self.current_project == name:
            self._activate(None)
        return True

    def get_project_info(self, name: str) -> Optional[dict]:
        if name.lower() == DEFAULT_PROJECT_NAME:
            return {
                "name": DEFAULT_PROJECT_NAME,
                "logline": "",
                "created_at": "N/A",
            }
        metadata_file = self.get_project_dir(name) / "project.json"
        if not metadata_file.exists():
            return None
        try:
            with metadata_file.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None

    def get_project_dir(self, name: Optional[str] = None) -> Path:
        selected = name if name is not None else self.current_project
        return PROJECT_ROOT / (f".novel_{selected}" if selected else ".novel")

    def update_context(self, volume: int | None = None, chapter: int | None = None):
        if volume is not None:
            self.current_volume = volume
        if chapter is not None:
            self.current_chapter = chapter
        self._save_state()

        from core.runtime import get_runtime

        runtime = get_runtime()
        runtime.context.set_current_ids(self.current_volume, self.current_chapter)

    def cd(self, path: str) -> bool:
        candidate = (self.current_path / path).resolve()
        project_root = self.get_project_dir().resolve()
        try:
            candidate.relative_to(project_root)
        except ValueError:
            return False
        if candidate.exists() and candidate.is_dir():
            self.current_path = candidate
            self._save_state()
            return True
        return False


project_manager = ProjectManager()
