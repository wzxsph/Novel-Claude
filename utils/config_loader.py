"""
Config Loader - Unified configuration management

Loads config.json and provides access to all core variables.
"""

import json
from pathlib import Path

# Default config path (project root)
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

# Global config cache
_config_cache: dict[Path, dict] = {}


def load_config(config_path: str = None) -> dict:
    """Load configuration from config.json"""
    global _config_cache

    path = (Path(config_path) if config_path else DEFAULT_CONFIG_PATH).resolve()
    if path in _config_cache:
        return _config_cache[path]

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    if not isinstance(loaded, dict):
        raise ValueError(f"Config root must be a JSON object: {path}")
    _config_cache[path] = loaded

    return loaded


def get_config(key: str = None, default=None):
    """
    Get config value by key.

    Args:
        key: Dot-notation key like "writing.target_word_count"
            If None, returns entire config
        default: Default value if key not found

    Returns:
        Config value or default
    """
    config = load_config()

    if key is None:
        return config

    # Parse dot notation
    keys = key.split('.')
    value = config

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default

    return value


def reload_config():
    """Force reload of config (useful for testing)"""
    global _config_cache
    _config_cache.clear()
    return load_config()
