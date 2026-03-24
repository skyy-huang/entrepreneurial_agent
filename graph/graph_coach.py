import json
import os
import networkx as nx
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

def _get_llm(temperature: float = 0.5) -> ChatOpenAI:
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        temperature=temperature,
    )

class GraphCoach:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "..", "data", "master_graph.json")
        self.db_path = db_path
        self.graph = nx.DiGraph()
        self.hyperedges = []
        self._load_graph()

    def _load_graph(self):
        """将 JSON 数据加载到 NetworkX 图和超边列表中"""
        if not os.path.exists(self.db_path):
            print("未找到 master_graph.json，图谱为空。请先运行 build_graph.py")
            return

        with open(self.db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for node in data.get("nodes", []):
            self.graph.add_node(node["id"], type=node.get("type"), description=node.get("description"))

        for edge in data.get("edges", []):
            self.graph.add_edge(edge["source"], edge["target"], relation=edge.get("relation"))
            
        for hedge in data.get("hyperedges", []):
            self.hyperedges.append(hedge)
            
    def retrieve_context(self) -> str:
        """从图谱和超图中提取成功案例的商业逻辑上下文"""
        if self.graph.number_of_nodes() == 0 and len(self.hyperedges) == 0:
            return "目前缺乏成功案例的支撑数据。"
            
        edges_summary = []
        for u, v, data in self.graph.edges(data=True):
            edges_summary.append(f"[{u}] -({data.get('relation', '关联')})-> [{v}]")
            
        hyperedges_summary = []
        for hedge in self.hyperedges:
            nodes_str = " + ".join([f"[{n}]" for n in hedge.get("nodes", [])])
            hyperedges_summary.append(f"超边逻辑【{hedge.get('id', '未命名')}】: {nodes_str}\n  说明: {hedge.get('description', '')}")
            
        context = "【成功商业案例二元逻辑】:\n" + "\n".join(edges_summary[:100])
        context += "\n\n【成功商业案例超图（多维协同）逻辑】:\n" + "\n".join(hyperedges_summary[:50])
        return context

    async def generate_coaching_suggestions(self, new_project_text: str) -> str:
        """结合图谱上下文评估新项目"""
        graph_context = self.retrieve_context()
        
        prompt = f"""作为一个基于知识图谱的双创智能教练，你需要评估一份新的商业计划。
        
以下是基于以往【优秀案例】构建的商业路径逻辑（图谱边关系形式）：
{graph_context}

以下是【新项目计划书】的摘要和说明：
{new_project_text[:5000]}

请对比图谱中成功案例的逻辑，指出新计划书中可能缺失的成功要素（例如：是否有技术但缺乏变现场景？是否有痛点但缺乏特定的解决方案对标？）。
请给出具体的、带有实操性的建议。"""

        llm = _get_llm(temperature=0.7)
        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            print(f"Error generating suggestions: {e}")
            return "生成建议时发生错误。"