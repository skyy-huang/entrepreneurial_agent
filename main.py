"""
双创智能教练 - FastAPI 主程序 V2
启动命令：uvicorn main:app --reload --port 8121
新增：RBAC权限隔离 / Admin接口 / 竞赛评分路由 / 教师干预接口 / 日志观测
"""
import json
import os
import secrets
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("entrepreneurial_agent")

from graph.state import make_initial_state
from graph.workflow import app_graph
from teacher.dashboard import aggregate_class_data, generate_student_capability_report, generate_grading_report
from storage import load_sessions, save_sessions, load_users, save_users
from observability import (
    start_run, add_step, finish_run, mark_degraded, record_intervention, iter_runs,
    INTERVENTION_KINDS,
)
from version import get_version_info, AGENT_VERSION
from workflows import theory_response, review_response, classify_claims
from graph.document_agent import parse_and_summarize_document

app = FastAPI(title="双创智能教练 V2", version=AGENT_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 启动时加载已有会话和用户
sessions_store: dict = load_sessions()
users_store: dict = load_users()

# ─────────────────────────────────────────────────────────────
# RBAC 账号配置
#
# 凭据一律从环境变量读取，不写死在代码里。原实现把教师和管理员口令明文
# 硬编码在源码中（含一个管理员默认口令），直接违反手册自检项
# 「代码、配置和日志中不存在API密钥或不必要个人信息」。
#
# 配置方式（.env）：
#   TEACHER_ACCOUNTS={"teacher1":"你的口令","teacher2":"另一个口令"}
#   ADMIN_ACCOUNTS={"admin":"你的管理员口令"}
# 未配置时自动生成一次性随机口令，并在启动日志中以 WARNING 提示一次。
# ─────────────────────────────────────────────────────────────
def _load_accounts(env_var: str, role: str) -> dict:
    raw = os.getenv(env_var, "").strip()
    accounts: dict = {}
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for username, password in parsed.items():
                    accounts[str(username)] = {"password": str(password), "role": role}
        except json.JSONDecodeError:
            logger.error(
                "%s 不是合法 JSON，已忽略本变量。格式示例：{\"账号\":\"口令\"}", env_var
            )
    if not accounts:
        username = "teacher" if role == "teacher" else "admin"
        generated = secrets.token_urlsafe(9)
        accounts = {username: {"password": generated, "role": role}}
        logger.warning(
            "[AUTH] 未配置 %s，已为账号 '%s' 生成一次性随机口令：%s  "
            "（请在 .env 中配置 %s 以获得固定口令）",
            env_var, username, generated, env_var,
        )
    return accounts


TEACHERS = _load_accounts("TEACHER_ACCOUNTS", "teacher")
ADMINS = _load_accounts("ADMIN_ACCOUNTS", "admin")

ALL_USERS = {**TEACHERS, **ADMINS}


def verify_token(authorization: Optional[str], required_role: str = "teacher") -> dict:
    """验证 token 并检查角色权限"""
    if not authorization or not authorization.startswith("token-"):
        raise HTTPException(status_code=401, detail="未授权，请先登录")
    username = authorization.replace("token-", "")
    user = ALL_USERS.get(username)
    if not user:
        raise HTTPException(status_code=401, detail="无效凭证")
    role = user.get("role", "student")
    if required_role == "admin" and role != "admin":
        raise HTTPException(status_code=403, detail="权限不足，需要管理员权限")
    if required_role == "teacher" and role not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="权限不足，需要教师或管理员权限")
    logger.info("[AUTH] user=%s role=%s accessed required_role=%s", username, role, required_role)
    return {"username": username, "role": role}


# ─────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────
class StartSessionRequest(BaseModel):
    student_id: str
    password: str
    project_name: Optional[str] = ""

class StudentLoginRequest(BaseModel):
    student_id: str
    password: str

class ChatRequest(BaseModel):
    session_id: str
    message: str
    agent_mode: Optional[str] = "coach"


class TheoryRequest(BaseModel):
    question: str
    test_id: Optional[str] = "manual"


class ReviewRequest(BaseModel):
    project_text: str
    rubric: Optional[str] = "创业项目基础评审"
    test_id: Optional[str] = "manual"


class EvidenceRequest(BaseModel):
    text: str


class StudentDeleteRequest(BaseModel):
    student_id: str
    password: str


class TeacherLoginRequest(BaseModel):
    username: str
    password: str


class InterventionRequest(BaseModel):
    session_id: str
    intervention_text: str


class AdminUserActionRequest(BaseModel):
    target_username: str
    action: str  # "add" / "remove" / "change_role"
    new_role: Optional[str] = "student"
    new_password: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# API 路由（教师/学生相关接口）
# ─────────────────────────────────────────────────────────────
@app.post("/api/student/login")
async def student_login(req: StudentLoginRequest):
    """学生登录并获取历史会话"""
    student_id = req.student_id.strip()
    if not student_id:
        raise HTTPException(status_code=400, detail="学生ID不能为空")
    if not req.password:
        raise HTTPException(status_code=400, detail="密码不能为空")

    if student_id in users_store:
        if users_store[student_id] != req.password:
            raise HTTPException(status_code=401, detail="密码错误，请重试或更换学号")
    else:
        users_store[student_id] = req.password
        save_users(users_store)
        
    history = []
    for sid, state in sessions_store.items():
        if state.get("student_id") == student_id and state.get("round_count", 0) > 0:
            history.append({
                "session_id": sid,
                "current_phase": state.get("current_phase", "value_probe"),
                "round_count": state.get("round_count", 0),
                "messages": len(state.get("messages", []))
            })
            
    history.reverse()
    return {"student_id": student_id, "history": history}

@app.post("/api/teacher/login")
async def teacher_login(req: TeacherLoginRequest):
    """教师及管理员登录"""
    user = ALL_USERS.get(req.username)
    if user and user["password"] == req.password:
        return {"token": f"token-{req.username}", "username": req.username, "role": user["role"]}
    raise HTTPException(status_code=401, detail="用户名或密码错误")


@app.post("/api/session/start")
async def start_session(req: StartSessionRequest):
    """创建新的对话会话"""
    student_id = req.student_id.strip()
    if not student_id:
        raise HTTPException(status_code=400, detail="学生ID不能为空")
    if len(student_id) > 50:
        raise HTTPException(status_code=400, detail="学生ID过长")
    if not req.password:
        raise HTTPException(status_code=400, detail="密码不能为空")

    # 注册或校验密码
    if student_id in users_store:
        if users_store[student_id] != req.password:
            raise HTTPException(status_code=401, detail="密码错误，请重试或更换学号")
    else:
        users_store[student_id] = req.password
        save_users(users_store)

    session_id = str(uuid.uuid4())[:8]
    state = make_initial_state(session_id, student_id)
    sessions_store[session_id] = state
    save_sessions(sessions_store)

    return {
        "session_id": session_id,
        "welcome_message": (
            "# 从项目事实开始\n\n"
            "请先告诉我三件事：**谁**遇到了什么问题、他们现在如何解决、你准备改变什么结果。\n\n"
            "> 没有调研数据也没关系，请把不确定的内容标成假设，我们会逐项验证。"
        ),
        "current_phase": "value_probe",
        "round_count": 0,
        "capability_scores": state["capability_scores"],
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """处理学生输入，经过 extractor→critic→coach 三节点流水线"""
    if req.session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="会话不存在，请重新开始")

    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")
    if len(message) > 3000:
        raise HTTPException(status_code=400, detail="消息过长，请控制在3000字以内")

    existing = sessions_store[req.session_id]
    run = start_run("F2", "manual", project_version=existing.get("project_version", ""))
    run["session_id"] = req.session_id
    add_step(run, "input_validation", "success", f"message_length={len(message)}")
    state = dict(existing)
    state["current_input"] = message
    state["agent_mode"] = req.agent_mode

    try:
        result = await app_graph.ainvoke(state)
        add_step(run, "agent_workflow", "success", "extractor->critic->coach")
    except Exception as exc:
        add_step(run, "agent_workflow", "failed", type(exc).__name__)
        finish_run(run, "failed", type(exc).__name__, str(exc))
        raise HTTPException(status_code=503, detail="项目指导暂时不可用，已有上下文已保留，请稍后安全重试") from exc

    # 如实记录降级：LLM 不可用时流程仍然完成了任务，但审计者必须能看出差别
    degraded_reason = result.get("degraded_reason")
    if degraded_reason:
        mark_degraded(run, degraded_reason)

    sessions_store[req.session_id] = result
    save_sessions(sessions_store)
    finish_run(run, "success")

    return {
        "session_id": req.session_id,
        "coach_response": result["coach_response"],
        "next_task": result["next_task"],
        "thought_process": result.get("thought_process", ""),
        "detected_fallacies": result["detected_fallacies"],
        "capability_scores": result["capability_scores"],
        "current_phase": result["current_phase"],
        "round_count": result["round_count"],
        "hypergraph_summary": result["hypergraph_summary"],
        "probing_strategy": result.get("probing_strategy", ""),
        "retrieved_hyperedge_types": result.get("retrieved_hyperedge_types", []),
        "rule_engine_result": result.get("rule_engine_result", {}),
        "kb_context": result.get("kb_context", {}),
        "degraded": bool(degraded_reason),
        "degraded_reason": degraded_reason or "",
        "run_id": run["run_id"],
    }


@app.post("/api/learn")
async def learn(req: TheoryRequest):
    """F1 理论学习：解释、正反例、理解检查和来源边界。"""
    run = start_run("F1", req.test_id or "manual")
    if not req.question.strip():
        add_step(run, "input_validation", "failed", "question_missing")
        finish_run(run, "failed", "input_missing")
        raise HTTPException(status_code=400, detail="请先输入一个学习问题")
    add_step(run, "input_validation", "success", f"question_length={len(req.question.strip())}")
    try:
        result = theory_response(req.question)
        add_step(run, "theory_response", "success", "deterministic_local_workflow")
        finish_run(run, "success")
        result["run_id"] = run["run_id"]
        return result
    except ValueError as exc:
        finish_run(run, "failed", "input_missing")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/upload")
async def upload_document(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    message: Optional[str] = Form(None),
):
    """F2 文件输入：先提取文本，再交给项目指导流程审计。"""
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="会话不存在，请重新开始")
    if not file.filename:
        raise HTTPException(status_code=400, detail="请选择文件")
    allowed = {"pdf", "docx", "doc", "txt"}
    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in allowed:
        raise HTTPException(status_code=400, detail="仅支持 PDF、DOCX、DOC 或 TXT 文件")
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 10MB")
    summary = await parse_and_summarize_document(file_bytes, file.filename)
    if not summary:
        raise HTTPException(status_code=422, detail="无法提取文件文本，请检查文件是否为空或为扫描图片")

    run = start_run("F2", "file-upload")
    run["session_id"] = session_id
    add_step(run, "file_parse", "success", f"extension={extension}, bytes={len(file_bytes)}")
    state = dict(sessions_store[session_id])
    note = message.strip() if message else "请审计这份项目材料，指出最关键的证据缺口。"
    state["current_input"] = (
        f"学生上传文件：{file.filename}\n"
        f"补充说明：{note}\n\n"
        "以下是系统提取的文本或结构化摘要，请不要把其中未标注的数字自动视为事实：\n"
        f"{summary[:15000]}"
    )
    state["agent_mode"] = "coach"
    try:
        result = await app_graph.ainvoke(state)
        add_step(run, "agent_workflow", "success", "file->extractor->critic->coach")
    except Exception as exc:
        add_step(run, "agent_workflow", "failed", type(exc).__name__)
        finish_run(run, "failed", type(exc).__name__, str(exc))
        raise HTTPException(status_code=503, detail="文件已读取，但项目指导暂时不可用，请稍后重试") from exc
    sessions_store[session_id] = result
    save_sessions(sessions_store)
    degraded_reason = result.get("degraded_reason")
    if degraded_reason:
        mark_degraded(run, degraded_reason)
    finish_run(run, "success")
    return {
        "session_id": session_id,
        "filename": file.filename,
        "coach_response": result["coach_response"],
        "next_task": result["next_task"],
        "detected_fallacies": result["detected_fallacies"],
        "capability_scores": result["capability_scores"],
        "current_phase": result["current_phase"],
        "round_count": result["round_count"],
        "degraded": bool(degraded_reason),
        "degraded_reason": degraded_reason or "",
        "run_id": run["run_id"],
    }


@app.post("/api/review")
async def review(req: ReviewRequest):
    """F3 评审反馈：量规、证据缺口、边界分类和可执行修改。"""
    run = start_run("F3", req.test_id or "manual")
    if len(req.project_text.strip()) < 20:
        add_step(run, "input_validation", "failed", "project_text_too_short")
        finish_run(run, "failed", "input_missing")
        raise HTTPException(status_code=400, detail="评审至少需要20个字符的项目材料")
    add_step(run, "input_validation", "success", f"project_length={len(req.project_text.strip())}")
    try:
        result = review_response(req.project_text, req.rubric or "创业项目基础评审")
        add_step(run, "rubric_review", "success", f"dimensions={len(result['dimensions'])}")
        finish_run(run, "success")
        result["run_id"] = run["run_id"]
        return result
    except ValueError as exc:
        finish_run(run, "failed", "input_missing")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/evidence/classify")
async def classify_evidence(req: EvidenceRequest):
    """将项目材料拆成 F/I/H/S，并明确哪些内容仍需核验。"""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="请输入需要标注的材料")
    run = start_run("evidence", "manual")
    add_step(run, "claim_classification", "success", f"text_length={len(req.text.strip())}")
    finish_run(run, "success")
    return {"claims": classify_claims(req.text), "run_id": run["run_id"], "note": "自动分类仅作初筛，最终标注由项目成员负责。"}


class ScoreRequest(BaseModel):
    session_id: str
    project_text: str
    competition: Optional[str] = None


@app.post("/api/score")
async def score_project(req: ScoreRequest):
    """R1–R9 逐项评分：证据引擎底分 + LLM 可选加分。

    该节点独立于 F2 的线性工作流，避免每轮对话都跑一遍九维评分。
    未配置或不可用 LLM 时只输出证据引擎算出的底分（delta=0）。
    """
    if req.session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="会话不存在，请重新开始")
    if len(req.project_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="评分至少需要20个字符的项目材料")

    run = start_run("score", "manual")
    run["session_id"] = req.session_id
    state = dict(sessions_store[req.session_id])
    state["current_input"] = req.project_text.strip()
    if req.competition:
        state["competition_mode"] = req.competition
    add_step(run, "input_validation", "success", f"project_length={len(req.project_text.strip())}")

    from graph.nodes import rubric_scoring_node

    try:
        result = await rubric_scoring_node(state)
        add_step(run, "rubric_scoring", "success", f"items={len(result.get('rubric_scores', {}))}")
    except Exception as exc:
        add_step(run, "rubric_scoring", "failed", type(exc).__name__)
        finish_run(run, "failed", type(exc).__name__, str(exc))
        raise HTTPException(status_code=503, detail="评分暂时不可用，请稍后重试") from exc

    if not _llm_available_for_run():
        mark_degraded(run, "LLM 不可用，仅输出证据引擎底分（score_delta=0）")

    sessions_store[req.session_id]["rubric_scores"] = result.get("rubric_scores", {})
    sessions_store[req.session_id]["score_breakdown"] = result.get("score_breakdown", {})
    save_sessions(sessions_store)
    finish_run(run, "success")

    return {
        "session_id": req.session_id,
        "rubric_scores": result.get("rubric_scores", {}),
        "score_breakdown": result.get("score_breakdown", {}),
        "coach_response": result.get("coach_response", ""),
        "run_id": run["run_id"],
    }


def _llm_available_for_run() -> bool:
    """判断当前是否配置了可用的 API Key（不代表余额可用）。"""
    from version import llm_configured

    return llm_configured()


class InterventionRecordRequest(BaseModel):
    session_id: str
    kind: str                      # 补充 / 修改 / 确认 / 绕过 / 重跑 / 纠错
    detail: str = ""
    run_id: Optional[str] = None   # 关联到具体一次运行，便于回溯


@app.post("/api/intervention")
async def record_human_intervention(req: InterventionRecordRequest):
    """记录人工干预。

    手册明确要求：改写 Agent 输出、手工补齐遗漏模块、替换错误引用、
    修改测试输入、重跑失败任务都必须记录，且不得把人工成果计为 Agent 能力。
    这是「人机边界透明」原则的落地点。
    """
    if req.session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="会话不存在，请重新开始")
    if req.kind not in INTERVENTION_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"干预类型必须是以下之一：{'、'.join(INTERVENTION_KINDS)}",
        )
    state = sessions_store[req.session_id]
    log = state.setdefault("human_interventions", [])
    entry = {
        "kind": req.kind,
        "detail": (req.detail or "").strip()[:500],
        "run_id": req.run_id or "",
        "at": datetime.now(timezone.utc).isoformat(),
    }
    log.append(entry)
    sessions_store[req.session_id] = state
    save_sessions(sessions_store)
    logger.info(
        "[INTERVENTION] session=%s kind=%s run=%s detail=%s",
        req.session_id, req.kind, req.run_id or "-", entry["detail"][:80],
    )
    return {"message": "人工干预已记录", "session_id": req.session_id, "entry": entry,
            "total": len(log)}


@app.get("/api/version")
async def api_version():
    """版本快照。

    手册第三阶段要求保存「Agent V2 代码提交号或不可变版本标签」以及
    「提示词、知识库、工具和关键配置快照」，并且最终结论要能回到材料版本、
    运行编号和证据来源。此接口为版本快照提供单一可信来源。
    """
    return get_version_info()


@app.get("/api/runs")
async def list_runs(flow: Optional[str] = None, limit: int = 50):
    """列出最近的运行记录摘要，供测试报告与异常审计使用。"""
    limit = max(1, min(limit, 500))
    items = []
    for record in iter_runs(limit=limit if not flow else None):
        if flow and record.get("flow") != flow:
            continue
        items.append({
            "run_id": record.get("run_id"),
            "flow": record.get("flow"),
            "test_id": record.get("test_id"),
            "status": record.get("status"),
            "degraded": record.get("degraded", False),
            "started_at": record.get("started_at"),
            "duration_ms": record.get("duration_ms"),
            "agent_version": record.get("agent_version"),
            "git_commit": record.get("git_commit"),
            "human_interventions": len(record.get("human_interventions", [])),
        })
    return {"count": len(items), "items": items[-limit:]}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """按 run_id 定位脱敏运行记录。"""
    for record in iter_runs():
        if record.get("run_id") == run_id:
            return record
    raise HTTPException(status_code=404, detail="运行记录不存在")


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """获取指定会话的完整状态"""
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="会话不存在")
    state = sessions_store[session_id]
    return {
        "session_id": session_id,
        "student_id": state["student_id"],
        "messages": state["messages"],
        "capability_scores": state["capability_scores"],
        "rubric_scores": state.get("rubric_scores", {}),
        "score_breakdown": state.get("score_breakdown", {}),
        "rule_engine_result": state.get("rule_engine_result", {}),
        "current_phase": state["current_phase"],
        "round_count": state["round_count"],
        "detected_fallacies": state["detected_fallacies"],
        "hypergraph_summary": state["hypergraph_summary"],
        "probing_strategy": state.get("probing_strategy", ""),
        "kb_context": state.get("kb_context", {}),
    }


@app.delete("/api/student/session/{session_id}")
async def delete_student_session(session_id: str, req: StudentDeleteRequest):
    """学生只能删除属于自己的项目。"""
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="项目不存在")
    student_id = req.student_id.strip()
    if not student_id or users_store.get(student_id) != req.password:
        raise HTTPException(status_code=401, detail="身份验证失败")
    if sessions_store[session_id].get("student_id") != student_id:
        raise HTTPException(status_code=403, detail="不能删除其他人的项目")
    del sessions_store[session_id]
    save_sessions(sessions_store)
    return {"message": "项目已删除", "session_id": session_id}


# ─────────────────────────────────────────────────────────────
# 教师端接口（需要 teacher 或 admin 权限）
# ─────────────────────────────────────────────────────────────
@app.get("/api/teacher/dashboard")
async def get_teacher_dashboard(authorization: Optional[str] = Header(None)):
    """获取教师端班级看板聚合数据"""
    verify_token(authorization, required_role="teacher")
    all_sessions = list(sessions_store.values())
    data = aggregate_class_data(all_sessions)
    return data


@app.get("/api/teacher/student/{session_id}/report")
async def get_student_report(session_id: str, authorization: Optional[str] = Header(None)):
    """获取单个学生的能力评估报告（A6-4）"""
    verify_token(authorization, required_role="teacher")
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="会话不存在")
    state = sessions_store[session_id]
    report = generate_student_capability_report(state)
    return report


@app.get("/api/teacher/student/{session_id}/grading_report")
async def get_grading_report(session_id: str, authorization: Optional[str] = Header(None)):
    """获取单个学生的批改评价智能体报告"""
    verify_token(authorization, required_role="teacher")
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="会话不存在")
    state = sessions_store[session_id]
    report = generate_grading_report(state)
    return report

@app.post("/api/teacher/intervene")
async def teacher_intervene(req: InterventionRequest, authorization: Optional[str] = Header(None)):
    """教师干预接口（A6-3）：注入干预策略到学生会话"""
    verify_token(authorization, required_role="teacher")
    if req.session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="会话不存在")
    sessions_store[req.session_id]["teacher_intervention"] = req.intervention_text
    save_sessions(sessions_store)
    logger.info("[INTERVENTION] session=%s intervention_set=%s", req.session_id, req.intervention_text[:50])
    return {"message": "干预策略已注入，下次学生对话时将自动生效", "session_id": req.session_id}


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str, authorization: Optional[str] = Header(None)):
    """删除指定会话（教师权限）"""
    verify_token(authorization, required_role="teacher")
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="会话不存在")
    del sessions_store[session_id]
    save_sessions(sessions_store)
    return {"message": "会话已删除"}


class ScoreReviewRequest(BaseModel):
    session_id: str
    rubric_id: str          # e.g. "R1"
    revised_score: int      # 0-5
    review_reason: str


@app.post("/api/teacher/review-score")
async def teacher_review_score(req: ScoreReviewRequest, authorization: Optional[str] = Header(None)):
    """Teacher reviews/overrides a rubric score (Direction 5: accountability)."""
    user = verify_token(authorization, required_role="teacher")
    if req.session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="Session not found")
    if req.revised_score < 0 or req.revised_score > 5:
        raise HTTPException(status_code=400, detail="Score must be 0-5")

    state = sessions_store[req.session_id]
    rubric_scores = state.get("rubric_scores", {})
    breakdown = state.get("score_breakdown", {})

    old_score = rubric_scores.get(req.rubric_id, {}).get("score", "N/A")

    # Update rubric_scores
    if req.rubric_id not in rubric_scores:
        rubric_scores[req.rubric_id] = {}
    rubric_scores[req.rubric_id]["score"] = req.revised_score
    rubric_scores[req.rubric_id]["teacher_reviewed"] = True
    rubric_scores[req.rubric_id]["teacher_reason"] = req.review_reason
    rubric_scores[req.rubric_id]["reviewed_by"] = user["username"]

    # Update breakdown if exists
    if req.rubric_id in breakdown:
        breakdown[req.rubric_id]["final_score"] = req.revised_score
        breakdown[req.rubric_id]["teacher_override"] = True
        breakdown[req.rubric_id]["teacher_reason"] = req.review_reason

    sessions_store[req.session_id]["rubric_scores"] = rubric_scores
    sessions_store[req.session_id]["score_breakdown"] = breakdown
    save_sessions(sessions_store)

    logger.info(
        "[SCORE_REVIEW] teacher=%s session=%s rubric=%s old=%s new=%d reason=%s",
        user["username"], req.session_id, req.rubric_id,
        old_score, req.revised_score, req.review_reason[:60],
    )
    return {
        "message": f"{req.rubric_id} score updated: {old_score} -> {req.revised_score}",
        "session_id": req.session_id,
        "rubric_id": req.rubric_id,
        "revised_score": req.revised_score,
    }


# ─────────────────────────────────────────────────────────────
# 管理员接口（Admin Only）
# ─────────────────────────────────────────────────────────────
@app.get("/api/admin/global-dashboard")
async def admin_global_dashboard(authorization: Optional[str] = Header(None)):
    """管理员全局大盘（A6-5）"""
    verify_token(authorization, required_role="admin")
    all_sessions = list(sessions_store.values())
    class_data = aggregate_class_data(all_sessions)

    from collections import Counter
    rule_freq: Counter = Counter()
    for s in all_sessions:
        for f in s.get("detected_fallacies", []):
            rid = f.get("rule_id", "")
            if rid:
                rule_freq[rid] += 1

    top3_bugs = [
        {"rule_id": rid, "count": cnt, "name": __import__("hypergraph.rules", fromlist=["RULES"]).RULES.get(rid, {}).get("name", rid)}
        for rid, cnt in rule_freq.most_common(3)
    ]

    return {
        "total_projects": len(all_sessions),
        "total_valid_sessions": sum(1 for s in all_sessions if s.get("round_count", 0) > 0),
        "average_rubric_score": class_data.get("avg_capability_scores", {}),
        "rule_trigger_frequency": dict(rule_freq),
        "top3_business_bugs": top3_bugs,
        "high_risk_count": class_data.get("high_risk_count", 0),
        "teaching_suggestions": class_data.get("teaching_suggestions", []),
    }


@app.get("/api/admin/users")
async def admin_list_users(authorization: Optional[str] = Header(None)):
    """管理员：列出所有用户（A6-5）"""
    verify_token(authorization, required_role="admin")
    return {
        "teachers": list(TEACHERS.keys()),
        "admins": list(ADMINS.keys()),
    }


@app.post("/api/admin/users/action")
async def admin_user_action(req: AdminUserActionRequest, authorization: Optional[str] = Header(None)):
    """管理员：修改用户角色"""
    verify_token(authorization, required_role="admin")
    if req.action == "change_role":
        if req.target_username in ALL_USERS:
            ALL_USERS[req.target_username]["role"] = req.new_role
            logger.info("[ADMIN] Changed role of %s to %s", req.target_username, req.new_role)
            return {"message": f"{req.target_username} 角色已修改为 {req.new_role}"}
        raise HTTPException(status_code=404, detail="用户不存在")
    raise HTTPException(status_code=400, detail="不支持的操作")


# ─────────────────────────────────────────────────────────────
# 页面路由
# ─────────────────────────────────────────────────────────────
@app.get("/")
async def serve_student():
    return FileResponse("frontend/index.html")


@app.get("/teacher")
async def serve_teacher():
    return FileResponse("frontend/teacher.html")


@app.get("/admin")
async def serve_admin():
    """管理员控制台页面。

    原实现会在 admin.html 缺失时静默回退到教师页面，这会让访问 /admin 的人
    误以为存在管理员控制台、实际看到的却是教师视图。这里改为如实说明：
    管理接口可用，但独立控制台页面尚未实现。
    """
    admin_path = "frontend/admin.html"
    if os.path.exists(admin_path):
        return FileResponse(admin_path)
    return JSONResponse(
        status_code=501,
        content={
            "detail": "管理员控制台页面（frontend/admin.html）尚未实现。",
            "available_api": [
                "/api/admin/global-dashboard",
                "/api/admin/users",
                "/api/admin/users/action",
            ],
            "teacher_console": "/teacher",
        },
    )


# 静态资源
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
# 如果 static 已被重命名为 assets
if os.path.exists("frontend/assets"):
    app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")


# ─────────────────────────────────────────────────────────────
# 启动入口
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8121, reload=True)
