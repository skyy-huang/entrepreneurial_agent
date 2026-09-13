"""脱敏运行记录：支持复现、异常审计和人工边界追踪。"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
_RUN_FILE = os.path.join(_LOG_DIR, "runs.jsonl")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\n", " ")
    return text[:limit]


def start_run(flow: str, test_id: str = "manual") -> dict[str, Any]:
    return {"run_id": f"run_{uuid.uuid4().hex[:12]}", "started_at": _now(), "status": "started", "flow": flow, "test_id": test_id, "version": "V2", "steps": []}


def add_step(run: dict[str, Any], step: str, status: str, detail: str = "") -> None:
    run["steps"].append({"at": _now(), "step": step, "status": status, "detail": _safe_text(detail)})


def finish_run(run: dict[str, Any], status: str, error_type: str = "") -> dict[str, Any]:
    run["finished_at"] = _now()
    run["status"] = status
    if error_type:
        run["error_type"] = _safe_text(error_type, 80)
    os.makedirs(_LOG_DIR, exist_ok=True)
    with open(_RUN_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(run, ensure_ascii=False) + "\n")
    return run
