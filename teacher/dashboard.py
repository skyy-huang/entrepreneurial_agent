"""
教师端数据聚合逻辑
从"个体诊断"提升到"班级画像"：
  - 班级共性错误排行榜（H1-H15 频率统计）
  - 学习增值指数（capability_scores 变化）
  - AI 生成教学干预建议
"""
from typing import List, Dict, Any
from collections import Counter

from hypergraph.rules import RULES

# 各规则对应的教学主题
_TEACHING_TOPICS: Dict[str, str] = {rule_id: info["teaching_topic"] for rule_id, info in RULES.items()}

# 各阶段中文名
_PHASE_NAMES = {
    "value_probe": "价值探测",
    "pressure_test": "压力测试",
    "landing_check": "落地校验",
}


def aggregate_class_data(all_sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    聚合全班所有团队的会话数据，生成教师看板所需的全部字段。
    参数：all_sessions - 每个元素是一个 AgentState 字典
    """
    total_teams = len(all_sessions)
    if total_teams == 0:
        return _empty_dashboard()

    # ── 统计规则触发频率（每队只计一次，避免重复触发噪声）
    fallacy_counter: Counter = Counter()
    all_scores: Dict[str, List[float]] = {
        "pain_point_discovery": [],
        "solution_planning": [],
        "business_modeling": [],
        "resource_leverage": [],
        "pitch_expression": [],
    }
    team_details: List[Dict] = []

    for session in all_sessions:
        # 去重：每队每条规则只计一次
        triggered = set()
        for f in session.get("detected_fallacies", []):
            rid = f.get("rule_id", "").upper()
            if rid:
                triggered.add(rid)
        for rid in triggered:
            fallacy_counter[rid] += 1

        # 收集能力得分
        scores = session.get("capability_scores", {})
        for dim in all_scores:
            val = scores.get(dim)
            if isinstance(val, (int, float)):
                all_scores[dim].append(float(val))

        team_details.append({
            "student_id": session.get("student_id", "未知"),
            "session_id": session.get("session_id", ""),
            "round_count": session.get("round_count", 0),
            "triggered_rules": sorted(triggered),
            "capability_scores": scores,
            "current_phase": _PHASE_NAMES.get(
                session.get("current_phase", "value_probe"), "价值探测"
            ),
            "avg_score": round(
                sum(scores.values()) / len(scores) if scores else 5.0, 1
            ),
        })

    # ── 平均能力得分
    avg_scores = {
        dim: round(sum(lst) / len(lst), 1) if lst else 5.0
        for dim, lst in all_scores.items()
    }

    # ── 规则排行榜
    rule_ranking = []
    for rule_id, count in fallacy_counter.most_common():
        rule_info = RULES.get(rule_id, {})
        pct = round(count / total_teams * 100, 1)
        rule_ranking.append({
            "rule_id": rule_id,
            "name": rule_info.get("name", rule_id),
            "description": rule_info.get("description", ""),
            "severity": rule_info.get("severity", "medium"),
            "count": count,
            "percentage": pct,
        })

    # ── 教学干预建议
    teaching_suggestions = _generate_suggestions(rule_ranking, total_teams)

    # ── 学习增值指数
    value_index = _calc_value_index(all_sessions)

    # ── 阶段分布
    phase_dist = dict(Counter(
        _PHASE_NAMES.get(s.get("current_phase", "value_probe"), "价值探测")
        for s in all_sessions
    ))

    # ── 高风险项目数（存在 ≥2 条高严重度漏洞）
    high_risk_count = sum(
        1 for s in all_sessions
        if sum(1 for f in s.get("detected_fallacies", []) if f.get("severity") == "high") >= 2
    )

    return {
        "total_teams": total_teams,
        "high_risk_count": high_risk_count,
        "rule_ranking": rule_ranking,
        "avg_capability_scores": avg_scores,
        "teaching_suggestions": teaching_suggestions,
        "learning_value_index": value_index,
        "team_details": team_details,
        "phase_distribution": phase_dist,
    }


def _generate_suggestions(rule_ranking: List[Dict], total_teams: int) -> List[str]:
    """根据规则触发情况生成可操作的教学建议"""
    suggestions = []
    for rule in rule_ranking[:5]:  # 取前5名
        pct = rule["percentage"]
        rid = rule["rule_id"]
        topic = _TEACHING_TOPICS.get(rid, rule["name"])

        if pct >= 50:
            suggestions.append(
                f"🔴 【紧急】建议下周开设专题：「{topic}」"
                f"——{pct}%的团队（{rule['count']}/{total_teams}）"
                f"存在【{rid}·{rule['name']}】问题：{rule['description']}"
            )
        elif pct >= 30:
            suggestions.append(
                f"🟡 建议重点讲授「{topic}」"
                f"——{pct}%的团队存在【{rid}·{rule['name']}】风险"
            )
        elif pct >= 15:
            suggestions.append(
                f"🟢 建议补充讲授「{topic}」——{pct}%的团队有相关薄弱点"
            )

    if not suggestions:
        suggestions.append(
            "✅ 本阶段班级整体逻辑能力表现良好，建议推进到下一训练阶段，"
            "可考虑引入真实导师进行 1v1 路演练习。"
        )
    return suggestions


def _calc_value_index(all_sessions: List[Dict]) -> Dict[str, Any]:
    """
    计算学习增值指数
    判断标准：轮次 ≥3 且平均得分 ≥6.5 → 进步中；轮次 ≥5 且平均得分 < 5.5 → 停滞
    """
    improving, stagnant = 0, 0
    for s in all_sessions:
        rounds = s.get("round_count", 0)
        scores = s.get("capability_scores", {})
        avg = sum(scores.values()) / len(scores) if scores else 5.0
        if rounds >= 3 and avg >= 6.5:
            improving += 1
        elif rounds >= 5 and avg < 5.5:
            stagnant += 1

    total = len(all_sessions)
    return {
        "improving": improving,
        "stagnant": stagnant,
        "neutral": total - improving - stagnant,
        "total": total,
        "improvement_rate": round(improving / total * 100, 1) if total > 0 else 0,
    }


def _empty_dashboard() -> Dict[str, Any]:
    return {
        "total_teams": 0,
        "high_risk_count": 0,
        "rule_ranking": [],
        "avg_capability_scores": {k: 5.0 for k in [
            "pain_point_discovery", "solution_planning",
            "business_modeling", "resource_leverage", "pitch_expression"
        ]},
        "teaching_suggestions": ["暂无学生数据，请等待学生开始使用系统后再查看。"],
        "learning_value_index": {"improving": 0, "stagnant": 0, "neutral": 0, "total": 0, "improvement_rate": 0},
        "team_details": [],
        "phase_distribution": {},
    }
