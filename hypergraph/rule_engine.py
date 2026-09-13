"""
确定性规则引擎（Phase 1 — 非 LLM）
基于 extracted_data.summary 字段，用纯 Python 逻辑判断 H1-H20 哪些规则被触发。
不调用任何 LLM，延迟 ≈ 0ms，成本 ≈ 0。
"""
import logging
from typing import List, Dict, Any

from .rules import RULES

logger = logging.getLogger("entrepreneurial_agent.rule_engine")

# ── 关键词触发表 ──────────────────────────────────────────────
# 每条规则关联一组"阳性信号"（出现则加分）和"阴性信号"（缺失则触发）
_RULE_SIGNALS: Dict[str, Dict[str, Any]] = {
    "H1": {
        "check_fields": ["target_customer", "value_proposition", "core_pain_point"],
        "negative_keywords": ["未提及", "不确定", "所有人", "大众", "任何人"],
        "require_all": True,
        "description": "客户-价值主张错位：目标客户或价值主张缺失/模糊",
    },
    "H2": {
        "check_fields": ["key_channels"],
        "negative_keywords": ["未提及", "不确定", "自然流量", "口碑"],
        "require_all": True,
        "description": "渠道不可达：获客渠道未确定或依赖不可控渠道",
    },
    "H3": {
        "check_fields": ["price_point"],
        "negative_keywords": ["未提及", "免费", "不确定", "之后再定"],
        "require_all": True,
        "description": "定价无支付意愿证据：定价未确定或缺乏验证",
    },
    "H4": {
        "check_fields": ["core_pain_point", "target_customer"],
        "positive_keywords": ["万亿", "千亿", "百亿", "巨大市场", "市场很大"],
        "require_all": False,
        "description": "TAM/SAM/SOM 口径混乱：使用宏观数字代替真实可达市场",
    },
    "H5": {
        "check_fields": ["core_pain_point"],
        "negative_keywords": ["未提及", "我觉得", "应该", "可能", "感觉"],
        "require_all": True,
        "description": "需求证据不足：痛点判断基于臆测而非调研",
    },
    "H8": {
        "check_fields": ["revenue_model", "cost_structure", "price_point"],
        "negative_keywords": ["未提及", "不确定", "之后再说"],
        "require_all": True,
        "description": "单位经济不成立：收入模式/成本/定价未明确",
    },
    "H9": {
        "check_fields": ["revenue_model", "key_channels"],
        "positive_keywords": ["病毒传播", "刷屏", "自然增长", "爆发式"],
        "require_all": False,
        "description": "增长逻辑跳跃：依赖不可控的增长假设",
    },
    "H10": {
        "check_fields": ["team_description", "technology_level"],
        "negative_keywords": ["未提及", "不确定"],
        "require_all": True,
        "description": "里程碑不可交付：团队或技术能力不明确",
    },
    "H11": {
        "check_fields": ["value_proposition", "core_pain_point"],
        "positive_keywords": ["数据", "用户信息", "医疗", "金融", "AI", "无人机", "跨境", "采集"],
        "require_all": False,
        "description": "合规/伦理缺口：涉及敏感领域但未提及合规",
    },
    "H12": {
        "check_fields": ["technology_level", "team_description"],
        "negative_keywords": ["未提及", "不确定"],
        "require_all": True,
        "description": "技术路线与资源不匹配：技术或团队信息缺失",
    },
    "H16": {
        "check_fields": ["value_proposition"],
        "positive_keywords": ["没有对手", "第一家", "唯一", "独创", "没有竞争"],
        "require_all": False,
        "description": "隐性替代方案忽视：声称无竞争对手",
    },
    "H17": {
        "check_fields": ["value_proposition", "core_pain_point"],
        "positive_keywords": ["技术壁垒", "领先", "独家", "护城河", "独创技术"],
        "require_all": False,
        "description": "巨头入场风险未评估：声称技术壁垒但未考虑巨头",
    },
    "H18": {
        "check_fields": ["revenue_model", "cost_structure"],
        "positive_keywords": ["先免费", "后期再赚", "积累用户", "融资后"],
        "require_all": False,
        "description": "现金流断裂风险：先烧钱模式但无盈利时间表",
    },
    "H19": {
        "check_fields": ["key_channels", "target_customer"],
        "positive_keywords": ["1%", "只要一点", "病毒传播", "刷屏", "自然流量"],
        "require_all": False,
        "description": "获客成本幻觉：依赖大数法则而非真实 CAC",
    },
}


def run_rule_engine(
    extracted_summary: Dict[str, str],
    conversation_text: str = "",
    current_phase: str = "value_probe",
) -> Dict[str, Any]:
    """
    Phase 1 确定性规则引擎。
    输入：提取到的结构化商业要素摘要 + 对话文本。
    输出：{
        "triggered_rules": [...],      # 触发的规则列表
        "gap_fields": [...],            # 缺失的关键字段
        "confidence_map": {...},        # 每条规则的置信度
        "phase_recommendation": str,    # 建议阶段
    }
    """
    triggered: List[Dict[str, Any]] = []
    gap_fields: List[str] = []
    confidence_map: Dict[str, float] = {}

    # 将所有文本合并用于关键词搜索
    all_text = conversation_text + " " + " ".join(
        str(v) for v in extracted_summary.values() if v
    )

    for rule_id, signals in _RULE_SIGNALS.items():
        rule_info = RULES.get(rule_id, {})
        triggered_flag = False
        confidence = 0.0
        evidence_parts = []

        # ── 阴性检查：关键字段缺失或包含消极关键词 ────────
        if "negative_keywords" in signals and signals.get("require_all", False):
            missing_count = 0
            for field in signals["check_fields"]:
                value = extracted_summary.get(field, "未提及")
                if not value or value == "未提及":
                    missing_count += 1
                    gap_fields.append(field)
                    evidence_parts.append(f"字段 '{field}' 未提及")
                else:
                    for neg_kw in signals.get("negative_keywords", []):
                        if neg_kw in str(value):
                            missing_count += 1
                            evidence_parts.append(
                                f"字段 '{field}' 包含模糊表述 '{neg_kw}'"
                            )
                            break

            total_fields = len(signals["check_fields"])
            if missing_count > 0:
                confidence = round(missing_count / total_fields, 2)
                if confidence >= 0.5:
                    triggered_flag = True

        # ── 阳性检查：文本中包含触发性关键词 ────────────────
        if "positive_keywords" in signals and not signals.get("require_all", False):
            matched_keywords = []
            for kw in signals.get("positive_keywords", []):
                if kw in all_text:
                    matched_keywords.append(kw)

            if matched_keywords:
                confidence = min(0.5 + 0.15 * len(matched_keywords), 0.95)
                triggered_flag = True
                evidence_parts.append(
                    f"检测到触发关键词: {', '.join(matched_keywords)}"
                )

        # ── 记录结果 ──────────────────────────────────────────
        confidence_map[rule_id] = confidence

        if triggered_flag and confidence >= 0.5:
            triggered.append({
                "rule_id": rule_id,
                "name": rule_info.get("name", rule_id),
                "description": signals.get("description", rule_info.get("description", "")),
                "evidence": "; ".join(evidence_parts),
                "severity": rule_info.get("severity", "medium"),
                "confidence": confidence,
                "impact": rule_info.get("impact", ""),
                "fix_task": rule_info.get("fix_task", ""),
                "source": "rule_engine",  # 标记来源：确定性规则引擎
            })

    # ── 阶段推进建议 ──────────────────────────────────────────
    high_severity_count = sum(
        1 for t in triggered if t["severity"] == "high"
    )
    phase_recommendation = current_phase
    if high_severity_count == 0 and len(gap_fields) <= 2:
        phase_order = ["value_probe", "pressure_test", "landing_check"]
        idx = phase_order.index(current_phase) if current_phase in phase_order else 0
        if idx < len(phase_order) - 1:
            phase_recommendation = phase_order[idx + 1]

    # 去重 gap_fields
    gap_fields = list(dict.fromkeys(gap_fields))

    logger.info(
        "[RULE_ENGINE] triggered=%d rules, gaps=%d fields, phase_rec=%s",
        len(triggered), len(gap_fields), phase_recommendation,
    )

    return {
        "triggered_rules": triggered,
        "gap_fields": gap_fields,
        "confidence_map": confidence_map,
        "phase_recommendation": phase_recommendation,
    }
