"""
AgentState 定义
记录整个对话流程中的所有状态信息
V2 升级：加入 Rubric 评分、追问策略、知识图谱上下文、竞赛模式
"""
from typing import TypedDict, List, Dict, Any, Optional


class AgentState(TypedDict):
    # ── 会话基本信息 ──────────────────────────────────────────
    session_id: str
    student_id: str
    industry: Optional[str]
    level: Optional[str]

    # ── 对话历史 [{role: user/assistant, content: ...}] ──────
    messages: List[Dict[str, str]]

    # ── 当前学生输入 ──────────────────────────────────────────
    current_input: str

    # ── 提取器输出：结构化商业要素 ────────────────────────────
    extracted_data: Dict[str, Any]

    # ── 超图文本摘要（用于 Prompt 注入）──────────────────────
    hypergraph_summary: str

    # ── 审计器输出：触发的逻辑谬误列表 ──────────────────────
    # [{rule_id, name, description, evidence, severity, confidence, impact, fix_task}]
    detected_fallacies: List[Dict[str, Any]]

    # ── 五维能力得分 (0-10) ───────────────────────────────────
    # 痛点发现 / 方案策划 / 商业建模 / 资源杠杆 / 路演表达
    capability_scores: Dict[str, float]

    # ── Rubric 逐项评分 (R1-R9, 0-5) ─────────────────────────
    rubric_scores: Dict[str, Dict[str, Any]]  # {R1: {score, evidence, missing, fix_24h, fix_72h}}

    # ── 评分分解（方向5：可计算部分 + LLM 部分）────────────────
    # {R1: {final_score, score_floor, score_delta, floor_reason, delta_reason, ...}}
    score_breakdown: Dict[str, Dict[str, Any]]

    # ── Phase 1 规则引擎结果（方向2：Cheap-First）────────────────
    # {triggered_rules: [...], gap_fields: [...], confidence_map: {...}}
    rule_engine_result: Dict[str, Any]

    # ── 对话阶段: value_probe / pressure_test / landing_check
    current_phase: str

    # ── 检测到的谬误关键词（用于策略选择）────────────────────
    detected_keywords: List[str]

    # ── 选定的追问策略（来自策略库）──────────────────────────
    probing_strategy: str

    # ── 知识图谱检索上下文（用于日志和追问）─────────────────
    kb_context: Dict[str, Any]

    # ── 检索到的超图边类型（用于日志可观测性）────────────────
    retrieved_hyperedge_types: List[str]

    # ── 教练给学生的下一步行动任务 ───────────────────────────
    next_task: str

    # ── 当前激活的智能体模式 ────────────────────────────────────
    agent_mode: str

    # ── 系统的思维诊断过程 ────────────────────────────────────
    thought_process: str

    # ── 教练最终回复内容 ──────────────────────────────────────
    coach_response: str

    # ── 对话总轮数 ────────────────────────────────────────────
    round_count: int

    # ── 竞赛模式：存储当前激活的赛事名称 ────────────────────
    competition_mode: Optional[str]

    # ── 教师干预策略（由教师后台配置，实时注入对话）──────────
    teacher_intervention: Optional[str]

    # ── 角色类型：student / teacher / admin ───────────────────
    user_role: str


def make_initial_state(session_id: str, student_id: str, user_role: str = "student", industry: Optional[str] = None, level: Optional[str] = None) -> AgentState:
    return AgentState(
        session_id=session_id,
        student_id=student_id,
        industry=industry,
        level=level,
        messages=[],
        current_input="",
        extracted_data={},
        hypergraph_summary="",
        detected_fallacies=[],
        capability_scores={
            "pain_point_discovery": 5.0,   # 痛点发现
            "solution_planning": 5.0,       # 方案策划
            "business_modeling": 5.0,       # 商业建模
            "resource_leverage": 5.0,       # 资源杠杆
            "pitch_expression": 5.0,        # 路演表达
        },
        rubric_scores={},
        score_breakdown={},
        rule_engine_result={},
        current_phase="value_probe",
        detected_keywords=[],
        probing_strategy="evidence_challenge",
        kb_context={},
        retrieved_hyperedge_types=[],
        next_task="",
        agent_mode="coach",
        thought_process="",
        coach_response="",
        round_count=0,
        competition_mode=None,
        teacher_intervention=None,
        user_role=user_role,
    )
