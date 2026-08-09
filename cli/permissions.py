"""Permission system for Novel-Claude CLI."""
import json
from enum import Enum
from pathlib import Path

from utils import config

# Permission levels
class PermissionLevel(Enum):
    NONE = 0        # No file operations
    READ = 1        # Can read .novel workspace only
    WRITE = 2       # Can read/write .novel workspace
    FULL = 3        # Can execute any file operation


class PermissionManager:
    """Manages file operation permissions for the CLI."""

    def __init__(self):
        self.level = PermissionLevel.READ  # Default to READ
        self.config_file = (
            config.PROJECT_ROOT / ".novel_cli_config" / "permissions.json"
        )
        self._load()

    @staticmethod
    def _is_in_workspace(path: Path) -> bool:
        candidate = path if path.is_absolute() else config.PROJECT_ROOT / path
        try:
            candidate.resolve().relative_to(Path(config.NOVEL_DIR).resolve())
            return True
        except ValueError:
            return False

    def _load(self):
        """Load permissions from config."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    level = data.get('level', 'READ')
                    self.level = PermissionLevel[level]
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        """Save permissions to config."""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump({'level': self.level.name}, f, ensure_ascii=False, indent=2)

    def set_level(self, level: PermissionLevel):
        """Set permission level."""
        self.level = level
        self._save()

    def can_read(self, path: Path) -> bool:
        """Check if read is allowed for path."""
        if self.level == PermissionLevel.FULL:
            return True
        if self.level == PermissionLevel.NONE:
            return False
        return self._is_in_workspace(path)

    def can_write(self, path: Path) -> bool:
        """Check if write is allowed for path."""
        if self.level == PermissionLevel.FULL:
            return True
        if self.level in [PermissionLevel.NONE, PermissionLevel.READ]:
            return False
        return self._is_in_workspace(path)

    def check_read(self, path: Path) -> bool:
        """Raise error if read not allowed."""
        if not self.can_read(path):
            raise PermissionError(f"Read not allowed for: {path}")
        return True

    def check_write(self, path: Path) -> bool:
        """Raise error if write not allowed."""
        if not self.can_write(path):
            raise PermissionError(f"Write not allowed for: {path}")
        return True


# Global instance
permissions = PermissionManager()
