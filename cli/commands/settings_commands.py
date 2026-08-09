"""Non-secret settings inspection and env-file updates."""

from typing import Any, Dict, List

from dotenv import set_key

from utils import config


def handle(args: List[str]) -> Dict[str, Any]:
    return {"message": "Use: settings show, settings set <key> <value>"}


def show(args: List[str]) -> Dict[str, Any]:
    if args:
        return {"error": "Usage: settings show"}
    output = [
        "Current Configuration:",
        f"  LLM_PROVIDER: {config.LLM_PROVIDER}",
        f"  LLM_BASE_URL: {config.LLM_BASE_URL}",
        f"  MODEL_ID: {config.MODEL_ID}",
        f"  FLASH_MODEL_ID: {config.FLASH_MODEL_ID}",
        f"  CHAT_KEY_CONFIGURED: {'yes' if config.LLM_API_KEY else 'no'}",
        f"  ZHIPU_KEY_CONFIGURED: {'yes' if config.ZHIPU_API_KEY else 'no'}",
        f"  NOVEL_NAME: {config.NOVEL_NAME or '(default)'}",
        f"  NOVEL_DIR: {config.NOVEL_DIR}",
    ]
    return {"message": "\n".join(output)}


def set_value(args: List[str]) -> Dict[str, Any]:
    if len(args) < 2:
        return {"error": "Usage: settings set <key> <value>"}
    key = args[0].strip()
    value = " ".join(args[1:])
    if not key or not key.replace("_", "").isalnum():
        return {"error": "Invalid environment key."}
    try:
        set_key(str(config.ENV_FILE), key, value)
    except Exception as exc:
        return {"error": f"settings set failed: {exc}"}

    secret = any(token in key.upper() for token in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
    shown = "<updated>" if secret else value
    return {"message": f"{key} set to {shown}. Restart the CLI to apply it."}
