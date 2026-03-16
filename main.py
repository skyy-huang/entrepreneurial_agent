"""
双创智能教练 - FastAPI 主程序
启动命令；uvicorn main:app --reload --port 8000
"""
import os
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from graph.state import make_initial_state
from graph.workflow import app_graph
from teacher.dashboard import aggregate_class_data
from storage import load_sessions, save_sessions

app = FastAPI(title="双创智能教练", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 启动时加载已有会话
sessions_store: dict = load_sessions()

# ─────────────────────────────────────────────────────────────
# 教师账号配置 (可扩展为从数据库或文件读取)
# ─────────────────────────────────────────────────────────────
TEACHERS = {
    "teacher1": "123456",
    "teacher2": "888888",
    "wang": "password",
}

def verify_teacher_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("token-"):
        raise HTTPException(status_code=401, detail="未授权，请先登录")
    username = authorization.replace("token-", "")
    if username not in TEACHERS:
        raise HTTPException(status_code=401, detail="无效凭证")
    return username


# ─────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────
class StartSessionRequest(BaseModel):
    student_id: str
    project_name: Optional[str] = ""

class ChatRequest(BaseModel):
    session_id: str
    message: str

class TeacherLoginRequest(BaseModel):
    username: str
    password: str

# ─────────────────────────────────────────────────────────────
# API 路由（必须在 StaticFiles mount 之前定义）
# ─────────────────────────────────────────────────────────────
@app.post("/api/teacher/login")
async def teacher_login(req: TeacherLoginRequest):
    """教师端登录接口"""
    if TEACHERS.get(req.username) == req.password:
        return {"token": f"token-{req.username}", "username": req.username}
    raise HTTPException(status_code=401, detail="用户名或密码错误")

@app.post("/api/session/start")
async def start_session(req: StartSessionRequest):
    """创建新的对话会话，返回欢迎语和初始状态"""
    # 输入验证
    student_id = req.student_id.strip()
    if not student_id:
        raise HTTPException(status_code=400, detail="学生ID不能为空")
    if len(student_id) > 50:
        raise HTTPException(status_code=400, detail="学生ID过长")

    session_id = str(uuid.uuid4())[:8]
    state = make_initial_state(session_id, student_id)
    sessions_store[session_id] = state
    save_sessions(sessions_store)

    return {
        "session_id": session_id,
        "welcome_message": (
            "你好。我是你的双创智能教练。\n\n"
            "先说清楚规则：我不会帮你写商业计划书，我只会问你问题。"
            "如果你的逻辑有漏洞，我会把你堵在那里，直到你想清楚为止。\n\n"
            "好了，开始吧——**你想解决什么问题，为谁解决，你打算怎么做？**"
        ),
        "current_phase": "value_probe",
        "round_count": 0,
        "capability_scores": state["capability_scores"],
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """处理学生输入，经过 extractor→critic→coach 三节点流水线，返回教练回复"""
    if req.session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="会话不存在，请重新开始")

    # 输入验证
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")
    if len(message) > 2000:
        raise HTTPException(status_code=400, detail="消息过长，请控制在2000字以内")

    state = dict(sessions_store[req.session_id])
    state["current_input"] = message

    # 运行 LangGraph 工作流
    result = await app_graph.ainvoke(state)

    # 持久化
    sessions_store[req.session_id] = result
    save_sessions(sessions_store)

    return {
        "session_id": req.session_id,
        "coach_response": result["coach_response"],
        "next_task": result["next_task"],
        "detected_fallacies": result["detected_fallacies"],
        "capability_scores": result["capability_scores"],
        "current_phase": result["current_phase"],
        "round_count": result["round_count"],
        "hypergraph_summary": result["hypergraph_summary"],
    }


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """获取指定会话的完整状态（含对话历史）"""
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="会话不存在")
    state = sessions_store[session_id]
    return {
        "session_id": session_id,
        "student_id": state["student_id"],
        "messages": state["messages"],
        "capability_scores": state["capability_scores"],
        "current_phase": state["current_phase"],
        "round_count": state["round_count"],
        "detected_fallacies": state["detected_fallacies"],
        "hypergraph_summary": state["hypergraph_summary"],
    }


@app.get("/api/teacher/dashboard")
async def get_teacher_dashboard(authorization: Optional[str] = Header(None)):
    """获取教师端看板聚合数据"""
    verify_teacher_token(authorization)
    all_sessions = list(sessions_store.values())
    return aggregate_class_data(all_sessions)


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str, authorization: Optional[str] = Header(None)):
    """删除指定会话（用于重置）"""
    verify_teacher_token(authorization)
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="会话不存在")
    del sessions_store[session_id]
    save_sessions(sessions_store)
    return {"message": "会话已删除"}


# ─────────────────────────────────────────────────────────────
# 页面路由
# ─────────────────────────────────────────────────────────────

@app.get("/")
async def serve_student():
    return FileResponse("frontend/index.html")


@app.get("/teacher")
async def serve_teacher():
    return FileResponse("frontend/teacher.html")


# 静态资源（CSS、JS）
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


# ─────────────────────────────────────────────────────────────
# 启动入口
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
