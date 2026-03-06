"""
超图数据结构定义
将学生的自然语言描述映射为机器可审计的结构化节点与超边
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid


class NodeType(str, Enum):
    CONCEPT = "concept"      # 概念：目标客群、核心痛点、价值主张、竞争优势
    METHOD = "method"        # 方法：获客方式、盈利模式、运营策略
    ARTIFACT = "artifact"    # 产出物：MVP、原型、产品功能
    METRIC = "metric"        # 指标：价格、成本、LTV、CAC、GMV等数字


class Node(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: NodeType
    label: str
    value: Optional[Any] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class HyperedgeType(str, Enum):
    BUSINESS_MODEL = "business_model_consistency"   # 商业模式一致性
    MARKET_FIT = "customer_market_fit"              # 客户市场匹配
    UNIT_ECONOMICS = "unit_economics"               # 单位经济
    RESOURCE_MATCH = "resource_capability_match"    # 资源能力匹配


class Hyperedge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: HyperedgeType
    node_ids: List[str]
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class BusinessHypergraph(BaseModel):
    nodes: Dict[str, Node] = Field(default_factory=dict)
    hyperedges: List[Hyperedge] = Field(default_factory=list)

    def add_node(self, node: Node) -> str:
        self.nodes[node.id] = node
        return node.id

    def add_hyperedge(self, edge: Hyperedge):
        self.hyperedges.append(edge)

    def to_summary(self) -> str:
        if not self.nodes:
            return "超图暂无节点（信息尚未提取）"
        lines = ["【项目超图结构】"]
        type_labels = {
            "concept": "概念",
            "method": "方法",
            "artifact": "产出物",
            "metric": "指标"
        }
        for node in self.nodes.values():
            type_cn = type_labels.get(node.type.value, node.type.value)
            val = f" = {node.value}" if node.value else ""
            lines.append(f"  [{type_cn}] {node.label}{val}")
        if self.hyperedges:
            lines.append("【超边关联】")
            edge_type_labels = {
                "business_model_consistency": "商业模式一致性",
                "customer_market_fit": "客户市场匹配",
                "unit_economics": "单位经济",
                "resource_capability_match": "资源能力匹配"
            }
            for edge in self.hyperedges:
                type_cn = edge_type_labels.get(edge.type.value, edge.type.value)
                related = [self.nodes[nid].label for nid in edge.node_ids if nid in self.nodes]
                lines.append(f"  ⟨{type_cn}⟩ {edge.label} → [{', '.join(related)}]")
        return "\n".join(lines)
