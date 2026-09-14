# -*- coding: utf-8 -*-
"""
生成《02_源代码》快照。

为什么不直接在交付目录里维护一份代码副本：副本会与仓库根目录的实际代码
逐渐不一致，最终导致「提交的源码」和「实际运行的源码」不是同一个东西——
这正是课程手册反复要求避免的版本不可追溯问题。

因此这里生成的是**一次性快照**，并在快照目录写入一份 MANIFEST，
记录生成时间与 git 提交号，使快照可以被追溯到具体版本。

用法：python deliverables/build/copy_source.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEST = os.path.join(_ROOT, "deliverables", "02_源代码")

# 需要收进快照的源码与配置
INCLUDE_FILES = [
    "main.py", "workflows.py", "evidence.py", "knowledge.py",
    "observability.py", "version.py", "storage.py",
    "requirements.txt", ".env.example", "README.md",
]
INCLUDE_DIRS = ["graph", "hypergraph", "prompts", "teacher", "frontend", "tests"]

# 明确排除：密钥、运行时数据、个人环境
EXCLUDE_PATTERNS = ("__pycache__", ".pyc", ".env", "node_modules", ".vscode", "reports")


def should_skip(path: str) -> bool:
    return any(p in path for p in EXCLUDE_PATTERNS)


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5, cwd=_ROOT)
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def copy_tree(src: str, dst: str) -> int:
    count = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not should_skip(os.path.join(root, d))]
        rel = os.path.relpath(root, src)
        target = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target, exist_ok=True)
        for name in files:
            if should_skip(name):
                continue
            shutil.copy2(os.path.join(root, name), os.path.join(target, name))
            count += 1
    return count


def main() -> int:
    if os.path.exists(DEST):
        shutil.rmtree(DEST)
    os.makedirs(DEST, exist_ok=True)

    total = 0
    for name in INCLUDE_FILES:
        src = os.path.join(_ROOT, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(DEST, name))
            total += 1
    for name in INCLUDE_DIRS:
        src = os.path.join(_ROOT, name)
        if os.path.isdir(src):
            total += copy_tree(src, os.path.join(DEST, name))
        else:
            print(f"!! 目录不存在，已跳过：{name}")

    manifest = f"""# 02_源代码　快照说明

本目录是 Agent 与课程项目的**源码快照**，用于提交归档。

| 项目 | 值 |
|------|-----|
| 生成时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| git 提交号 | `{git_commit()}` |
| 文件总数 | {total} |

## 权威来源

**仓库根目录才是权威源码**，本目录仅为某一次的快照副本。
如需重新生成，请运行：

```bash
python deliverables/build/copy_source.py
```

## 本快照不包含的内容（及其原因）

| 未包含 | 原因 |
|--------|------|
| `.env` | 含 API 密钥，禁止进入提交物 |
| `storage/*.json` | 运行时产生的会话与用户数据 |
| `logs/runs.jsonl` | 运行时日志，含学生对话记录 |
| `data/` | 挑战杯案例库（体积较大，且非本组原创） |
| `__pycache__` / `.pyc` | Python 编译缓存 |
| `deliverables/` | 交付物本身，不属于源码 |

## 目录结构

```
02_源代码/
├── main.py              FastAPI 入口，全部 HTTP 接口
├── workflows.py         F1 理论学习 / F3 评审反馈（确定性引擎为主）
├── evidence.py          证据边界引擎：F/I/H/S 分类、否定感知
├── knowledge.py         F1 概念知识库（13 个词条）
├── observability.py     运行日志：七类字段、脱敏、降级状态、人工干预
├── version.py           版本快照（供 /api/version 与日志使用）
├── storage.py           会话与用户的文件持久化
├── graph/               LangGraph 编排：extractor → critic → coach
├── hypergraph/          超图规则引擎、评分引擎、证据检查
├── prompts/             各 Agent 角色的系统提示词（含证据边界护栏）
├── teacher/             教师端看板聚合
├── frontend/            学生端 / 教师端页面
└── tests/               统一测试集 U1—U6 与组内回归测试
```

## 运行方式

见 `README.md` 与《07_用户手册》。
"""
    with open(os.path.join(DEST, "MANIFEST.md"), "w", encoding="utf-8") as f:
        f.write(manifest)

    print(f"已生成源码快照：{DEST}")
    print(f"文件数：{total}　git 提交号：{git_commit()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
