"""
Agent 版本信息

手册第二阶段要求「为每个优化目标建立问题编号，并关联代码提交和测试用例」，
第三阶段要求保存「Agent V2 代码提交号或不可变版本标签」「提示词、知识库、
工具和关键配置快照」，并且最终结论要能回到材料版本、运行编号和证据来源。

因此每次运行记录都必须带上下面的版本信息，而不是只写一个笼统的 "V2"。
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache

# 语义化版本：每次冻结 V2 时手工递增，与 git 提交号互相印证
AGENT_VERSION = "2.1.0"
AGENT_STAGE = "V2"

# 提示词与知识库版本：修改 prompts/ 或 hypergraph/rules.py、knowledge.py 时递增
PROMPT_VERSION = "2.1.0"
KB_VERSION = "2.1.0"

# 默认模型（DeepSeek 兼容 OpenAI 协议）
DEFAULT_MODEL = "deepseek-chat"


@lru_cache(maxsize=1)
def _git_commit() -> str:
    """读取当前提交号。取不到时返回 unknown，不抛异常。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


@lru_cache(maxsize=1)
def _git_dirty() -> bool:
    """工作区是否有未提交改动——有改动时提交号不能单独作为版本凭证。"""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if result.returncode == 0:
            return bool(result.stdout.strip())
    except Exception:
        pass
    return False


def model_name() -> str:
    return os.getenv("MODEL_NAME", DEFAULT_MODEL)


def llm_configured() -> bool:
    """是否配置了可用的 API Key（不代表余额可用）。"""
    key = os.getenv("DEEPSEEK_API_KEY", "")
    return bool(key and key != "your_deepseek_api_key_here")


def get_version_info() -> dict:
    """供 /api/version 与运行日志使用的版本快照。"""
    return {
        "agent_version": AGENT_VERSION,
        "agent_stage": AGENT_STAGE,
        "prompt_version": PROMPT_VERSION,
        "kb_version": KB_VERSION,
        "model": model_name(),
        "llm_configured": llm_configured(),
        "git_commit": _git_commit(),
        "git_dirty": _git_dirty(),
        "version_note": (
            "git_dirty=true 表示工作区存在未提交改动，此时 git_commit 不能单独作为版本凭证，"
            "需要通过目录快照或压缩包一并留存。" if _git_dirty() else ""
        ),
    }
