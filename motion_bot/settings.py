"""Per-user Clarence settings (local machine only).

Each person on their own computer keeps their own Grok API key here.
Keys are never bundled into the app and are not shared across users/machines.

Grok is opt-in: document generation (one-shot / form) never uses the API.
Only conversational chat may call Grok when the user turns it on *and* has
saved their own key.
"""

from __future__ import annotations

import json
import os
import platform
import threading
from pathlib import Path
from typing import Any, Dict, Optional

_LOCK = threading.Lock()

_SETTINGS_KEYS = frozenset(
    {
        "grok_chat_enabled",
        "xai_api_key",
        "migrated_env_key",
    }
)


def _default_settings_dir() -> Path:
    """User-private directory — not inside the project tree."""
    override = os.environ.get("MOTION_BOT_SETTINGS_DIR", "").strip()
    if override:
        return Path(override).expanduser()

    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library" / "Application Support" / "Clarence"
    if system == "Windows":
        base = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
        return Path(base) / "Clarence"
    # Linux / other
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        return Path(xdg) / "clarence"
    return home / ".config" / "clarence"


def settings_path() -> Path:
    explicit = os.environ.get("MOTION_BOT_SETTINGS_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return _default_settings_dir() / "settings.json"


def _defaults() -> Dict[str, Any]:
    env_default = os.environ.get("CLARENCE_GROK_DEFAULT", "").strip().lower()
    grok_on = env_default in ("1", "true", "yes", "on")
    return {
        "grok_chat_enabled": grok_on,
        "xai_api_key": "",
        "migrated_env_key": False,
    }


def load_settings() -> Dict[str, Any]:
    path = settings_path()
    base = _defaults()
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                for k in _SETTINGS_KEYS:
                    if k in data:
                        base[k] = data[k]
        except (OSError, json.JSONDecodeError):
            pass

    base["grok_chat_enabled"] = bool(base.get("grok_chat_enabled"))
    base["xai_api_key"] = str(base.get("xai_api_key") or "").strip()
    base["migrated_env_key"] = bool(base.get("migrated_env_key"))

    # One-time: if this Mac already had XAI_API_KEY in the environment / .env
    # and the user store is empty, adopt it so existing installs keep working.
    # Other people on other computers will not have that env and must add their own.
    if not base["xai_api_key"] and not base["migrated_env_key"]:
        env_key = os.environ.get("XAI_API_KEY", "").strip()
        if env_key:
            base["xai_api_key"] = env_key
            base["migrated_env_key"] = True
            try:
                _write_unlocked(base)
            except OSError:
                pass
        else:
            base["migrated_env_key"] = True
            try:
                _write_unlocked(base)
            except OSError:
                pass

    return base


def _write_unlocked(data: Dict[str, Any]) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Restrictive perms on POSIX
    tmp = path.with_suffix(".tmp")
    payload = {k: data.get(k, _defaults().get(k)) for k in _SETTINGS_KEYS}
    payload["grok_chat_enabled"] = bool(payload.get("grok_chat_enabled"))
    payload["xai_api_key"] = str(payload.get("xai_api_key") or "").strip()
    payload["migrated_env_key"] = bool(payload.get("migrated_env_key"))
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def save_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    with _LOCK:
        current = load_settings()
        if "grok_chat_enabled" in updates:
            current["grok_chat_enabled"] = bool(updates["grok_chat_enabled"])
        if "xai_api_key" in updates:
            key = updates.get("xai_api_key")
            if key is None:
                current["xai_api_key"] = ""
            else:
                current["xai_api_key"] = str(key).strip()
            current["migrated_env_key"] = True
        _write_unlocked(current)
        return dict(current)


def is_grok_chat_enabled() -> bool:
    return bool(load_settings().get("grok_chat_enabled"))


def set_grok_chat_enabled(enabled: bool) -> Dict[str, Any]:
    return save_settings({"grok_chat_enabled": bool(enabled)})


def get_xai_api_key() -> str:
    """Return this machine's private API key (empty if unset)."""
    # Prefer user settings — never rely on a shared project secret for multi-user.
    key = str(load_settings().get("xai_api_key") or "").strip()
    if key:
        return key
    # Dev escape hatch only when CLARENCE_ALLOW_ENV_API_KEY=1
    if os.environ.get("CLARENCE_ALLOW_ENV_API_KEY", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return os.environ.get("XAI_API_KEY", "").strip()
    return ""


def set_xai_api_key(key: str) -> Dict[str, Any]:
    return save_settings({"xai_api_key": (key or "").strip()})


def clear_xai_api_key() -> Dict[str, Any]:
    return save_settings({"xai_api_key": ""})


def has_xai_api_key() -> bool:
    return bool(get_xai_api_key())


def mask_api_key(key: Optional[str] = None) -> str:
    """Safe display form, e.g. xai-…D7Or"""
    k = (key if key is not None else get_xai_api_key()) or ""
    k = k.strip()
    if not k:
        return ""
    if len(k) <= 10:
        return "•" * len(k)
    return f"{k[:4]}…{k[-4:]}"
