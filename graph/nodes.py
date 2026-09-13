"""
三个核心 LangGraph 节点（V2 升级）：
  extractor_node  → 提取商业要素，构建超图，记录日志
  critic_node     → H1-H20 规则审计 + 追问策略选择 + 超图溯源日志
  coach_node      → 苏格拉底式提问 + 单任务分配 + Rubric 打分

新增：
  rubric_scoring_node  → 逐项 Rubric 评分（R1-R9）
  competition_node     → 竞赛顾问模式路由
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
async def coach_node(state: AgentState) -> dict:
    """基于审计结果，用苏格拉底提问法生成回复，每次只分配1个行动任务"""
    if not _llm_available():
        fallacies = state.get("detected_fallacies", [])
        summary = state.get("extracted_data", {}).get("summary", {})
        missing = state.get("rule_engine_result", {}).get("gap_fields", [])
        focus = fallacies[0]["description"] if fallacies else "当前描述已经形成基础闭环"
        next_task = "请补充一个具体客户、一个真实痛点证据，以及客户目前采用的替代方案。"
        if missing:
            next_task = f"请优先补充：{', '.join(dict.fromkeys(missing[:3]))}。每项都给出一个具体事实或数字。"
        coach_reply = (
            "这是本地诊断模式：当前未配置 DeepSeek API Key，因此先使用规则引擎给你反馈。\n\n"
            f"**当前最需要验证的点**：{focus}\n\n"
            f"你刚才的输入已记录。目标客户：{summary.get('target_customer', '未提及')}；"
            f"核心痛点：{summary.get('core_pain_point', '未提及')}。\n\n"
            "不要先扩展功能，请先把下面这一条证据补齐。"
        )
        new_messages = list(state["messages"]) + [
            {"role": "user", "content": state["current_input"]},
            {"role": "assistant", "content": coach_reply},
        ]
        return {
            "coach_response": coach_reply,
            "next_task": next_task,
            "thought_process": "本地模式：先运行确定性规则，再围绕最高优先级缺口生成一条行动任务。",
            "messages": new_messages,
            "round_count": state["round_count"] + 1,
        }

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
    except Exception as exc:
        logger.warning("[COACH] LLM unavailable, using local response: %s", exc)
        fallacies = state.get("detected_fallacies", [])
        missing = state.get("rule_engine_result", {}).get("gap_fields", [])
        focus = fallacies[0]["description"] if fallacies else "当前描述已经形成基础闭环"
        coach_reply = (
            "当前使用本地诊断模式：AI 服务暂时不可用，先用规则引擎给你反馈。\n\n"
            f"**最需要验证的点**：{focus}\n\n"
            "不要先扩展功能，请先补齐一条可验证证据。"
        )
        if missing:
            coach_reply += f"\n\n缺失字段：{', '.join(dict.fromkeys(missing[:3]))}。"

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

    response = await llm.ainvoke(messages)
    llm_result = _parse_json_response(response.content, {
        "rubric_deltas": {},
        "critical_gaps": [],
        "quick_wins": [],
    })

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
