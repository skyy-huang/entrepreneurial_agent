"""
三个核心 LangGraph 节点：
  extractor_node  → 提取商业要素，构建超图
  critic_node     → 调用 H1-H15 规则进行逻辑审计
  coach_node      → 苏格拉底式提问 + 分配行动任务
"""
import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .state import AgentState
from hypergraph.extractor import extract_business_elements, build_hypergraph_from_extraction
from hypergraph.rules import get_rules_for_prompt
from prompts.coach_prompt import build_coach_prompt


def _get_llm(temperature: float = 0.3) -> ChatOpenAI:
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        temperature=temperature,
    )


# ─────────────────────────────────────────────────────────────
# Node 1: Extractor
# ─────────────────────────────────────────────────────────────
async def extractor_node(state: AgentState) -> dict:
    """从学生输入中提取结构化商业要素，构建超图"""
    extracted = await extract_business_elements(
        state["current_input"],
        state["messages"],
    )
    hg = build_hypergraph_from_extraction(extracted)
    return {
        "extracted_data": extracted,
        "hypergraph_summary": hg.to_summary(),
    }


# ─────────────────────────────────────────────────────────────
# Node 2: Critic
# ─────────────────────────────────────────────────────────────
_CRITIC_SYSTEM_PROMPT = """你是一个专业的商业逻辑审计专家，基于超图结构对学生的创业计划进行严格审计。

你将收到：对话历史、提取的商业要素、超图结构。
你的任务：检查 H1-H15 中哪些规则被触发，输出严格 JSON。

{rules}

返回格式（严格JSON，不要有任何其他文字）：
{{
  "detected_fallacies": [
    {{
      "rule_id": "H8",
      "name": "单位经济不成立",
      "description": "规则简述",
      "evidence": "从对话中找到的具体证据，引用学生原话或数字",
      "severity": "high",
      "confidence": 0.9
    }}
  ],
  "capability_score_updates": {{
    "pain_point_discovery": 6.0,
    "solution_planning": 4.0,
    "business_modeling": 3.0,
    "resource_leverage": 5.0,
    "pitch_expression": 7.0
  }},
  "should_advance_phase": false,
  "audit_summary": "一句话总结审计结果"
}}

打分规则（0-10分）：
- 根据学生在对话中展现的思考深度和证据质量评分
- 只更新你有足够证据评估的维度；confidence < 0.6 的漏洞不纳入 detected_fallacies
- should_advance_phase=true 的条件：当前阶段无高严重度漏洞，且学生展现了基本的逻辑自洽"""


async def critic_node(state: AgentState) -> dict:
    """调用 H1-H15 规则对超图进行逻辑审计，输出检测到的谬误"""
    llm = _get_llm(temperature=0.1)

    conversation_text = "\n".join([
        f"{'学生' if m['role'] == 'user' else '教练'}: {m['content']}"
        for m in state["messages"][-10:]
    ]) if state["messages"] else "（无历史对话）"

    summary_data = state.get("extracted_data", {}).get("summary", {})
    extracted_summary = json.dumps(summary_data, ensure_ascii=False, indent=2)

    user_content = f"""对话历史：
{conversation_text}

学生最新输入：{state['current_input']}

提取的商业要素摘要：
{extracted_summary}

超图结构：
{state.get('hypergraph_summary', '暂无')}

当前阶段：{state['current_phase']}（value_probe=价值探测 / pressure_test=压力测试 / landing_check=落地校验）
当前轮次：{state['round_count']}
当前能力得分：{json.dumps(state['capability_scores'], ensure_ascii=False)}

请对以上信息进行逻辑审计。"""

    messages = [
        SystemMessage(content=_CRITIC_SYSTEM_PROMPT.format(rules=get_rules_for_prompt())),
        HumanMessage(content=user_content),
    ]

    response = await llm.ainvoke(messages)
    audit_result = _parse_json_response(response.content, {
        "detected_fallacies": [],
        "capability_score_updates": state["capability_scores"],
        "should_advance_phase": False,
        "audit_summary": "审计解析失败",
    })

    # 渐进式更新能力得分（新值权重 30%，防止单次大幅波动）
    new_scores = dict(state["capability_scores"])
    for key, val in audit_result.get("capability_score_updates", {}).items():
        if key in new_scores and isinstance(val, (int, float)):
            new_scores[key] = round(new_scores[key] * 0.7 + float(val) * 0.3, 1)

    # 阶段推进
    new_phase = state["current_phase"]
    if audit_result.get("should_advance_phase"):
        phase_order = ["value_probe", "pressure_test", "landing_check"]
        idx = phase_order.index(state["current_phase"])
        if idx < len(phase_order) - 1:
            new_phase = phase_order[idx + 1]

    return {
        "detected_fallacies": audit_result.get("detected_fallacies", []),
        "capability_scores": new_scores,
        "current_phase": new_phase,
    }


# ─────────────────────────────────────────────────────────────
# Node 3: Coach
# ─────────────────────────────────────────────────────────────
async def coach_node(state: AgentState) -> dict:
    """基于审计结果，用苏格拉底提问法生成回复，每次只分配1个行动任务"""
    llm = _get_llm(temperature=0.7)

    system_prompt = build_coach_prompt(
        phase=state["current_phase"],
        detected_fallacies=state["detected_fallacies"],
        hypergraph_summary=state["hypergraph_summary"],
    )

    # 构建对话历史（最近8条）
    lc_messages = [SystemMessage(content=system_prompt)]
    for msg in state["messages"][-8:]:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        else:
            lc_messages.append(AIMessage(content=msg["content"]))
    lc_messages.append(HumanMessage(content=state["current_input"]))

    response = await llm.ainvoke(lc_messages)
    coach_reply = response.content

    # 提取任务
    next_task = _extract_task(coach_reply)

    # 更新对话历史
    new_messages = list(state["messages"]) + [
        {"role": "user", "content": state["current_input"]},
        {"role": "assistant", "content": coach_reply},
    ]

    return {
        "coach_response": coach_reply,
        "next_task": next_task,
        "messages": new_messages,
        "round_count": state["round_count"] + 1,
    }


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _extract_task(reply: str) -> str:
    """从教练回复中提取【任务】部分"""
    for marker in ["【任务】", "**任务**", "任务：", "下一步任务："]:
        if marker in reply:
            idx = reply.index(marker) + len(marker)
            task_line = reply[idx:].split("\n")[0].strip()
            # 去除可能的 markdown 粗体标记
            return task_line.replace("**", "").strip()
    return ""


def _parse_json_response(content: str, fallback: dict) -> dict:
    """安全解析 LLM 返回的 JSON"""
    content = content.strip()
    # 尝试清理 markdown 代码块
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
