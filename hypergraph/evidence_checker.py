"""
证据检查器（Phase 1 — 非 LLM）
自动对照 RUBRIC_ITEMS.required_evidence 与 extracted_data，
检查项目材料中缺少哪些关键证据。

不调用任何 LLM，延迟 ≈ 0ms，成本 ≈ 0。
"""
import logging
from typing import Dict, Any, List

from .rules import RUBRIC_ITEMS

logger = logging.getLogger("entrepreneurial_agent.evidence_checker")

# ── 证据类型 → 触发关键词映射 ─────────────────────────────────
# 如果对话/提取数据中包含这些关键词，则认为对应证据"可能存在"
_EVIDENCE_KEYWORDS: Dict[str, List[str]] = {
    "User Interview": [
        "访谈", "用户反馈", "用户说", "调研", "走访", "面谈",
        "受访者", "采访", "深度访谈", "interview",
    ],
    "Survey": [
        "问卷", "调查", "样本", "回收", "survey", "填写",
        "有效问卷", "发放",
    ],
    "Interview Quotes": [
        "用户原话", "反馈原文", "用户表示", "受访者说",
        "引用", "quote", "原话",
    ],
    "Behavioral Data": [
        "行为数据", "点击率", "转化率", "留存率", "DAU", "MAU",
        "用户行为", "使用数据", "埋点", "analytics",
    ],
    "Technical Roadmap": [
        "技术路线", "架构图", "技术方案", "开发计划",
        "roadmap", "技术栈", "系统架构",
    ],
    "Resource Match": [
        "团队", "人员", "负责人", "技术人员", "全职",
        "资源", "投入", "成员",
    ],
    "POC/Prototype": [
        "原型", "MVP", "demo", "POC", "样品", "测试版",
        "概念验证", "prototype", "最小可行",
    ],
    "Business Model Canvas": [
        "商业模式", "画布", "BMC", "canvas", "盈利模式",
        "商业闭环", "商业逻辑",
    ],
    "Unit Economics": [
        "单位经济", "LTV", "CAC", "毛利", "客单价",
        "获客成本", "客户终身价值", "ARPU", "unit economics",
    ],
    "TAM/SAM/SOM breakdown": [
        "TAM", "SAM", "SOM", "可达市场", "目标市场规模",
        "自下而上", "bottom-up", "市场规模估算",
    ],
    "Competitor Table": [
        "竞品", "竞争对手", "竞品分析", "竞品矩阵",
        "对标", "替代方案", "competitor",
    ],
    "Unit Economics Table": [
        "单位经济", "LTV", "CAC", "毛利率", "边际成本",
        "单笔交易", "unit economics",
    ],
    "Cash Flow Projection": [
        "现金流", "收支预测", "月度预算", "烧钱速率",
        "burn rate", "资金链", "盈亏平衡", "BEP",
    ],
    "Comparison Matrix": [
        "对比矩阵", "竞品对比", "差异化对比", "功能对比",
        "competitor matrix", "对比表",
    ],
    "Patent/Paper (for tech projects)": [
        "专利", "论文", "SCI", "EI", "发明", "实用新型",
        "软著", "著作权", "patent", "paper",
    ],
    "Team Profile with roles": [
        "团队介绍", "成员分工", "团队构成", "负责人",
        "CEO", "CTO", "核心团队", "team",
    ],
    "Milestone Chart": [
        "里程碑", "时间线", "甘特图", "进度计划",
        "milestone", "阶段目标", "交付节点",
    ],
    "Pitch Deck": [
        "路演", "PPT", "演示文稿", "pitch", "deck",
        "展示材料", "项目介绍", "BP",
    ],
    "Demo/Prototype Video": [
        "演示视频", "demo视频", "产品演示", "录屏",
        "操作演示", "demo video",
    ],
}


def check_evidence_gaps(
    extracted_data: Dict[str, Any],
    conversation_text: str = "",
) -> Dict[str, Any]:
    """
    Phase 1 证据检查器。
    输入：提取到的结构化要素 + 对话文本。
    输出：{
        "rubric_evidence_status": {
            "R1": {
                "required": ["User Interview", "Survey"],
                "found": ["User Interview"],
                "missing": ["Survey"],
                "coverage": 0.5,
            },
            ...
        },
        "overall_coverage": 0.45,
        "critical_missing": ["Survey", "Unit Economics", ...],
    }
    """
    # 将所有可搜索文本合并
    summary = extracted_data.get("summary", {})
    all_text = conversation_text + " " + " ".join(
        str(v) for v in summary.values() if v
    )
    # 加入节点 label
    for node in extracted_data.get("nodes", []):
        all_text += " " + node.get("label", "")
    # 加入超边 label
    for edge in extracted_data.get("hyperedges", []):
        all_text += " " + edge.get("label", "")

    all_text_lower = all_text.lower()

    rubric_status: Dict[str, Dict[str, Any]] = {}
    all_missing: List[str] = []
    total_required = 0
    total_found = 0

    for item in RUBRIC_ITEMS:
        rid = item["id"]
        required = item.get("required_evidence", [])
        found = []
        missing = []

        for evidence_type in required:
            keywords = _EVIDENCE_KEYWORDS.get(evidence_type, [])
            is_found = False
            for kw in keywords:
                if kw.lower() in all_text_lower:
                    is_found = True
                    break

            if is_found:
                found.append(evidence_type)
            else:
                missing.append(evidence_type)
                all_missing.append(evidence_type)

        total_required += len(required)
        total_found += len(found)

        coverage = len(found) / len(required) if required else 1.0
        rubric_status[rid] = {
            "rubric_name": item["name"],
            "required": required,
            "found": found,
            "missing": missing,
            "coverage": round(coverage, 2),
        }

    overall_coverage = round(total_found / total_required, 2) if total_required > 0 else 0.0

    # 去重并按频率排序 critical_missing
    from collections import Counter
    missing_counter = Counter(all_missing)
    critical_missing = [item for item, _ in missing_counter.most_common()]

    logger.info(
        "[EVIDENCE_CHECKER] overall_coverage=%.2f critical_missing=%s",
        overall_coverage,
        critical_missing[:5],
    )

    return {
        "rubric_evidence_status": rubric_status,
        "overall_coverage": overall_coverage,
        "critical_missing": critical_missing,
    }
