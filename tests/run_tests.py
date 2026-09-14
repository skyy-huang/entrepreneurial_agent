# -*- coding: utf-8 -*-
"""
统一测试运行器 U1—U6

用法：
    python tests/run_tests.py                    # 默认打到 http://127.0.0.1:8000
    python tests/run_tests.py --base http://127.0.0.1:8121
    python tests/run_tests.py --label V2-修订后   # 写入报告，便于 V1/V2 对比

输出：
    tests/reports/<label>_<时间戳>.json    机器可读的完整结果
    tests/reports/<label>_<时间戳>.md      人类可读的自测试报告

设计说明：
- 结果**全部保留**，包括失败项。手册明确要求「每次运行记录人工干预、失败、
  重试和异常，不把失败样本删除」，因此运行器不做任何过滤。
- 报告头部带 Agent 版本、git 提交号与运行时间，使结论能回到版本和运行编号。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.unified import UNIFIED_TESTS  # noqa: E402
from custom.project_tests import CUSTOM_TESTS  # noqa: E402

REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def _login(client: httpx.Client, student_id: str) -> str:
    resp = client.post("/api/session/start", json={"student_id": student_id, "password": "test"})
    resp.raise_for_status()
    return resp.json()["session_id"]


def _run_u1(client: httpx.Client) -> tuple[dict, dict]:
    test = next(t for t in UNIFIED_TESTS if t["id"] == "U1")
    resp = client.post("/api/learn", json={"question": test["test_input"], "test_id": "U1"})
    resp.raise_for_status()
    return resp.json(), {}


def _run_u2(client: httpx.Client) -> tuple[dict, dict]:
    test = next(t for t in UNIFIED_TESTS if t["id"] == "U2")
    resp = client.post("/api/evidence/classify", json={"text": test["test_input"]})
    resp.raise_for_status()
    return resp.json(), {}


def _run_u3_u4(client: httpx.Client) -> tuple[dict, dict]:
    """U4 依赖 U3 建立的会话上下文，必须按顺序在同一会话内执行。"""
    u3 = next(t for t in UNIFIED_TESTS if t["id"] == "U3")
    u4 = next(t for t in UNIFIED_TESTS if t["id"] == "U4")

    session_id = _login(client, f"unified_{int(time.time())}")
    r3 = client.post("/api/chat", json={"session_id": session_id, "message": u3["test_input"]})
    r3.raise_for_status()
    result3 = r3.json()

    r4 = client.post("/api/chat", json={"session_id": session_id, "message": u4["test_input"]})
    r4.raise_for_status()
    result4 = r4.json()
    return result3, {"u4_result": result4, "session_id": session_id}


def _run_u5(client: httpx.Client) -> tuple[dict, dict]:
    test = next(t for t in UNIFIED_TESTS if t["id"] == "U5")
    resp = client.post("/api/review", json={"project_text": test["test_input"], "test_id": "U5"})
    resp.raise_for_status()
    return resp.json(), {}


def _run_u6(client: httpx.Client) -> tuple[dict, dict]:
    """U6：逐项触发异常，检查是否如实报错。"""
    cases = []

    # 用一个真实会话，把「文件类型不合法」与其他错误隔离开
    session_id = _login(client, f"u6_{int(time.time())}")

    # 1) 不支持的文件类型
    r = client.post(
        "/api/upload",
        data={"session_id": session_id},
        files={"file": ("malware.exe", b"MZ\x90\x00 binary", "application/octet-stream")},
    )
    cases.append({"name": "不支持的文件类型", "status": r.status_code,
                  "detail": _detail(r)})

    # 2) 合法扩展名但内容无法解析（伪造的空 PDF）
    r = client.post(
        "/api/upload",
        data={"session_id": session_id},
        files={"file": ("broken.pdf", b"not a real pdf", "application/pdf")},
    )
    cases.append({"name": "文件无法解析", "status": r.status_code, "detail": _detail(r)})

    # 3) 会话不存在
    r = client.post("/api/chat", json={"session_id": "does-not-exist", "message": "你好"})
    cases.append({"name": "会话不存在", "status": r.status_code, "detail": _detail(r)})

    # 4) 超长消息
    r = client.post("/api/chat", json={"session_id": session_id, "message": "长" * 4000})
    cases.append({"name": "输入超长", "status": r.status_code, "detail": _detail(r)})

    # 5) 评审输入过短
    r = client.post("/api/review", json={"project_text": "太短"})
    cases.append({"name": "评审输入过短", "status": r.status_code, "detail": _detail(r)})

    # 6) 空问题
    r = client.post("/api/learn", json={"question": "   "})
    cases.append({"name": "学习问题为空", "status": r.status_code, "detail": _detail(r)})

    return {"cases": cases}, {}


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict):
            return str(body.get("detail") or body.get("message") or "")[:120]
        return str(body)[:120]
    except Exception:
        return resp.text[:120]


RUNNERS = {
    "U1": _run_u1,
    "U2": _run_u2,
    "U3": _run_u3_u4,   # U3 与 U4 共用一次会话
    "U5": _run_u5,
    "U6": _run_u6,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="运行统一测试集 U1—U6")
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="服务地址")
    parser.add_argument("--label", default="V2", help="报告标签，用于 V1/V2 对比")
    parser.add_argument("--suite", default="both", choices=["unified", "custom", "both"],
                        help="unified=课程统一测试集 U1—U6；custom=组内回归测试；both=全部")
    args = parser.parse_args()

    started = datetime.now()
    report = {
        "label": args.label,
        "base_url": args.base,
        "started_at": started.isoformat(),
        "results": [],
        "summary": {},
    }

    with httpx.Client(base_url=args.base, timeout=180.0) as client:
        # 版本快照：结论必须能回到 Agent 版本与提交号
        try:
            report["version"] = client.get("/api/version").json()
        except Exception as exc:
            report["version"] = {"error": f"无法获取版本信息：{exc}"}
            print(f"!! 无法连接 {args.base}：{exc}")
            return 2

        print(f"Agent 版本：{report['version'].get('agent_version')}  "
              f"提交号：{report['version'].get('git_commit')}  "
              f"模型：{report['version'].get('model')}")
        print("=" * 72)

        u3_result, u3_extra = None, {}
        unified_tests = UNIFIED_TESTS if args.suite in ("unified", "both") else []
        for test in unified_tests:
            tid = test["id"]
            print(f"\n[{tid}] {test['name']}")
            entry = {"id": tid, "name": test["name"], "flow": test["flow"],
                     "focus": test["focus"], "checks": [], "passed": 0, "total": 0}

            try:
                # U4 复用 U3 建立的会话上下文，不单独发起请求
                if tid == "U4":
                    raw = u3_extra.get("u4_result")
                    entry["session_id"] = u3_extra.get("session_id", "")
                    if raw is None:
                        raise RuntimeError("U3 未成功建立会话上下文，U4 无法执行")
                else:
                    raw, extra = RUNNERS[tid](client)
                    if tid == "U3":
                        u3_result, u3_extra = raw, extra
                        extra = {}

                if tid == "U6":
                    checks = test["checker"](raw.get("cases", []))
                    entry["checks"] = [{"name": n, "passed": p, "detail": d} for n, p, d in checks]
                    entry["raw"] = raw
                    entry["passed"] = sum(1 for _, p, _ in checks if p)
                    entry["total"] = len(checks)
                    for name, ok, detail in checks:
                        print(f"   {'PASS' if ok else 'FAIL'}  {name}  {detail}")
                    report["results"].append(entry)
                    continue

                checks = test["checker"](raw)
                entry["checks"] = [{"name": n, "passed": p, "detail": d} for n, p, d in checks]
                entry["raw"] = raw
                entry["passed"] = sum(1 for _, p, _ in checks if p)
                entry["total"] = len(checks)
                for name, ok, detail in checks:
                    print(f"   {'PASS' if ok else 'FAIL'}  {name}  {detail}")
            except Exception as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
                entry["total"] = 1
                print(f"   ERROR {entry['error']}")
            report["results"].append(entry)

        # ── 组内回归测试 ────────────────────────────────────────
        if args.suite in ("custom", "both"):
            print("\n" + "=" * 72)
            print("组内回归测试（tests/custom）")
            print("=" * 72)
            for test in CUSTOM_TESTS:
                entry = {
                    "id": test["id"], "name": test["name"], "flow": test["kind"],
                    "focus": f"回归：{test.get('regression_of', '-')}",
                    "checks": [], "passed": 0, "total": 0, "suite": "custom",
                }
                try:
                    checks = (test["runner"](client) if test["kind"] == "http"
                              else test["runner"]({}))
                    entry["checks"] = [{"name": n, "passed": p, "detail": d} for n, p, d in checks]
                    entry["passed"] = sum(1 for _, p, _ in checks if p)
                    entry["total"] = len(checks)
                    status = "PASS" if entry["passed"] == entry["total"] else "FAIL"
                    print(f"\n[{test['id']}] {test['name']}  -> {status}")
                    for name, ok, detail in checks:
                        print(f"   {'PASS' if ok else 'FAIL'}  {name}  {detail}")
                except Exception as exc:
                    entry["error"] = f"{type(exc).__name__}: {exc}"
                    entry["total"] = 1
                    print(f"\n[{test['id']}] {test['name']}  -> ERROR {entry['error']}")
                report["results"].append(entry)

    report["finished_at"] = datetime.now().isoformat()
    total = sum(r["total"] for r in report["results"])
    passed = sum(r["passed"] for r in report["results"])
    report["summary"] = {
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "duration_sec": round((datetime.now() - started).total_seconds(), 1),
    }

    os.makedirs(REPORT_DIR, exist_ok=True)
    stamp = started.strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(REPORT_DIR, f"{args.label}_{stamp}.json")
    md_path = os.path.join(REPORT_DIR, f"{args.label}_{stamp}.md")

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as file:
        file.write(_render_markdown(report))

    print("\n" + "=" * 72)
    print(f"合计 {passed}/{total} 项通过（{report['summary']['pass_rate'] * 100:.1f}%）"
          f"，耗时 {report['summary']['duration_sec']}s")
    print(f"报告：{md_path}")
    print(f"原始：{json_path}")
    return 0 if passed == total else 1


def _render_markdown(report: dict) -> str:
    v = report.get("version", {})
    lines = [
        f"# 自测试报告（{report['label']}）",
        "",
        "## 运行环境",
        "",
        "| 项目 | 值 |",
        "|------|-----|",
        f"| 标签 | {report['label']} |",
        f"| Agent 版本 | {v.get('agent_version', '-')} |",
        f"| 提示词版本 | {v.get('prompt_version', '-')} |",
        f"| 知识库版本 | {v.get('kb_version', '-')} |",
        f"| git 提交号 | {v.get('git_commit', '-')} |",
        f"| 工作区有未提交改动 | {v.get('git_dirty', '-')} |",
        f"| 模型 | {v.get('model', '-')} |",
        f"| 服务地址 | {report['base_url']} |",
        f"| 开始时间 | {report['started_at']} |",
        f"| 结束时间 | {report.get('finished_at', '-')} |",
        "",
        f"## 结果汇总",
        "",
        f"通过 **{report['summary']['passed']}/{report['summary']['total']}** 项"
        f"（{report['summary']['pass_rate'] * 100:.1f}%），"
        f"耗时 {report['summary']['duration_sec']} 秒。",
        "",
        "| 用例 | 名称 | 通过/总数 |",
        "|------|------|-----------|",
    ]
    for r in report["results"]:
        lines.append(f"| {r['id']} | {r['name']} | {r['passed']}/{r['total']} |")

    lines += ["", "## 逐项结果", ""]
    for r in report["results"]:
        lines.append(f"### {r['id']} {r['name']}")
        lines.append("")
        lines.append(f"**观察重点**：{r['focus']}")
        lines.append("")
        if r.get("error"):
            lines.append(f"> 运行出错：{r['error']}")
            lines.append("")
            continue
        lines.append("| 校验项 | 结果 | 证据 |")
        lines.append("|--------|------|------|")
        for c in r["checks"]:
            mark = "通过" if c["passed"] else "**未通过**"
            detail = str(c.get("detail", "")).replace("|", "\\|")[:80]
            lines.append(f"| {c['name']} | {mark} | {detail} |")
        lines.append("")

    failed = [c for r in report["results"] for c in r["checks"] if not c["passed"]]
    lines += ["## 未通过项与后续动作", ""]
    if failed:
        lines.append("以下项目未通过，按要求**未被删除**，作为 V2 的待改进清单：")
        lines.append("")
        for c in failed:
            lines.append(f"- {c['name']}（{c.get('detail', '')}）")
    else:
        lines.append("全部通过。仍建议在跨组测试中补充外部视角，避免自测偏差。")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
