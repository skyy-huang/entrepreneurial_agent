"""
简单的文件持久化存储
将 sessions 字典序列化为 JSON 文件，避免重启丢失数据
"""
import json
import os
from typing import Dict, Any

_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage")
_SESSIONS_FILE = os.path.join(_STORAGE_DIR, "sessions.json")
_USERS_FILE = os.path.join(_STORAGE_DIR, "users.json")


def load_sessions() -> Dict[str, Any]:
    os.makedirs(_STORAGE_DIR, exist_ok=True)
    if os.path.exists(_SESSIONS_FILE):
        try:
            with open(_SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_sessions(sessions: Dict[str, Any]) -> None:
    os.makedirs(_STORAGE_DIR, exist_ok=True)
    with open(_SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)

def load_users() -> Dict[str, Any]:
    os.makedirs(_STORAGE_DIR, exist_ok=True)
    if os.path.exists(_USERS_FILE):
        try:
            with open(_USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_users(users: Dict[str, Any]) -> None:
    os.makedirs(_STORAGE_DIR, exist_ok=True)
    with open(_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

