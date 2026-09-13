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
    # 过滤掉轮次为0或没有实质性内容的会话（即仅仅输入了学生ID的会话）
    valid_sessions = [s for s in all_sessions if s.get("round_count", 0) > 0]
    total_teams = len(valid_sessions)

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

    for session in valid_sessions:
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
            "kb_context": session.get("kb_context", {}),
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
    value_index = _calc_value_index(valid_sessions)

    # ── 阶段分布
    phase_dist = dict(Counter(
        _PHASE_NAMES.get(s.get("current_phase", "value_probe"), "价值探测")
        for s in valid_sessions
    ))

    # ── 高风险项目数（存在 ≥2 条高严重度漏洞）
    high_risk_count = sum(
        1 for s in valid_sessions
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


def generate_student_capability_report(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    A6-4：基于学生多轮对话历史，生成结构化能力画像评估报告
    包含：五维打分 + 三轮对话行为诊断 + 原话引用
    """
    messages = state.get("messages", [])
    scores = state.get("capability_scores", {})
    fallacies = state.get("detected_fallacies", [])
    round_count = state.get("round_count", 0)

    # 按角色拆分对话
    user_messages = [m["content"] for m in messages if m.get("role") == "user"]
    assistant_messages = [m["content"] for m in messages if m.get("role") == "assistant"]

    # 三轮对话行为诊断
    def _diagnose_round(idx: int, label: str) -> Dict[str, Any]:
        if idx < len(user_messages):
            quote = user_messages[idx][:150]
            evidence = f"学生在第{idx+1}轮对话中说：「{quote}…」"
        else:
            evidence = "（该轮次暂无对话记录）"
        return {"label": label, "evidence": evidence}

    rounds_diagnosis = [
        _diagnose_round(0, "第一轮（核心价值探测）：学生初始描述痛点的范围与具体性"),
        _diagnose_round(1, "第二轮（逻辑压力测试）：面对追问时的逻辑自洽程度"),
        _diagnose_round(2, "第三轮（落地可行性）：对里程碑和执行路径的规划清晰度"),
    ]

    # 规则命中摘要（引用原话证据）
    fallacy_summary = []
    for f in fallacies[:5]:
        fallacy_summary.append({
            "rule_id": f.get("rule_id", "?"),
            "name": f.get("name", ""),
            "evidence_quote": f.get("evidence", "（无直接引用）"),
            "severity": f.get("severity", "medium"),
        })

    # 能力维度标准化（0-5 scale for report）
    normalized_scores = {
        "痛点发现 (Empathy)": round(scores.get("pain_point_discovery", 5.0) / 2, 1),
        "方案策划 (Ideation)": round(scores.get("solution_planning", 5.0) / 2, 1),
        "商业建模 (Business)": round(scores.get("business_modeling", 5.0) / 2, 1),
        "资源杠杆 (Execution)": round(scores.get("resource_leverage", 5.0) / 2, 1),
        "逻辑表达 (Logic)": round(scores.get("pitch_expression", 5.0) / 2, 1),
    }
    overall = round(sum(normalized_scores.values()) / len(normalized_scores), 1)

    return {
        "student_id": state.get("student_id", ""),
        "session_id": state.get("session_id", ""),
        "round_count": round_count,
        "overall_score": overall,
        "capability_scores_normalized": normalized_scores,
        "rounds_diagnosis": rounds_diagnosis,
        "detected_fallacies_summary": fallacy_summary,
        "ai_disclaimer": "⚠️ 以上能力评估由AI基于对话历史生成，仅供教师参考，请结合课堂表现综合判断。",
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


def generate_grading_report(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    A6-1: Generating a grading report with Rubric Table, Evidence Trace, Revision Suggestions, and Instructor Review Notes.
    """
    rubric_scores = state.get("rubric_scores", {})
    breakdown = state.get("score_breakdown", {})
    fallacies = state.get("detected_fallacies", [])
    
    rubric_table = []
    for r_id, r_info in rubric_scores.items():
        rubric_table.append({
            "rubric_id": r_id,
            "score": r_info.get("score", 0),
            "missing": r_info.get("missing", []),
            "breakdown": breakdown.get(r_id, {})
        })
        
    evidence_trace = []
    for f in fallacies:
        evidence_trace.append({
            "rule_id": f.get("rule_id", ""),
            "name": f.get("name", ""),
            "evidence": f.get("evidence", ""),
            "severity": f.get("severity", "medium")
        })
        
    revision_suggestions = []
    for r_id, r_info in rubric_scores.items():
        fix_24h = r_info.get("fix_24h", "")
        fix_72h = r_info.get("fix_72h", "")
        if fix_24h or fix_72h:
            revision_suggestions.append({
                "rubric_id": r_id,
                "fix_24h": fix_24h,
                "fix_72h": fix_72h
            })
            
    high_risks = [f.get("name") for f in fallacies if f.get("severity") == "high"]
    if high_risks:
        instructor_review_notes = "Based on the AI assessment, the student needs to focus on critical issues like: " + ", ".join(high_risks[:3]) + "."
    else:
        instructor_review_notes = "Based on the AI assessment, the student needs to focus on improving overall evidence depth."

    return {
        "student_id": state.get("student_id", ""),
        "session_id": state.get("session_id", ""),
        "rubric_table": rubric_table,
        "evidence_trace": evidence_trace,
        "revision_suggestions": revision_suggestions,
        "instructor_review_notes": instructor_review_notes
    }

