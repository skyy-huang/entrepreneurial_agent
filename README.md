# 双创智能教练 (Entrepreneurial Agent)

**基于超图推理与知识图谱的学生-教师创新创业智能体系统**

---

## 项目架构

```
entrepreneurial_agent/
├── main.py                        # FastAPI 主程序入口
├── requirements.txt               # 依赖包
├── storage.py                     # 文件持久化存储
├── .env.example                   # 环境变量模板
│
├── hypergraph/                    # 超图核心引擎
│   ├── schema.py                  # 节点/超边数据结构 (Pydantic)
│   ├── rules.py                   # H1-H15 逻辑审计规则库
│   └── extractor.py               # 商业要素提取器 (LLM)
│
├── graph/                         # LangGraph 多 Agent 编排
│   ├── state.py                   # AgentState TypedDict
│   ├── nodes.py                   # extractor / critic / coach 三节点
│   └── workflow.py                # LangGraph 工作流
│
├── prompts/
│   └── coach_prompt.py            # Coach 系统提示词（苏格拉底提问法）
│
├── teacher/
│   └── dashboard.py               # 教师端数据聚合与教学建议
│
└── frontend/
    ├── index.html                 # 学生端 UI
    ├── teacher.html               # 教师端看板 UI
    └── static/
        ├── css/style.css
        └── js/student.js / teacher.js
```

## 快速启动

1. **配置 API Key**
   ```bash
   cp .env.example .env
   # 编辑 .env，填写 DEEPSEEK_API_KEY
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **启动服务**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

4. **访问**
   - 学生端：http://localhost:8000
   - 教师看板：http://localhost:8000/teacher

---

## 系统核心逻辑

### 超图逻辑引擎
将学生的自然语言输入提取为结构化节点（Concept/Method/Artifact/Metric）和超边（商业模式一致性/客户市场匹配/单位经济/资源能力匹配），通过 H1-H15 规则进行跨节点联合审计。

### H1-H15 逻辑规则库
| 规则 | 名称 | 严重度 |
|------|------|--------|
| H1 | 客户-渠道错位 | 高 |
| H2 | 竞争壁垒虚假 | 高 |
| H3 | 市场规模虚高 | 中 |
| H4 | 收入模型单一 | 中 |
| H5 | 技术可行性未验证 | 高 |
| H6 | 团队关键能力缺口 | 高 |
| H7 | 政策法规风险忽视 | 高 |
| H8 | 单位经济不成立 | 高 |
| H9 | 规模化路径不清 | 中 |
| H10 | 付费意愿假设偏高 | 高 |
| H11 | 渠道与定价矛盾 | 中 |
| H12 | 竞品分析缺失 | 中 |
| H13 | 核心假设未验证 | 高 |
| H14 | 现金流断裂风险 | 高 |
| H15 | 持续性路径缺失 | 中 |

### 三阶段对话流程
1. **价值探测**：验证"谁有痛点、痛点多痛、为什么你能解决"
2. **压力测试**：逐笔核算成本与收入，验证单位经济
3. **落地校验**：确认团队能力与执行路径

### LangGraph 工作流
```
学生输入
    ↓
extractor_node  —— 提取商业要素，构建超图
    ↓
critic_node     —— H1-H15 规则审计，更新能力得分
    ↓
coach_node      —— 苏格拉底提问 + 分配行动任务
    ↓
教练回复
```

### 教师端功能
- **班级共性错误排行榜**：H1-H15 触发频率统计
- **学习增值指数**：基于五维能力得分动态追踪
- **AI 教学干预建议**：根据触发率自动生成下周教学重点