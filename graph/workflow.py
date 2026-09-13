"""
LangGraph 工作流编排
extractor_node → critic_node → coach_node → END
"""
from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import extractor_node, critic_node, coach_node


def create_workflow():
    workflow = StateGraph(AgentState)

    workflow.add_node("extractor", extractor_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("coach", coach_node)

    workflow.set_entry_point("extractor")
    workflow.add_edge("extractor", "critic")
    workflow.add_edge("critic", "coach")
    workflow.add_edge("coach", END)

    return workflow.compile()


# 全局编译后的图实例（在 main.py 中导入使用）
app_graph = create_workflow()
