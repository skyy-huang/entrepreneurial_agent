# 双创智能教练（Entrepreneurial Agent）

**面向创新创业课程的智能教练 Agent V2**

三个可独立运行的工作流：**理论学习 F1** / **项目指导 F2** / **评审反馈 F3**。
核心设计目标是**证据诚信**——系统不会把没有来源的陈述当成事实，也不会编造引用。

> 配套交付物见 `deliverables/`：项目开发文档、迭代开发文档、创新性说明、
> 自测试报告、用户手册、验收 PPT。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env      # 编辑 .env，至少填写账号配置

# 3. 启动
uvicorn main:app --reload --port 8000
```

- 学生端：http://localhost:8000
- 教师看板：http://localhost:8000/teacher

> **没有配置 API Key 也能完整运行。** F1/F3 使用本地确定性引擎，不依赖大模型；
> F2 会降级为规则引擎模式，并在响应与日志中**如实标注** `degraded: true`。

---

## 项目结构

```
entrepreneurial_agent/
├── main.py                  FastAPI 入口，全部 HTTP 接口
├── workflows.py             F1 理论学习 / F3 评审反馈（确定性引擎）
├── evidence.py              证据边界引擎：F/I/H/S 分类、否定感知、来源识别
├── knowledge.py             F1 概念知识库（13 个词条）
├── observability.py         运行日志：七类字段、脱敏、降级状态、人工干预
├── version.py               版本快照（/api/version 与日志共同使用）
├── storage.py               会话与用户的文件持久化
├── requirements.txt
├── .env.example
│
├── graph/                   LangGraph 编排
│   ├── state.py             AgentState 定义
│   ├── nodes.py             extractor → critic → coach 三节点 + rubric 评分节点
│   ├── workflow.py          工作流装配
│   ├── graph_coach.py       知识图谱检索
│   └── document_agent.py    PDF/DOCX/TXT 文本提取
│
├── hypergraph/              超图规则引擎
│   ├── schema.py            节点/超边数据结构
│   ├── rules.py             H1-H20 规则库、R1-R9 量规、追问策略库
│   ├── rule_engine.py       Phase1 确定性规则引擎
│   ├── score_engine.py      评分下限引擎
│   └── evidence_checker.py  证据覆盖度检查
│
├── prompts/coach_prompt.py  各角色系统提示词（含证据边界与反编造护栏）
├── teacher/dashboard.py     教师端班级数据聚合
├── frontend/                学生端 / 教师端页面
└── tests/                   统一测试集与组内回归测试
```

---

## 三个流程

| 流程 | 入口 | 说明 |
|------|------|------|
| **F1 理论学习** | `POST /api/learn` | 解释概念、判断方法、常见误区、正反例、3 个理解检查、来源边界声明 |
| **F2 项目指导** | `POST /api/chat` | 多轮苏格拉底式追问，逐轮推进用户/场景/问题/证据/方案/创新/风险 |
| **F3 评审反馈** | `POST /api/review` | 按五维度量规评审，输出得分、证据缺口、诚信风险与可执行建议 |

F1/F3 为**确定性引擎**：输出稳定、可复现，且在结构上不可能编造引用。
F2 为 LLM 主路径 + 规则引擎降级。

### 证据边界 F/I/H/S

| 类型 | 定义 | 能否作为结论依据 |
|------|------|------------------|
| **F 事实** | 有可定位来源（机构、标题、年份、链接） | 可以，需标注来源 |
| **I 推断** | 基于事实作出的解释 | 仅作待验证输入 |
| **H 假设** | 尚未验证的判断，**包括所有无来源数字** | 仅作待验证输入 |
| **S 模拟** | 课程、教师或 Agent 设定的情境 | 不得作为证据 |

分类器采用**保守口径**：没有明确来源标记的陈述一律不给 F；「没有调研」「无来源」
这类否定式不会被误判为存在证据。

---

## API 一览

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/student/login` | 学生登录 |
| POST | `/api/session/start` | 创建项目会话 |
| POST | `/api/chat` | F2 项目指导 |
| POST | `/api/upload` | F2 文件上传（PDF/DOCX/DOC/TXT，≤10MB） |
| POST | `/api/learn` | F1 理论学习 |
| POST | `/api/review` | F3 评审反馈 |
| POST | `/api/evidence/classify` | F/I/H/S 逐条标注 |
| POST | `/api/score` | R1–R9 逐项评分（证据引擎底分 + LLM 可选加分） |
| POST | `/api/intervention` | 记录人工干预（补充/修改/确认/绕过/重跑/纠错） |
| GET | `/api/version` | 版本快照（版本号、提示词版本、知识库版本、git 提交号） |
| GET | `/api/runs` | 最近运行记录摘要 |
| GET | `/api/runs/{run_id}` | 按 run_id 查询完整运行记录 |
| GET | `/api/session/{session_id}` | 会话状态 |
| GET | `/api/teacher/dashboard` | 教师看板（需 teacher 权限） |

交互式接口文档：http://localhost:8000/docs

---

## 账号配置

凭据只从环境变量读取，**不写进代码**：

```bash
TEACHER_ACCOUNTS={"teacher1":"你的口令"}
ADMIN_ACCOUNTS={"admin":"你的管理员口令"}
```

未配置时系统会生成一次性随机口令，并在启动日志中以 WARNING 级别打印一次。
`/api/admin/*` 接口可用，但管理员控制台页面尚未实现（访问 `/admin` 返回 501）。

---

## 运行日志与可观测性

每次流程运行产生一个 `run_id`，脱敏记录写入 `logs/runs.jsonl`。日志覆盖七类字段：

| 类别 | 字段 |
|------|------|
| 身份 | run_id、agent_version、flow、test_id、project_version |
| 时间 | started_at、finished_at、duration_ms |
| 状态 | started / success / **degraded** / failed |
| 行为 | steps[]（关键节点与工具调用结果） |
| 异常 | error_type、error_detail、retry_count |
| 人机边界 | human_interventions[]（补充、修改、绕过、重跑） |
| 保护 | API Key、手机号等自动脱敏，不记录敏感数据 |

> **降级会如实记录。** 大模型不可用时，运行状态记为 `degraded` 而不是 `success`，
> 并保存降级原因，使「失败运行没有被隐瞒」这条要求可以自证。

---

## 运行测试

```bash
# 启动服务后（另一个终端）
python tests/run_tests.py --label V2 --suite both --base http://127.0.0.1:8000
```

- `--suite unified` 只跑课程统一测试集 U1—U6
- `--suite custom` 只跑组内回归测试
- `--suite both` 全部（默认）

报告输出到 `tests/reports/`，包含 JSON（机器可读）与 Markdown（自测试报告）两份，
**通过项与失败项全部保留，不做筛选**。

生成《06_自测试报告》交付文档：

```bash
python deliverables/build/generate_selftest.py
```

---

## 重新生成交付物

```bash
python deliverables/build/generate_pptx.py     # 验收 PPT
python deliverables/build/build_all.py         # 文档 → DOCX → PDF
python deliverables/build/copy_source.py       # 源码快照
python deliverables/build/generate_personal.py --names "姓名1,姓名2,姓名3"
```

---

## 已知限制

1. **F2 依赖外部大模型**。未配置 API Key 或额度不足时降级为规则引擎，输出质量下降。
2. **F1/F3 无服务端会话归属**。这两个流程的对话记录不进入会话存储，教师端看不到使用情况（已列为延期项）。
3. **知识库覆盖有限**。F1 收录 13 个概念，未命中的概念只返回通用拆解路径，不编造定义。
4. **管理员控制台未实现**。`/api/admin/*` 可用，但无独立页面。
5. **`logs/runs.jsonl` 无自动轮转**。长期运行需手动归档。

---

## 免责声明

本系统用于创新创业课程教学辅助，不构成商业、法律、医疗或财务建议。
所有 AI 生成内容仅供参考，最终判断与资料核验由使用者负责。
