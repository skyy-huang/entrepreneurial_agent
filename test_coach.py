import asyncio
from dotenv import load_dotenv
from graph.graph_coach import GraphCoach

# 加载环境变量
load_dotenv()

async def main():
    coach = GraphCoach()
    
    # 模拟一份新项目
    new_project = """
    我们的项目是一个面向大学生的二手书交易平台。
    核心功能是允许学生上传旧书照片并标价，其他学生可以在线下单购买。
    我们打算通过收取每笔交易10%的手续费来盈利。
    缺乏核心技术壁垒。
    """
    
    print("正在基于提取出来的图谱知识库评估项目...\n")
    suggestion = await coach.generate_coaching_suggestions(new_project)
    print("================== 【智能教练建议】 ==================")
    print(suggestion)

if __name__ == "__main__":
    asyncio.run(main())