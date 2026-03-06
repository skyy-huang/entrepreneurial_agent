"""
商业要素提取器
使用 DeepSeek LLM 将学生的自然语言输入转化为结构化超图节点和超边
"""
import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .schema import BusinessHypergraph, Node, Hyperedge, NodeType, HyperedgeType


def get_llm(temperature: float = 0.1) -> ChatOpenAI:
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        temperature=temperature,
    )


EXTRACTION_SYSTEM_PROMPT = """你是一个商业要素提取专家。从学生的创业描述中提取结构化商业要素，用于后续逻辑审计。

返回严格的JSON格式，不要有任何其他文字：
{
  "nodes": [
    {"type": "concept|method|artifact|metric", "label": "节点名称", "value": "具体数值或描述（无则null）"}
  ],
  "hyperedges": [
    {
      "type": "business_model_consistency|customer_market_fit|unit_economics|resource_capability_match",
      "label": "超边描述",
      "node_labels": ["关联的节点label列表"]
    }
  ],
  "summary": {
    "target_customer": "目标客群（尽量具体）",
    "core_pain_point": "核心痛点",
    "value_proposition": "价值主张",
    "revenue_model": "收入模式",
    "key_channels": "关键渠道",
    "cost_structure": "主要成本项",
    "price_point": "定价（有数字尽量提取数字）",
    "team_description": "团队描述",
    "technology_level": "技术水平：idea/prototype/mvp/product",
    "stage": "当前阶段：idea/validation/early_revenue/scaling"
  }
}

节点类型说明：
- concept: 概念类（目标客群、核心痛点、价值主张、竞争优势）
- method: 方法类（获客方式、盈利模式、运营策略）
- artifact: 产出物（MVP、原型、产品功能）
- metric: 指标类（价格、成本、LTV、CAC、GMV等具体数字）

超边类型说明：
- business_model_consistency: 聚合[客户+渠道+价格+成本]检测商业模式一致性
- customer_market_fit: 聚合[客群+痛点+解决方案]检测需求匹配
- unit_economics: 聚合[定价+成本+获客费用]检测单位经济
- resource_capability_match: 聚合[团队+技术+资源需求]检测能力匹配

如果信息不足，nodes 和 hyperedges 可以为空数组，summary字段填写"未提及"。"""


async def extract_business_elements(text: str, conversation_history: list) -> dict:
    """从学生输入和对话历史中提取结构化商业要素"""
    llm = get_llm()

    # 取最近6条对话作为上下文
    history_text = "\n".join([
        f"{'学生' if m['role'] == 'user' else '教练'}: {m['content']}"
        for m in conversation_history[-6:]
    ]) if conversation_history else "（无历史对话）"

    user_content = f"""历史对话（上下文参考）：
{history_text}

学生最新输入：
{text}

请提取以上内容中的商业要素。"""

    messages = [
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    response = await llm.ainvoke(messages)

    try:
        content = response.content.strip()
        # 清理 markdown 代码块
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
        return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return _empty_extraction()


def build_hypergraph_from_extraction(extracted: dict) -> BusinessHypergraph:
    """将提取结果构建为超图对象"""
    hg = BusinessHypergraph()
    label_to_id: dict = {}

    for node_data in extracted.get("nodes", []):
        type_str = node_data.get("type", "concept")
        try:
            node_type = NodeType(type_str)
        except ValueError:
            node_type = NodeType.CONCEPT

        node = Node(
            type=node_type,
            label=node_data.get("label", "未知"),
            value=node_data.get("value"),
        )
        node_id = hg.add_node(node)
        label_to_id[node.label] = node_id

    for edge_data in extracted.get("hyperedges", []):
        type_str = edge_data.get("type", "business_model_consistency")
        try:
            edge_type = HyperedgeType(type_str)
        except ValueError:
            edge_type = HyperedgeType.BUSINESS_MODEL

        node_ids = [
            label_to_id[label]
            for label in edge_data.get("node_labels", [])
            if label in label_to_id
        ]
        if node_ids:
            edge = Hyperedge(
                type=edge_type,
                node_ids=node_ids,
                label=edge_data.get("label", ""),
            )
            hg.add_hyperedge(edge)

    return hg


def _empty_extraction() -> dict:
    return {
        "nodes": [],
        "hyperedges": [],
        "summary": {
            "target_customer": "未提及",
            "core_pain_point": "未提及",
            "value_proposition": "未提及",
            "revenue_model": "未提及",
            "key_channels": "未提及",
            "cost_structure": "未提及",
            "price_point": "未提及",
            "team_description": "未提及",
            "technology_level": "idea",
            "stage": "idea",
        },
    }
