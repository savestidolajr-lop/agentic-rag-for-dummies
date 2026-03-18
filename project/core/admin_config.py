"""
Admin-configurable runtime settings.

Persists to admin_config.json in the data directory.
Falls back to code defaults when no override is saved.
"""
import json
import os
from datetime import datetime, timezone

import config

_CONFIG_PATH = os.path.join(config._DATA_DIR, "admin_config.json")

DEFAULTS: dict = {
    "temperature": config.LLM_TEMPERATURE,
    "max_tool_calls": config.MAX_TOOL_CALLS,
    "orchestrator_prompt": "",
    "aggregation_prompt": "",
    "fallback_response_prompt": "",
}

_cache: dict | None = None


def load() -> dict:
    global _cache
    try:
        with open(_CONFIG_PATH) as f:
            stored = json.load(f)
        _cache = {**DEFAULTS, **stored}
    except FileNotFoundError:
        _cache = dict(DEFAULTS)
    except Exception as e:
        print(f"⚠️  admin_config load error: {e}")
        _cache = dict(DEFAULTS)
    return _cache


def get(key: str, fallback=None):
    """Return the stored value for *key*, or *fallback* if not set / empty."""
    global _cache
    if _cache is None:
        load()
    val = _cache.get(key)
    # Empty string means "not overridden — use code default"
    if val is None or val == "":
        return fallback
    return val


def save(updates: dict) -> None:
    global _cache
    if _cache is None:
        load()
    _cache.update(updates)
    _cache["last_updated"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(_CONFIG_PATH) or ".", exist_ok=True)
    with open(_CONFIG_PATH, "w") as f:
        json.dump(_cache, f, indent=2)


def reset() -> None:
    """Delete all overrides and revert to code defaults."""
    global _cache
    _cache = dict(DEFAULTS)
    try:
        os.remove(_CONFIG_PATH)
    except FileNotFoundError:
        pass


def get_all() -> dict:
    global _cache
    if _cache is None:
        load()
    return dict(_cache)
