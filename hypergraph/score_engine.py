"""
评分引擎（Phase 1 — 非 LLM）
为每个 Rubric 项（R1-R9）自动计算 score_floor（基于证据的底分）。
LLM 在 Phase 2 仅能在底分基础上添加 score_delta（上限 ±2 分）。

最终评分 = clamp(score_floor + score_delta, 0, 5)

不调用任何 LLM，延迟 ≈ 0ms，成本 ≈ 0。
"""
import logging
from typing import Dict, Any, List

from .rules import RUBRIC_ITEMS

logger = logging.getLogger("entrepreneurial_agent.score_engine")


def compute_score_floors(
    extracted_summary: Dict[str, str],
    evidence_result: Dict[str, Any],
    conversation_text: str = "",
) -> Dict[str, Dict[str, Any]]:
    """
    为 R1-R9 每个 Rubric 项计算确定性底分。

    输入：
        extracted_summary: 提取到的商业要素摘要
        evidence_result: evidence_checker 的输出
        conversation_text: 对话全文

    输出：
        {
            "R1": {
                "score_floor": 2,
                "floor_reason": "证据覆盖率 50%，缺少 Survey",
                "max_delta": 2,
                "evidence_coverage": 0.5,
            },
            ...
        }
    """
    rubric_status = evidence_result.get("rubric_evidence_status", {})
    floors: Dict[str, Dict[str, Any]] = {}

    for item in RUBRIC_ITEMS:
        rid = item["id"]
        status = rubric_status.get(rid, {})
        coverage = status.get("coverage", 0.0)
        missing = status.get("missing", [])
        found = status.get("found", [])

        # ── 基于证据覆盖率计算底分 ──────────────────────────
        # 覆盖率 ≥ 0.8  → floor = 3（证据基本齐全）
        # 覆盖率 ≥ 0.5  → floor = 2（部分证据）
        # 覆盖率 ≥ 0.25 → floor = 1（少量证据）
        # 覆盖率 < 0.25  → floor = 0（几乎无证据）
        if coverage >= 0.8:
            base_floor = 3
        elif coverage >= 0.5:
            base_floor = 2
        elif coverage >= 0.25:
            base_floor = 1
        else:
            base_floor = 0

        # ── 特殊规则加成/扣减 ───────────────────────────────
        adjustments = []

        # R1 Problem Definition: 如果 core_pain_point 明确且具体，+1
        if rid == "R1":
            pain = extracted_summary.get("core_pain_point", "未提及")
            if pain and pain != "未提及" and len(pain) > 10:
                base_floor = min(base_floor + 1, 4)
                adjustments.append("痛点描述具体 +1")

        # R3 Solution Feasibility: 根据 technology_level 加成
        if rid == "R3":
            tech_level = extracted_summary.get("technology_level", "idea")
            if tech_level in ("product", "mvp"):
                base_floor = min(base_floor + 1, 4)
                adjustments.append(f"技术水平={tech_level} +1")
            elif tech_level == "prototype":
                base_floor = min(base_floor + 1, 3)
                adjustments.append(f"技术水平={tech_level} +1")

        # R4 Business Model: 5 个核心字段的完整度
        if rid == "R4":
            bm_fields = ["target_customer", "value_proposition", "revenue_model",
                         "key_channels", "cost_structure"]
            filled = sum(
                1 for f in bm_fields
                if extracted_summary.get(f, "未提及") not in ("未提及", "", None)
            )
            bm_rate = filled / len(bm_fields)
            if bm_rate >= 0.8:
                base_floor = max(base_floor, 2)
                adjustments.append(f"商业模式字段完整度 {bm_rate:.0%}")
            elif bm_rate < 0.4:
                base_floor = min(base_floor, 1)
                adjustments.append(f"商业模式字段严重缺失 {bm_rate:.0%}")

        # R6 Financial Logic: 检查是否提到了具体数字
        if rid == "R6":
            summary_text = " ".join(str(v) for v in extracted_summary.values())
            has_numbers = any(c.isdigit() for c in summary_text)
            price = extracted_summary.get("price_point", "未提及")
            if price and price != "未提及" and has_numbers:
                base_floor = max(base_floor, 1)
                adjustments.append("含有财务数字")
            else:
                base_floor = min(base_floor, 1)
                adjustments.append("缺少具体财务数字")

        # R8 Team: 团队信息完整度
        if rid == "R8":
            team = extracted_summary.get("team_description", "未提及")
            if team and team != "未提及" and len(team) > 15:
                base_floor = max(base_floor, 2)
                adjustments.append("团队描述较完整")

        # ── 底分范围约束：0-4（留 1 分给 LLM delta）──────────
        base_floor = max(0, min(base_floor, 4))

        # ── LLM 可调 delta 上限 ──────────────────────────────
        # 底分越低，LLM 能调整的空间越小（防止底分被 LLM 绕过）
        if base_floor <= 1:
            max_delta = 1
        elif base_floor <= 2:
            max_delta = 2
        else:
            max_delta = 2

        # 构建底分理由
        reason_parts = [f"证据覆盖率 {coverage:.0%}"]
        if missing:
            reason_parts.append(f"缺少: {', '.join(missing[:3])}")
        if found:
            reason_parts.append(f"已有: {', '.join(found[:3])}")
        reason_parts.extend(adjustments)

        floors[rid] = {
            "score_floor": base_floor,
            "floor_reason": "; ".join(reason_parts),
            "max_delta": max_delta,
            "evidence_coverage": coverage,
        }

    logger.info(
        "[SCORE_ENGINE] floors=%s",
        {rid: v["score_floor"] for rid, v in floors.items()},
    )

    return floors


def apply_delta_to_floors(
    floors: Dict[str, Dict[str, Any]],
    llm_scores: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    将 LLM 给出的 score_delta 应用到底分上，输出最终评分 + 分解。

    输入：
        floors: compute_score_floors 的输出
        llm_scores:  LLM 返回的 {R1: {score_delta: 1, reasoning: "..."}, ...}

    输出：
        {
            "R1": {
                "final_score": 3,
                "score_floor": 2,
                "score_delta": 1,
                "max_delta": 2,
                "floor_reason": "...",
                "delta_reason": "...",    # LLM 给出的加分理由
                "missing_evidence": [...],
                "evidence_coverage": 0.5,
            },
            ...
        }
    """
    result: Dict[str, Dict[str, Any]] = {}

    for rid, floor_info in floors.items():
        floor = floor_info["score_floor"]
        max_delta = floor_info["max_delta"]

        llm_data = llm_scores.get(rid, {})

        # LLM 可以给 score_delta 或直接给 score（向后兼容）
        if "score_delta" in llm_data:
            raw_delta = llm_data["score_delta"]
        elif "score" in llm_data:
            # 如果 LLM 给了绝对分，计算它与底分的差值作为 delta
            raw_delta = llm_data["score"] - floor
        else:
            raw_delta = 0

        # 限制 delta 在 [-1, max_delta] 范围内
        clamped_delta = max(-1, min(int(raw_delta), max_delta))
        final_score = max(0, min(floor + clamped_delta, 5))

        result[rid] = {
            "final_score": final_score,
            "score_floor": floor,
            "score_delta": clamped_delta,
            "max_delta": max_delta,
            "floor_reason": floor_info["floor_reason"],
            "delta_reason": llm_data.get("reasoning", llm_data.get("missing_evidence", "")),
            "missing_evidence": llm_data.get("missing_evidence", []),
            "evidence_coverage": floor_info["evidence_coverage"],
        }

    logger.info(
        "[SCORE_ENGINE] final_scores=%s",
        {rid: v["final_score"] for rid, v in result.items()},
    )

    return result
