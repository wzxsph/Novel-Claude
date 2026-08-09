"""
Chapter State Manager - Progressive saving and state machine management

Tracks chapter generation state and enables resume from interruption.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from utils import config


# Chapter states
STATE_PENDING = "pending"
STATE_GENERATING = "generating"
STATE_COMPLETED = "completed"
STATE_FAILED = "failed"


class ChapterState:
    """State for a single chapter"""
    def __init__(self, volume_id: int, chapter_id: int):
        self.volume_id = volume_id
        self.chapter_id = chapter_id
        self.state = STATE_PENDING
        self.generated_chars = 0
        self.last_updated = None
        self.error_message = ""
        self.retry_count = 0

    def to_dict(self) -> dict:
        return {
            "volume_id": self.volume_id,
            "chapter_id": self.chapter_id,
            "state": self.state,
            "generated_chars": self.generated_chars,
            "last_updated": self.last_updated,
            "error_message": self.error_message,
            "retry_count": self.retry_count
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChapterState":
        volume_id = int(data["volume_id"])
        chapter_id = int(data["chapter_id"])
        if volume_id <= 0 or chapter_id <= 0:
            raise ValueError("卷章编号必须为正整数")
        state = cls(volume_id, chapter_id)
        saved_state = data.get("state", STATE_PENDING)
        state.state = (
            saved_state
            if saved_state
            in {STATE_PENDING, STATE_GENERATING, STATE_COMPLETED, STATE_FAILED}
            else STATE_PENDING
        )
        state.generated_chars = max(0, int(data.get("generated_chars", 0)))
        state.last_updated = data.get("last_updated")
        state.error_message = str(data.get("error_message", ""))
        state.retry_count = max(0, int(data.get("retry_count", 0)))
        return state


class ChapterStateManager:
    """Manages states for all chapters in a volume"""

    def __init__(self, volume_id: int):
        self.volume_id = volume_id
        self.state_file = Path(config.VOLUMES_DIR) / f"vol_{volume_id:02d}_chapter_states.json"
        self.chapters: Dict[int, ChapterState] = {}
        self._load()

    def _load(self):
        """Load states from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                return
            if not isinstance(data, dict):
                return
            for chapter_data in data.get("chapters", []):
                try:
                    state = ChapterState.from_dict(chapter_data)
                except (KeyError, TypeError, ValueError):
                    continue
                if state.volume_id == self.volume_id:
                    self.chapters[state.chapter_id] = state

    def _save(self):
        """Save states to file"""
        data = {
            "volume_id": self.volume_id,
            "last_updated": datetime.now().isoformat(),
            "chapters": [s.to_dict() for s in self.chapters.values()]
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = self.state_file.with_suffix(".json.tmp")
        with open(temporary_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temporary_file.replace(self.state_file)

    def get_state(self, chapter_id: int) -> ChapterState:
        """Get or create state for a chapter"""
        chapter_id = int(chapter_id)
        if chapter_id <= 0:
            raise ValueError("章号必须为正整数")
        if chapter_id not in self.chapters:
            self.chapters[chapter_id] = ChapterState(self.volume_id, chapter_id)
        return self.chapters[chapter_id]

    def set_state(self, chapter_id: int, state: str, error_message: str = ""):
        """Update chapter state"""
        s = self.get_state(chapter_id)
        s.state = state
        s.last_updated = datetime.now().isoformat()
        if error_message:
            s.error_message = error_message
        if state == STATE_FAILED:
            s.retry_count += 1
        self._save()

    def update_progress(self, chapter_id: int, chars: int):
        """Update generation progress (for progressive saving)"""
        s = self.get_state(chapter_id)
        s.generated_chars = max(0, int(chars))
        s.last_updated = datetime.now().isoformat()
        self._save()

    def mark_completed(self, chapter_id: int):
        """Mark chapter as completed"""
        self.set_state(chapter_id, STATE_COMPLETED)

    def mark_failed(self, chapter_id: int, error: str):
        """Mark chapter as failed"""
        self.set_state(chapter_id, STATE_FAILED, error)

    def mark_generating(self, chapter_id: int):
        """Mark chapter as currently generating"""
        self.set_state(chapter_id, STATE_GENERATING)

    def get_pending_chapters(self) -> List[int]:
        """Get list of chapters that need to be generated"""
        pending = []
        for ch_id, state in sorted(self.chapters.items()):
            if state.state in [STATE_PENDING, STATE_FAILED]:
                pending.append(ch_id)
        return pending

    def get_completed_count(self) -> int:
        """Get count of completed chapters"""
        return sum(1 for s in self.chapters.values() if s.state == STATE_COMPLETED)

    def get_failed_count(self) -> int:
        """Get count of failed chapters"""
        return sum(1 for s in self.chapters.values() if s.state == STATE_FAILED)


def get_state_manager(volume_id: int) -> ChapterStateManager:
    """Get or create state manager for a volume"""
    return ChapterStateManager(volume_id)
