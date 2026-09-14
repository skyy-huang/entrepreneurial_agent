"""
脱敏运行记录：支持复现、异常审计和人工边界追踪。

字段设计对照第二阶段手册「日志与可观测性」表的七类最低要求：

    身份   run_id / agent_version / flow / test_id / project_version
    时间   started_at / finished_at / duration_ms / steps[].at
    状态   started / running / success / partial / degraded / failed / cancelled
    行为   steps[] 记录关键节点与工具调用结果
    异常   error_type / error_detail / retry_count
    人机边界 human_interventions[] 记录补充、修改、绕过、重跑
    保护   不记录 API Key、完整敏感数据或不必要个人信息

同时修正一个此前的日志失真问题：LLM 调用失败降级到本地规则后，运行仍被记为
success。降级不是失败，但也不是正常成功，必须让审计者能区分，否则
「失败运行没有被删除或隐瞒」这条自检项无法自证。
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from version import get_version_info

_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
_RUN_FILE = os.path.join(_LOG_DIR, "runs.jsonl")

# 允许的运行状态
STATUS_STARTED = "started"
STATUS_SUCCESS = "success"
STATUS_PARTIAL = "partial"
STATUS_DEGRADED = "degraded"
STATUS_FAILED = "failed"

# 人工干预类型（对应手册「人工补充、修改、确认、绕过和重跑」）
INTERVENTION_KINDS = ("补充", "修改", "确认", "绕过", "重跑", "纠错")

# 需要在写盘前脱敏的模式
_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-***REDACTED***"),
    (re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s,;\"']{6,})"), r"\1***REDACTED***"),
    (re.compile(r"(?i)(authorization\s*[=:]\s*)([^\s,;\"']{6,})"), r"\1***REDACTED***"),
    (re.compile(r"(?i)(token-)([A-Za-z0-9_\-]{4,})"), r"\1***REDACTED***"),
    # 中国大陆手机号
    (re.compile(r"\b1[3-9]\d{9}\b"), "***PHONE***"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_ms(started_at: str) -> int | None:
    try:
        start = datetime.fromisoformat(started_at)
        return int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    except Exception:
        return None


def redact(text: Any, limit: int = 300) -> str:
    """截断并脱敏。任何写入日志的自由文本都必须先经过这里。"""
    value = str(text if text is not None else "").replace("\n", " ")
    for pattern, replacement in _SECRET_PATTERNS:
        value = pattern.sub(replacement, value)
    return value[:limit]


# 兼容旧调用名
def _safe_text(value: Any, limit: int = 300) -> str:
    return redact(value, limit)


def start_run(flow: str, test_id: str = "manual", project_version: str = "") -> dict[str, Any]:
    """开启一次运行记录，自动带上完整版本快照。"""
    info = get_version_info()
    return {
        "run_id": f"run_{uuid.uuid4().hex[:12]}",
        "started_at": _now(),
        "status": STATUS_STARTED,
        "flow": flow,
        "test_id": test_id,
        "project_version": project_version or "未标注",
        # 身份：版本必须可定位，便于 V1/V2 公平比较
        "agent_version": info["agent_version"],
        "agent_stage": info["agent_stage"],
        "prompt_version": info["prompt_version"],
        "kb_version": info["kb_version"],
        "model": info["model"],
        "git_commit": info["git_commit"],
        "steps": [],
        "human_interventions": [],
        "retry_count": 0,
        "degraded": False,
    }


def add_step(run: dict[str, Any], step: str, status: str, detail: str = "") -> None:
    run["steps"].append({"at": _now(), "step": step, "status": status, "detail": redact(detail)})


def mark_degraded(run: dict[str, Any], reason: str) -> None:
    """标记本次运行发生降级（例如 LLM 不可用，改用本地确定性引擎）。"""
    run["degraded"] = True
    run["degraded_reason"] = redact(reason, 200)
    add_step(run, "degrade", "degraded", reason)


def record_intervention(run: dict[str, Any], kind: str, detail: str = "") -> None:
    """记录人工干预。手册要求人工补充、修改、绕过和重跑均可追溯。"""
    run["human_interventions"].append({
        "at": _now(),
        "kind": kind if kind in INTERVENTION_KINDS else "其他",
        "detail": redact(detail),
    })


def record_retry(run: dict[str, Any], detail: str = "") -> None:
    run["retry_count"] = run.get("retry_count", 0) + 1
    add_step(run, "retry", "retrying", detail)


def finish_run(run: dict[str, Any], status: str, error_type: str = "", error_detail: str = "") -> dict[str, Any]:
    """结束运行并落盘。

    status 为 success 但 degraded=True 时自动降级为 degraded 状态，
    避免把「LLM 失败、本地兜底」记录成正常成功。
    """
    if status == STATUS_SUCCESS and run.get("degraded"):
        status = STATUS_DEGRADED

    run["finished_at"] = _now()
    run["duration_ms"] = _duration_ms(run.get("started_at", ""))
    run["status"] = status
    if error_type:
        run["error_type"] = redact(error_type, 80)
    if error_detail:
        run["error_detail"] = redact(error_detail, 300)

    os.makedirs(_LOG_DIR, exist_ok=True)
    with open(_RUN_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(run, ensure_ascii=False) + "\n")
    return run


def iter_runs(limit: int | None = None):
    """按写入顺序读取运行记录，供测试报告与审计使用。"""
    if not os.path.exists(_RUN_FILE):
        return
    with open(_RUN_FILE, "r", encoding="utf-8") as file:
        lines = [line for line in file if line.strip()]
    for line in lines[-limit:] if limit else lines:
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue
