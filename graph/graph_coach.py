import json
import os
import networkx as nx
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

def _get_llm(temperature=0.2):
    return ChatOpenAI(
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        temperature=temperature,
        api_key=os.environ.get("DEEPSEEK_API_KEY", "")
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
            
    def get_relevant_nodes(self, query, top_k: int = 5, industry: str = None, level: str = None) -> list:
        """从图谱中获取与当前内容最相关的成功案例节点（放宽检索条件）"""
        if isinstance(query, dict):
            query_str = " ".join(str(v) for v in query.values() if v and v != "未提及")
        else:
            query_str = str(query)

        if self.graph.number_of_nodes() == 0:
            return {"nodes": [], "edges": []}

        # 提取关键词 (Bigram 拆词法)
        common_stop_words = {"的", "和", "是", "在", "项目", "我们", "平台", "系统", "服务", "产品", "未提", "提及"}
        bigrams = {query_str[i:i+2] for i in range(len(query_str)-1)}
        keywords = {bg for bg in bigrams if not any(sw in bg for sw in common_stop_words)}
        
        scored_nodes = []
        for n, data in self.graph.nodes(data=True):
            score = 0
            if n in query_str:
                score += 20
            
            desc = data.get("description", "")
            if desc:
                # 按关键词重叠度评分
                for kw in keywords:
                    if kw in desc or kw in n:
                        score += 5
                        
            # Filter/Boost attributes
            n_industry = data.get("industry")
            n_level = data.get("level")
            
            if industry and n_industry == industry:
                score += 15
            if level and n_level == level:
                score += 10
            
            if score > 0:
                scored_nodes.append(({"id": n, "source_file": data.get("source_file", ""), **data}, score))
                
        scored_nodes.sort(key=lambda x: x[1], reverse=True)
        
        # 去重，尽量展示不同的实际案例实体
        results = {"nodes": [], "edges": []}
        seen = set()
        for node, score in scored_nodes:
            if node["id"] not in seen:
                seen.add(node["id"])
                results["nodes"].append({"id": node["id"], "desc": node.get("description", ""), "source": node.get("source_file", "")})
            if len(results["nodes"]) >= top_k:
                break
                
        # 提取与被选中节点相关的关系
        for u, v, k, e_data in self.graph.edges(keys=True, data=True) if self.graph.is_multigraph() else []:
            pass # fallback if needed, but the init says nx.DiGraph()
            
        for u, v, e_data in self.graph.edges(data=True):
            if u in seen or v in seen:
                results["edges"].append({
                    "source": u,
                    "target": v,
                    "relation": e_data.get("relation", ""),
                    "source_file": e_data.get("source_file", "")
                })
                
        return results

    def get_similar_failure_cases(self, query, top_k: int = 3, industry: str = None, level: str = None) -> list:
        """检索相关的超边逻辑，作为前车之鉴或标杆对标"""
        if isinstance(query, dict):
            query_str = " ".join(str(v) for v in query.values() if v and v != "未提及")
        else:
            query_str = str(query)

        if not self.hyperedges:
            return []

        # 提取关键词 (Bigram 拆词法)
        common_stop_words = {"的", "和", "是", "在", "项目", "我们", "平台", "系统", "服务", "产品", "未提", "提及"}
        bigrams = {query_str[i:i+2] for i in range(len(query_str)-1)}
        keywords = {bg for bg in bigrams if not any(sw in bg for sw in common_stop_words)}
        
        scored_hedges = []
        for hedge in self.hyperedges:
            score = 0
            desc = hedge.get("description", "")
            nodes_str = " ".join(hedge.get("nodes", []))
            combined_text = desc + " " + nodes_str
            
            for kw in keywords:
                if kw in combined_text:
                    score += 5
            
            # Filter/Boost attributes
            h_industry = hedge.get("industry")
            h_level = hedge.get("level")
            
            if industry and h_industry == industry:
                score += 15
            if level and h_level == level:
                score += 10
                    
            if score > 0:
                scored_hedges.append((hedge, score))
                
        scored_hedges.sort(key=lambda x: x[1], reverse=True)
        return [{"id": h[0].get("id", "关键逻辑"), "nodes": h[0].get("nodes", []), "desc": h[0].get("description", ""), "source": h[0].get("source_file", "")} for h in scored_hedges[:top_k]]
            
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