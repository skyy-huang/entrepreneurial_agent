"""
AgentState 定义
记录整个对话流程中的所有状态信息，包括对话历史、超图、审计结果和能力得分
"""
from typing import TypedDict, List, Dict, Any


class AgentState(TypedDict):
    # 会话基本信息
    session_id: str
    student_id: str

    # 对话历史 [{"role": "user/assistant", "content": "..."}]
    messages: List[Dict[str, str]]

    # 当前学生输入
    current_input: str

    # 提取器输出：结构化商业要素
    extracted_data: Dict[str, Any]

    # 超图文本摘要（用于 Prompt 注入）
    hypergraph_summary: str

    # 审计器输出：触发的逻辑谬误列表
    # [{"rule_id": "H8", "name": "...", "description": "...", "evidence": "...", "severity": "high", "confidence": 0.9}]
    detected_fallacies: List[Dict[str, Any]]

    # 五维能力得分 (0-10)
    # keys: pain_point_discovery, solution_planning, business_modeling, resource_leverage, pitch_expression
    capability_scores: Dict[str, float]

    # 对话阶段: value_probe / pressure_test / landing_check
    current_phase: str

    # 教练给学生的下一步行动任务
    next_task: str

    # 教练最终回复内容
    coach_response: str

    # 对话总轮数
    round_count: int

    # 已解析的文件摘要（可为空字符串）
    uploaded_file_summary: str


def make_initial_state(session_id: str, student_id: str) -> AgentState:
    return AgentState(
        session_id=session_id,
        student_id=student_id,
        messages=[],
        current_input="",
        extracted_data={},
        hypergraph_summary="",
        detected_fallacies=[],
        capability_scores={
            "pain_point_discovery": 5.0,
            "solution_planning": 5.0,
            "business_modeling": 5.0,
            "resource_leverage": 5.0,
            "pitch_expression": 5.0,
        },
        current_phase="value_probe",
        next_task="",
        coach_response="",
        round_count=0,
        uploaded_file_summary="",
    )
