"""
三个核心 LangGraph 节点（V2 升级）：
  extractor_node  → 提取商业要素，构建超图，记录日志
  critic_node     → H1-H20 规则审计 + 追问策略选择 + 超图溯源日志
  coach_node      → 苏格拉底式提问 + 单任务分配 + Rubric 打分

   rubric_scoring_node → 逐项 Rubric 评分（R1-R9）

注意：rubric_scoring_node **不在** F2 的线性工作流中（见 graph/workflow.py）。
F2 每轮对话都跑一遍 R1-R9 评分既慢又偏离「项目指导」的语义，因此它以独立的
/api/score 接口对外提供。竞赛顾问模式则由 coach_node 依据 agent_mode 处理，
不存在名为 competition_node 的独立节点（旧版 docstring 有此误述）。
"""
import os
import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .state import AgentState
from hypergraph.extractor import extract_business_elements, build_hypergraph_from_extraction
from hypergraph.rules import (
    get_rules_for_prompt, RULES, RUBRIC_ITEMS, INTERROGATION_STRATEGIES,
    get_strategy_for_fallacy, get_competition_rubric,
)
from hypergraph.rule_engine import run_rule_engine
from hypergraph.evidence_checker import check_evidence_gaps
from hypergraph.score_engine import compute_score_floors, apply_delta_to_floors
from prompts.coach_prompt import (
    build_coach_prompt, build_competition_prompt,
    TUTOR_SYSTEM_PROMPT, INSTRUCTOR_ASSISTANT_PROMPT, ASSESSMENT_ASSISTANT_PROMPT,
)
from .graph_coach import GraphCoach

logger = logging.getLogger("entrepreneurial_agent")

# 全局初始化导师引擎
master_coach_engine = GraphCoach()


def _get_llm(temperature: float = 0.3) -> ChatOpenAI:
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        temperature=temperature,
    )


def _llm_available() -> bool:
    key = os.getenv("DEEPSEEK_API_KEY", "")
    return bool(key and key != "your_deepseek_api_key_here")


# ─────────────────────────────────────────────────────────────
# Node 1: Extractor
# ─────────────────────────────────────────────────────────────
async def extractor_node(state: AgentState) -> dict:
    """从学生输入中提取结构化商业要素，构建超图+知识图谱检索"""
    extracted = await extract_business_elements(
        state["current_input"],
        state["messages"],
    )
    hg = build_hypergraph_from_extraction(extracted)

    # 知识图谱检索上下文
    kb_context = {}
    try:
        # 增加容错和更宽泛的检索：如果 summary 提取的信息较少（比如提问具体概念），直接把原输入当作线索加入检索
        query_context = extracted.get("summary", {}).copy()
        if state.get("agent_mode") == "tutor":
            query_context["raw_query"] = state["current_input"]
            
        retrieved_result = master_coach_engine.get_relevant_nodes(
            query_context,
            industry=state.get("industry"),
            level=state.get("level")
        )
        retrieved_nodes = retrieved_result.get("nodes", [])
        retrieved_master_edges = retrieved_result.get("edges", [])
        
        retrieved_edges = hg.get_active_edge_types()
        similar_failures = master_coach_engine.get_similar_failure_cases(
            query_context,
            industry=state.get("industry"),
            level=state.get("level")
        )
        kb_context = {
            "retrieved_nodes": retrieved_nodes,
            "retrieved_master_edges": retrieved_master_edges,
            "retrieved_hyperedges": retrieved_edges,
            "similar_failures": similar_failures,
        }
        logger.info(
            "[EXTRACTOR] agent_name=extractor "
            "retrieved_kg_nodes=%s "
            "retrieved_hyperedges=%s",
            retrieved_nodes,
            retrieved_edges,
        )
    except Exception as e:
        logger.warning("[EXTRACTOR] Graph retrieval failed: %s", e)
        kb_context = {
            "retrieved_nodes": [],
            "retrieved_hyperedges": [],
            "similar_failures": [],
        }

    return {
        "extracted_data": extracted,
        "hypergraph_summary": hg.to_summary(),
        "kb_context": kb_context,
        "retrieved_hyperedge_types": kb_context.get("retrieved_hyperedges", []),
    }


# ---------------------------------------------------------------
# Node 2: Critic (two-phase: Phase1 rule-engine + Phase2 LLM)
# ---------------------------------------------------------------
_CRITIC_PHASE2_PROMPT = (
    "You are a business-logic auditor (Phase 2).\n"
    "Phase 1 (deterministic rule engine) already found these issues:\n"
    "{phase1_result}\n\n"
    "Your job:\n"
    "1. Review Phase-1 conclusions and find ADDITIONAL semantic-level "
    "logical flaws that keyword matching may miss.\n"
    "2. For every triggered rule supply 'evidence' quoting the student's "
    "own words or numbers.\n"
    "3. Provide capability_score_updates and select a probing strategy.\n\n"
    "Conversation context:\n{conversation_context}\n\n"
    "Extracted summary:\n{extracted_summary}\n\n"
    "Phase: {current_phase}  Round: {round_count}\n"
    "Current scores: {current_scores}\n\n"
    "Return STRICT JSON only:\n"
    '{{\n'
    '  "additional_fallacies": [\n'
    '    {{\n'
    '      "rule_id": "H8",\n'
    '      "name": "rule name",\n'
    '      "description": "brief",\n'
    '      "evidence": "student quote",\n'
    '      "severity": "high",\n'
    '      "confidence": 0.9,\n'
    '      "detected_keywords": ["kw"]\n'
    '    }}\n'
    '  ],\n'
    '  "capability_score_updates": {{\n'
    '    "pain_point_discovery": 6.0,\n'
    '    "solution_planning": 4.0,\n'
    '    "business_modeling": 3.0,\n'
    '    "resource_leverage": 5.0,\n'
    '    "pitch_expression": 7.0\n'
    '  }},\n'
    '  "selected_strategy": "cac_reality",\n'
    '  "should_advance_phase": false,\n'
    '  "audit_summary": "one-line summary"\n'
    '}}\n\n'
    "Strategy choices: {strategy_keys}\n"
    "Only output additional_fallacies NOT already found by Phase 1."
)


async def critic_node(state: AgentState) -> dict:
    """Two-phase Critic: Phase1(rule engine, 0 cost) then Phase2(LLM refine)."""

    conversation_text = "\n".join([
        f"{'student' if m['role'] == 'user' else 'coach'}: {m['content']}"
        for m in state["messages"][-10:]
    ]) if state["messages"] else "(no history)"

    summary_data = state.get("extracted_data", {}).get("summary", {})

    # == Phase 1 (non-LLM): deterministic rule engine + evidence check ==
    rule_result = run_rule_engine(
        extracted_summary=summary_data,
        conversation_text=conversation_text + " " + state["current_input"],
        current_phase=state["current_phase"],
    )

    evidence_result = check_evidence_gaps(
        extracted_data=state.get("extracted_data", {}),
        conversation_text=conversation_text + " " + state["current_input"],
    )

    phase1_fallacies = rule_result["triggered_rules"]
    phase1_summary = (
        f"Phase1 triggered {len(phase1_fallacies)} rules: "
        f"{[f['rule_id'] for f in phase1_fallacies]}\n"
        f"Gap fields: {rule_result['gap_fields']}\n"
        f"Evidence coverage: {evidence_result['overall_coverage']:.0%}\n"
        f"Missing evidence: {evidence_result['critical_missing'][:5]}"
    )

    logger.info("[CRITIC] Phase1 done: %s", phase1_summary)

    if not _llm_available():
        return {
            "detected_fallacies": phase1_fallacies,
            "capability_scores": state["capability_scores"],
            "current_phase": rule_result.get("phase_recommendation", state["current_phase"]),
            "detected_keywords": [],
            "probing_strategy": get_strategy_for_fallacy([]),
            "degraded_reason": "Critic 阶段 LLM 不可用，已改用确定性规则引擎完成审计",
            "rule_engine_result": {
                "triggered_rules": [f["rule_id"] for f in phase1_fallacies],
                "gap_fields": rule_result["gap_fields"],
                "evidence_coverage": evidence_result["overall_coverage"],
                "critical_missing_evidence": evidence_result["critical_missing"][:5],
                "phase1_count": len(phase1_fallacies),
                "phase2_count": 0,
            },
        }

    # == Phase 2 (LLM): supplement deep semantic flaws + score update ==
    llm = _get_llm(temperature=0.1)
    strategy_keys = list(INTERROGATION_STRATEGIES.keys())

    messages = [
        SystemMessage(content=_CRITIC_PHASE2_PROMPT.format(
            phase1_result=phase1_summary,
            conversation_context=conversation_text[-2000:],
            extracted_summary=json.dumps(summary_data, ensure_ascii=False, indent=2),
            current_phase=state["current_phase"],
            round_count=state["round_count"],
            current_scores=json.dumps(state["capability_scores"], ensure_ascii=False),
            strategy_keys=", ".join(strategy_keys),
        )),
        HumanMessage(content=f"Student latest input: {state['current_input']}"),
    ]

    try:
        response = await llm.ainvoke(messages)
    except Exception as exc:
        logger.warning("[CRITIC] LLM unavailable, using deterministic audit: %s", exc)
        return {
            "detected_fallacies": phase1_fallacies,
            "capability_scores": state["capability_scores"],
            "current_phase": rule_result.get("phase_recommendation", state["current_phase"]),
            "detected_keywords": [],
            "probing_strategy": get_strategy_for_fallacy([]),
            "degraded_reason": "Critic 阶段 LLM 不可用，已改用确定性规则引擎完成审计",
            "rule_engine_result": {
                "triggered_rules": [f["rule_id"] for f in phase1_fallacies],
                "gap_fields": rule_result["gap_fields"],
                "evidence_coverage": evidence_result["overall_coverage"],
                "critical_missing_evidence": evidence_result["critical_missing"][:5],
                "phase1_count": len(phase1_fallacies),
                "phase2_count": 0,
            },
        }
    phase2_result = _parse_json_response(response.content, {
        "additional_fallacies": [],
        "capability_score_updates": state["capability_scores"],
        "selected_strategy": "evidence_challenge",
        "should_advance_phase": False,
        "audit_summary": "Phase2 parse failed",
    })

    # == Merge Phase 1 + Phase 2 ==
    all_fallacies = list(phase1_fallacies)

    phase1_rule_ids = {f["rule_id"] for f in phase1_fallacies}
    for f in phase2_result.get("additional_fallacies", []):
        rid = f.get("rule_id", "").upper()
        if rid and rid not in phase1_rule_ids:
            rule_info = RULES.get(rid, {})
            f["rule_id"] = rid
            f["impact"] = f.get("impact") or rule_info.get("impact", "")
            f["fix_task"] = f.get("fix_task") or rule_info.get("fix_task", "")
            f["source"] = "llm_phase2"
            all_fallacies.append(f)

    # EMA smoothing for capability scores (30% new weight)
    new_scores = dict(state["capability_scores"])
    for key, val in phase2_result.get("capability_score_updates", {}).items():
        if key in new_scores and isinstance(val, (int, float)):
            new_scores[key] = round(new_scores[key] * 0.7 + float(val) * 0.3, 1)

    detected_keywords = []
    for f in all_fallacies:
        detected_keywords.extend(f.get("detected_keywords", []))

    selected_strategy = phase2_result.get("selected_strategy", "")
    if not selected_strategy or selected_strategy not in INTERROGATION_STRATEGIES:
        selected_strategy = get_strategy_for_fallacy(detected_keywords)

    # Phase advancement
    new_phase = state["current_phase"]
    phase1_rec = rule_result.get("phase_recommendation", state["current_phase"])
    if phase2_result.get("should_advance_phase") or phase1_rec != state["current_phase"]:
        phase_order = ["value_probe", "pressure_test", "landing_check"]
        idx = phase_order.index(state["current_phase"]) if state["current_phase"] in phase_order else 0
        if idx < len(phase_order) - 1:
            new_phase = phase_order[idx + 1]

    logger.info(
        "[CRITIC] Merged: phase1=%d rules, phase2=%d additional, "
        "total=%d, strategy=%s, phase=%s->%s",
        len(phase1_fallacies),
        len(phase2_result.get("additional_fallacies", [])),
        len(all_fallacies),
        selected_strategy,
        state["current_phase"],
        new_phase,
    )

    return {
        "detected_fallacies": all_fallacies,
        "capability_scores": new_scores,
        "current_phase": new_phase,
        "detected_keywords": detected_keywords,
        "probing_strategy": selected_strategy,
        "rule_engine_result": {
            "triggered_rules": [f["rule_id"] for f in phase1_fallacies],
            "gap_fields": rule_result["gap_fields"],
            "evidence_coverage": evidence_result["overall_coverage"],
            "critical_missing_evidence": evidence_result["critical_missing"][:5],
            "phase1_count": len(phase1_fallacies),
            "phase2_count": len(phase2_result.get("additional_fallacies", [])),
        },
    }


# ─────────────────────────────────────────────────────────────
# Node 3: Coach
# ─────────────────────────────────────────────────────────────
# 缺口字段 -> 学生可理解的中文表述
_GAP_LABELS = {
    "target_customer": "目标客户",
    "core_pain_point": "核心痛点",
    "value_proposition": "价值主张",
    "revenue_model": "收入模式",
    "key_channels": "触达渠道",
    "cost_structure": "成本结构",
    "price_point": "定价",
    "team_description": "团队构成",
    "technology_level": "技术路线",
    "stage": "项目阶段",
}


# 修订类任务的识别：手册 U4 要求「只修订受影响的模块，不整体重写，保留模拟标识」
_REVISION_MARKERS = ("新增", "修订", "修改", "变更", "调整", "基于原", "补充两点", "更新")

# 受影响模块的判定关键词
_MODULE_KEYWORDS = {
    "用户场景": ("场景", "用户", "学期", "时点", "集中处理", "频率"),
    "替代方案": ("替代", "竞品", "微信群", "免费", "现有做法"),
    "价值主张": ("价值", "主张", "改善", "收益"),
    "风险与边界": ("风险", "合规", "隐私", "伦理"),
    "定价与成本": ("价格", "定价", "付费", "成本", "元"),
    "渠道与触达": ("渠道", "触达", "推广", "运营"),
}


def _local_revision_reply(state: AgentState, reason: str) -> dict:
    """修订场景的降级输出：只点出受影响的模块，并明确保留模拟标识。"""
    text = state.get("current_input", "")

    affected = [
        name for name, keywords in _MODULE_KEYWORDS.items()
        if any(kw in text for kw in keywords)
    ]
    untouched = [name for name in _MODULE_KEYWORDS if name not in affected]

    affected_text = "、".join(affected) if affected else "用户场景、替代方案"
    untouched_text = "、".join(untouched) if untouched else "其余模块"

    next_task = (
        f"**Task description**：只改写受影响的 {affected_text}，其余模块保持原文不变。\n"
        "**Template/Guideline**：\n"
        "1. 逐条标明新增内容是「模拟 S」还是「事实 F」——教师提供的模拟情境一律标 S；\n"
        "2. 对每个被改写的模块，写一行「原文 → 修改后 → 修改理由」；\n"
        "3. 没有被新信息影响的模块，明确写「本次不修改」。\n"
        "**Acceptance Criteria**：受影响的模块已更新并标注证据类型，未受影响模块未被改写，"
        "每条修改都能说明理由，模拟材料未被表述为真实市场证据。"
    )

    reply = (
        f"⚠️ 当前运行于本地确定性模式（原因：{reason}）。以下反馈来自规则引擎，未调用大模型。\n\n"
        "1. **Project Stage**（项目阶段）：项目骨架已有，本次为增量修订。\n\n"
        "2. **Current Diagnosis**（当前诊断）：\n"
        f"新信息只影响部分模块，应做定点修订而不是整体重写。受影响模块：{affected_text}；"
        f"不受影响、应保持原样的模块：{untouched_text}。\n\n"
        "3. **Evidence Used**（诊断依据）：\n"
        "- 你本次补充的内容属于教师提供的模拟情境，按证据口径标记为 **模拟 S**。\n"
        "- 模拟 S 不能作为真实市场证据，只能用于生成待验证假设。\n"
        "- 本次未命中案例库对标，以上判断仅基于你提供的内容。\n\n"
        "4. **Impact if Unfixed**（不修复后果）：\n"
        "若把模拟情境当作真实证据写入材料，或借修订之名整体重写，会使材料与原始版本无法对照，"
        "评审时无法说明修改理由，也会削弱后续验证的可追溯性。\n\n"
        f"5. **Next Task**（下一步任务）：\n{next_task}\n\n"
        "⚠️ AI辅助分析，仅供参考，请结合实际情况转化"
    )

    return {
        "coach_response": reply,
        "next_task": next_task,
        "thought_process": (
            "本地模式：识别为修订类任务，按模块关键词定位受影响范围，"
            "输出定点修订指令并保留模拟标识。"
        ),
        "degraded_reason": reason,
        "messages": list(state["messages"]) + [
            {"role": "user", "content": state["current_input"]},
            {"role": "assistant", "content": reply},
        ],
        "round_count": state["round_count"] + 1,
    }


def _local_coach_reply(state: AgentState, reason: str) -> dict:
    """LLM 不可用时的确定性降级输出。

    降级输出同样必须满足手册对 F2 的最低完整输出要求：围绕用户、场景、问题、
    证据、方案、创新与风险推进，并给出唯一的下一步任务。因此这里按规则引擎
    的缺口字段生成完整结构，而不是丢一句泛泛的提示——旧实现正是因为在降级
    分支里没有可被解析的任务段落，导致 next_task 恒为空。
    """
    # 修订类任务走单独分支：U4 要求只改受影响模块、保留模拟标识、说明修改理由
    if any(marker in state.get("current_input", "") for marker in _REVISION_MARKERS):
        return _local_revision_reply(state, reason)

    fallacies = state.get("detected_fallacies", [])
    summary = state.get("extracted_data", {}).get("summary", {})
    missing = list(dict.fromkeys(state.get("rule_engine_result", {}).get("gap_fields", []))) or []

    focus = fallacies[0]["description"] if fallacies else "当前描述已形成基础闭环，但证据仍不充分"
    gap_cn = [_GAP_LABELS.get(field, field) for field in missing[:3]]

    if gap_cn:
        task_desc = f"补齐以下尚未提及的关键信息：{'、'.join(gap_cn)}。"
    else:
        task_desc = "为当前最核心的一条结论补充一个可核验来源，或明确标注它是假设。"

    guideline = (
        "1. 用一句话写清「哪类用户在什么场景下遇到什么问题」；\n"
        "2. 对每一条结论标注证据类型：事实 F（附来源）／推断 I／假设 H／模拟 S；\n"
        "3. 没有来源的数字一律标为 H，并写出你打算怎么核验它。"
    )
    criteria = "目标用户可识别、至少一条结论标注了证据类型、无来源数字已标为假设。"

    next_task = (
        f"**Task description**：{task_desc}\n"
        f"**Template/Guideline**：\n{guideline}\n"
        f"**Acceptance Criteria**：{criteria}"
    )

    coach_reply = (
        f"⚠️ 当前运行于本地确定性模式（原因：{reason}）。以下反馈来自规则引擎，未调用大模型。\n\n"
        "1. **Project Stage**（项目阶段）："
        f"{summary.get('stage') or '想法期（尚未提供阶段信息）'}\n\n"
        "2. **Current Diagnosis**（当前诊断）：\n"
        f"{focus}\n\n"
        "3. **Evidence Used**（诊断依据）：\n"
        f"- 目标客户：{summary.get('target_customer') or '未提及'}\n"
        f"- 核心痛点：{summary.get('core_pain_point') or '未提及'}\n"
        f"- 价值主张：{summary.get('value_proposition') or '未提及'}\n"
        "- 本次未命中案例库对标，以上判断仅基于你提供的内容。\n\n"
        "4. **Impact if Unfixed**（不修复后果）：\n"
        "缺少可核验的目标用户与痛点证据时，后续的方案、定价和渠道都建立在假设之上，"
        "无法判断问题是否真实存在。\n\n"
        f"5. **Next Task**（下一步任务）：\n{next_task}\n\n"
        "⚠️ AI辅助分析，仅供参考，请结合实际情况转化"
    )

    return {
        "coach_response": coach_reply,
        "next_task": next_task,
        "thought_process": "本地模式：先运行确定性规则引擎识别缺口，再围绕最高优先级缺口生成唯一行动任务。",
        "degraded_reason": reason,
        "messages": list(state["messages"]) + [
            {"role": "user", "content": state["current_input"]},
            {"role": "assistant", "content": coach_reply},
        ],
        "round_count": state["round_count"] + 1,
    }


async def coach_node(state: AgentState) -> dict:
    """基于审计结果，用苏格拉底提问法生成回复，每次只分配1个行动任务"""
    if not _llm_available():
        return _local_coach_reply(state, "未配置 DeepSeek API Key")

    llm = _get_llm(temperature=0.7)

    master_context = master_coach_engine.retrieve_context()

    agent_mode = state.get("agent_mode", "coach")
    
    if agent_mode == "tutor":
        from prompts.coach_prompt import TUTOR_SYSTEM_PROMPT
        
        # 将检索到的本地图谱节点明文织入Prompt（消除幻觉）
        kb = state.get("kb_context", {})
        r_nodes = kb.get("retrieved_nodes", [])
        retrieved_text = ""
        if r_nodes:
            retrieved_text = "【本地知识图谱检索结果】（请务必根据以下节点实体和属性准确回答，避免泛泛谈论）：\n"
            for n in r_nodes:
                retrieved_text += f"- [{n.get('id')}] : {n.get('desc', '')}\n"
        else:
            retrieved_text = "（本地图谱无需特殊知识介入或未检出强关联节点）\n"
            
        system_prompt = f"{TUTOR_SYSTEM_PROMPT}\n\n[当前项目结构图谱摘要]\n{state.get('hypergraph_summary', '')}\n\n{retrieved_text}"
        
        # 强制日志：写入 DEBUG
        logger.debug("[TUTOR] retrieved_kg_nodes: %s", r_nodes)
        
    elif agent_mode == "competition":
        from prompts.coach_prompt import build_competition_prompt
        # competition mode returns generic rubric items for prompt
        system_prompt = build_competition_prompt(
            competition_name="通用创业大赛评判标准",
            rubric_items=[]  # let it fallback
        )
        system_prompt += f"\n\n[当前项目结构图谱摘要]\n{state.get('hypergraph_summary', '')}"
    else:
        system_prompt = build_coach_prompt(
            phase=state["current_phase"],
            detected_fallacies=state["detected_fallacies"],
            hypergraph_summary=state["hypergraph_summary"],
            master_graph_context=master_context,
            probing_strategy=state.get("probing_strategy", ""),
            kb_context=state.get("kb_context", {}),
            teacher_intervention=state.get("teacher_intervention"),
        )

    # 构建对话历史（最近8条）
    lc_messages = [SystemMessage(content=system_prompt)]
    for msg in state["messages"][-8:]:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        else:
            lc_messages.append(AIMessage(content=msg["content"]))
    lc_messages.append(HumanMessage(content=state["current_input"]))

    try:
        response = await llm.ainvoke(lc_messages)
        coach_reply = response.content
        degraded_reason = None
    except Exception as exc:
        logger.warning("[COACH] LLM unavailable, using local response: %s", exc)
        # 降级到确定性引擎：输出必须仍然完整，且必须如实告知用户当前不是大模型在回答
        return _local_coach_reply(state, f"LLM 调用失败（{type(exc).__name__}）")

    # 提取唯一任务与思考过程
    next_task = _extract_task(coach_reply)

    # === 构建图谱驱动的思维过程展示 ===
    tp_lines = ["=== 🧠 结构化图谱推理引擎 (Graph-Driven Reasoning) ==="]
    
    # 1. 结构化特征与构建局部超图
    ext = state.get("extracted_data", {}).get("summary", {})
    found_nodes = [k for k, v in ext.items() if v and v not in ("未提及", "", None)]
    tp_lines.append("\n[1] 局部超图构建 (Local Hypergraph Parsing)")
    tp_lines.append(f"  ├─ 识别挂载实体节点: {', '.join(found_nodes) if found_nodes else '无显著实体'}")
    tp_lines.append(f"  └─ 子图特征化状态: 映射 {len(found_nodes)} 个维度，阶段指针 [{state.get('current_phase', '')}]")
    
    # 2. 知识检索与对标
    kb = state.get("kb_context", {})
    r_nodes = kb.get("retrieved_nodes", [])
    r_edges = kb.get("retrieved_hyperedges", [])
    s_fails = kb.get("similar_failures", [])
    tp_lines.append("\n[2] Master知识图谱实体寻路 (Knowledge Graph Pathfinding)")
    if r_nodes or r_edges or s_fails:
        if r_nodes:
            node_strs = []
            for n in r_nodes[:3]:
                if isinstance(n, dict):
                    node_strs.append(str(n.get('id', n)) + f"({n.get('source', '图谱数据')})")
                else:
                    node_strs.append(str(n))
            tp_lines.append(f"  ├─ 知识库成功案例标杆命中 (Hit Anchor Nodes): {', '.join(node_strs)}")
        if r_edges: tp_lines.append(f"  ├─ 超边联合态激活 (Hyperedges Match): {', '.join([str(e) for e in r_edges[:3]])}")
        if s_fails:
            fail_str = str(s_fails[0].get('id', s_fails[0]))[:30] + "..." if isinstance(s_fails[0], dict) else str(s_fails[0])[:30] + "..." 
            tp_lines.append(f"  └─ 相似失败演化路径映射 (Failing Paths): {fail_str}")
        else:
            tp_lines.append("  └─ 暂无历史失败教训")
    else:
        tp_lines.append("  └─ 检索策略: 当前项目与【标杆图谱库】重叠度极低，未命中关联业务流实体。")

    # 3. 超图断点审计与谬误识别
    falls = state.get("detected_fallacies", [])
    tp_lines.append("\n[3] 超图拓扑断点审计 (Logical Fallacy Engine)")
    if falls:
        tp_lines.append(f"  ├─ 拓扑闭环检测阻断，触发规则: {', '.join([f['rule_id'] for f in falls])}")
        tp_lines.append(f"  └─ 最高优逻辑断链溯源: {falls[0].get('name', 'N/A')} -> {falls[0].get('description', '')[:30]}...")
    else:
        tp_lines.append("  └─ 未探测到结构上的致命断链。")

    tp_lines.append(f"\n[4] 教练反馈熔铸 (Prompt Assembly)")
    tp_lines.append(f"  ├─ 决策选定苏格拉底追问网: {state.get('probing_strategy', '默认')}")
    tp_lines.append(f"  └─ (执行大模型渲染): 拼装上述「{len(falls)}条断链」与「{len(r_nodes)}个案例先验知识」生成终态指引。")
    
    thought_process = "\n".join(tp_lines)

    new_messages = list(state["messages"]) + [
        {"role": "user", "content": state["current_input"]},
        {"role": "assistant", "content": coach_reply},
    ]

    logger.info(
        "[COACH] agent_name=coach round=%d phase=%s strategy=%s next_task_extracted=%s",
        state["round_count"] + 1,
        state["current_phase"],
        state.get("probing_strategy", ""),
        bool(next_task),
    )

    return {
        "coach_response": coach_reply,
        "next_task": next_task,
        "thought_process": thought_process,
        "degraded_reason": degraded_reason,
        "messages": new_messages,
        "round_count": state["round_count"] + 1,
    }


# ---------------------------------------------------------------
# Node 4: Rubric Scoring (Direction-5: score_floor + score_delta)
# ---------------------------------------------------------------
_RUBRIC_SCORING_PROMPT_V2 = (
    "You are a competition advisor (Phase 2). "
    "Phase 1 (evidence engine) computed these score floors:\n"
    "{floor_summary}\n\n"
    "Your job: provide score_delta for each R1-R9 on top of the floor. "
    "Delta range: [-1, +{max_delta}]. "
    "Base your delta on narrative quality, logic depth, innovativeness.\n\n"
    "{competition_context}\n\n"
    "Project text:\n{project_text}\n\n"
    "Return STRICT JSON:\n"
    '{{\n'
    '  "rubric_deltas": {{\n'
    '    "R1": {{\n'
    '      "score_delta": 1,\n'
    '      "reasoning": "clear narrative, deep user portrait",\n'
    '      "missing_evidence": ["missing user interviews"],\n'
    '      "fix_24h": "do 5 phone interviews today",\n'
    '      "fix_72h": "complete 30 surveys"\n'
    '    }}\n'
    '  }},\n'
    '  "critical_gaps": ["top 3 gaps"],\n'
    '  "quick_wins": ["top 3 quick actions"]\n'
    '}}\n'
    "Cover R1-R9. If floor <= 1, missing_evidence must not be empty."
)


async def rubric_scoring_node(state: AgentState) -> dict:
    """Competition advisor: Phase1(floor engine) + Phase2(LLM delta)."""

    competition_name = state.get("competition_mode") or "China Internet+ Innovation Competition"
    competition_context = build_competition_prompt(competition_name, RUBRIC_ITEMS)

    project_text = state["current_input"]
    if state.get("hypergraph_summary"):
        project_text += f"\n\nProject structure:\n{state['hypergraph_summary']}"

    conversation_text = "\n".join([
        f"{'student' if m['role'] == 'user' else 'coach'}: {m['content']}"
        for m in state["messages"][-6:]
    ]) if state["messages"] else ""

    # == Phase 1 (non-LLM): compute score floors ==
    summary_data = state.get("extracted_data", {}).get("summary", {})

    evidence_result = check_evidence_gaps(
        extracted_data=state.get("extracted_data", {}),
        conversation_text=conversation_text + " " + state["current_input"],
    )

    floors = compute_score_floors(
        extracted_summary=summary_data,
        evidence_result=evidence_result,
        conversation_text=conversation_text,
    )

    floor_lines = []
    for item in RUBRIC_ITEMS:
        rid = item["id"]
        fi = floors.get(rid, {})
        floor_lines.append(
            f"{rid} {item['name']}: floor={fi.get('score_floor', 0)}/5, "
            f"max_delta={fi.get('max_delta', 2)}, "
            f"reason={fi.get('floor_reason', 'N/A')}"
        )
    floor_summary = "\n".join(floor_lines)

    logger.info("[RUBRIC] Phase1 floors: %s",
                {rid: f["score_floor"] for rid, f in floors.items()})

    # == Phase 2 (LLM): delta on top of floors ==
    # 此处必须容错：LLM 不可用时应退化为「仅使用证据引擎算出的分数下限」，
    # 而不是让异常冒泡打断整个流程。原实现没有 try/except，一旦此节点被接入
    # 工作流，API 失败就会直接击穿请求。
    llm_result: dict = {"rubric_deltas": {}, "critical_gaps": [], "quick_wins": []}
    if _llm_available():
        llm = _get_llm(temperature=0.2)
        messages = [
            SystemMessage(content=_RUBRIC_SCORING_PROMPT_V2.format(
                floor_summary=floor_summary,
                max_delta="2",
                competition_context=competition_context,
                project_text=project_text[:3000],
            )),
            HumanMessage(content="Output score_delta for each R1-R9."),
        ]
        try:
            response = await llm.ainvoke(messages)
            llm_result = _parse_json_response(response.content, llm_result)
        except Exception as exc:
            logger.warning("[RUBRIC] LLM delta unavailable, floors only: %s", exc)
    else:
        logger.info("[RUBRIC] LLM not configured, using evidence-engine floors only")

    # == Merge: floor + delta -> final ==
    llm_deltas = llm_result.get("rubric_deltas", {})
    score_breakdown = apply_delta_to_floors(floors, llm_deltas)

    final_scores_list = [v["final_score"] for v in score_breakdown.values()]
    overall_score = round(
        sum(final_scores_list) / len(final_scores_list), 1
    ) if final_scores_list else 0.0

    logger.info("[RUBRIC] Phase2 done: overall=%.1f", overall_score)

    # == Build reply with breakdown table ==
    reply_lines = [
        f"**{competition_name} Rubric Scoring (Floor + Delta)**",
        "",
        "| Dimension | Floor | Delta | Final | Key Gap |",
        "|-----------|-------|-------|-------|---------|",
    ]
    for item in RUBRIC_ITEMS:
        rid = item["id"]
        bd = score_breakdown.get(rid, {})
        floor_val = bd.get("score_floor", "?")
        delta_val = bd.get("score_delta", 0)
        final_val = bd.get("final_score", "?")
        delta_str = f"+{delta_val}" if delta_val >= 0 else str(delta_val)
        missing = bd.get("missing_evidence", [])
        gap_text = "; ".join(missing[:2]) if missing else "OK"
        reply_lines.append(
            f"| {item['name']} | {floor_val} | {delta_str} | "
            f"**{final_val}/5** | {gap_text} |"
        )

    reply_lines += [
        "",
        f"**Overall: {overall_score:.1f} / 5.0**",
        "",
        "Floor = evidence-engine auto-score; Delta = AI quality assessment",
        "",
        "**Key gaps to fix:**",
    ]
    for gap in llm_result.get("critical_gaps", []):
        reply_lines.append(f"* {gap}")
    reply_lines += ["", "**Quick wins:**"]
    for win in llm_result.get("quick_wins", []):
        reply_lines.append(f"* {win}")
    reply_lines.append("\nAI-assisted scoring, for reference only.")
    coach_reply = "\n".join(reply_lines)

    # Build backward-compatible rubric_scores
    rubric_scores = {}
    for rid, bd in score_breakdown.items():
        delta_info = llm_deltas.get(rid, {})
        rubric_scores[rid] = {
            "score": bd["final_score"],
            "score_floor": bd["score_floor"],
            "score_delta": bd["score_delta"],
            "missing_evidence": bd.get("missing_evidence", delta_info.get("missing_evidence", [])),
            "fix_24h": delta_info.get("fix_24h", ""),
            "fix_72h": delta_info.get("fix_72h", ""),
            "floor_reason": bd.get("floor_reason", ""),
            "delta_reason": bd.get("delta_reason", ""),
        }

    new_messages = list(state["messages"]) + [
        {"role": "user", "content": state["current_input"]},
        {"role": "assistant", "content": coach_reply},
    ]

    return {
        "rubric_scores": rubric_scores,
        "score_breakdown": score_breakdown,
        "coach_response": coach_reply,
        "messages": new_messages,
        "round_count": state["round_count"] + 1,
        "next_task": llm_result.get("quick_wins", [""])[0] if llm_result.get("quick_wins") else "",
    }

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _extract_task(reply: str) -> str:
    """从教练回复中提取唯一【任务】部分"""
    for marker in ["5. **Next Task", "5. Next Task", "下一步任务：", "【任务】", "**任务**", "任务："]:
        if marker in reply:
            idx = reply.index(marker)
            task_text = reply[idx:].strip()
            # We don't remove the marker itself here so the student sees the task description and guidelines
            return task_text
    return ""


def _parse_json_response(content: str, fallback: dict) -> dict:
    """安全解析 LLM 返回的 JSON"""
    content = content.strip()
    if "```" in content:
        parts = content.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return fallback
