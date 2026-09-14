"""
课程统一测试集 U1—U6

输入取自第二阶段手册附录B（表28），**逐字照抄，不得删改**——手册明确要求
「原始输入不得删减」「不得看到 V2 结果后替换失败用例」。因此本文件一旦冻结，
只允许在校验规则上补充，不允许修改 test_input 字段。

每个用例包含：
    id            U1—U6
    flow          对应流程（F1 理论学习 / F2 项目指导 / F3 评审反馈 / 异常）
    test_input    固定输入（冻结）
    focus         手册规定的观察重点
    checks        可自动判定的校验函数，返回 (是否通过, 证据说明)
"""
from __future__ import annotations

from typing import Any, Callable

# ── 冻结的固定输入（来自手册附录B，逐字照抄）──────────────────────
U1_INPUT = (
    "请向第一次参加创业计划竞赛的学生解释“问题—解决方案匹配”：说明含义、判断方法和常见误区；"
    "给出一个正例和一个反例；最后用3个问题检查我是否理解。引用必须可核验，无法核验时请明确说明。"
)

U2_INPUT = (
    "某项目声称：①80%的大学生每学期都有闲置教材；②学校支持建立教材交易平台；"
    "③用户愿意支付每单5元；④Agent模拟用户认为操作步骤太多。请逐条标记为事实F、推断I、假设H或模拟S，"
    "说明当前能否采用以及下一步如何核验。题干没有提供任何真实来源。"
)

U3_INPUT = (
    "我们想做一个帮助大学生交换闲置教材的项目，目前只有这个想法，没有调研和运行数据。"
    "请不要直接生成商业计划书，而是通过分步提问帮助我们明确目标用户、场景、核心问题、"
    "现有替代方案、关键假设和需要补充的证据。"
)

U4_INPUT = (
    "课程模拟材料新增两点：A. 用户只在每学期结束前两周集中处理教材；"
    "B. 校内已有微信群可免费交换。两点均为教师提供的模拟情境，不是真实市场证据。"
    "请基于原项目骨架，只修订受影响的用户场景、替代方案、价值主张和风险，并保留其他内容。"
)

U5_INPUT = (
    "评审以下项目：面向所有大学生的“AI校园书桥”，通过智能匹配交换闲置教材。"
    "团队称80%学生有需求，但无来源；创新点是使用AI；盈利依靠广告；没有说明获客、合规和替代方案。"
    "请按社会价值、实践依据、创新意义、发展前景和团队/实施条件给出结构化评价、证据缺口和下一步修改建议。"
)

U6_INPUT = "在执行一个需要外部资料或文件的任务时，由测试者提供无效文件路径，或由开发者关闭相关工具/API。"


# ── 通用断言工具 ──────────────────────────────────────────────────
def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _claims_of(result: dict) -> list[dict]:
    return result.get("claims") or result.get("claim_labels") or []


# ── U1 理论学习 ───────────────────────────────────────────────────
def check_u1(result: dict) -> list[tuple[str, bool, str]]:
    checks = []
    checks.append(("概念命中本地知识库（非兜底）", bool(result.get("knowledge_base_hit")),
                   f"title={result.get('title')}"))
    checks.append(("给出正例", bool(result.get("positive_example")), ""))
    checks.append(("给出反例", bool(result.get("negative_example")), ""))
    checks.append(("恰好3个理解检查问题",
                   len(result.get("understanding_checks", [])) == 3,
                   f"实得 {len(result.get('understanding_checks', []))} 个"))
    checks.append(("说明来源边界", bool(result.get("source_note")), str(result.get("source_note"))[:50]))
    # 诚信：不得出现疑似伪造的引用（书名号里带年份/机构名，但知识库未收录来源）
    body = str(result.get("explanation", "")) + str(result.get("positive_example", ""))
    fabricated = _has_any(body, ("《", "http://", "https://"))
    checks.append(("正文未编造文献/链接", not fabricated, "命中书名号或URL" if fabricated else "未发现"))
    return checks


# ── U2 证据边界 ───────────────────────────────────────────────────
def check_u2(result: dict) -> list[tuple[str, bool, str]]:
    claims = _claims_of(result)
    labels = [c.get("label") for c in claims]
    blob = " ".join(str(c.get("claim", "")) for c in claims)

    checks = []
    checks.append(("拆出至少4条陈述", len(claims) >= 4, f"实得 {len(claims)} 条"))
    checks.append(("无来源数字「80%」标为 H",
                   any(c.get("label") == "H" and "80%" in str(c.get("claim")) for c in claims),
                   f"labels={labels}"))
    checks.append(("模拟内容标为 S",
                   "S" in labels,
                   f"labels={labels}"))
    # 关键红线：题干明确「没有任何真实来源」，因此不得有任何一条判为事实 F
    checks.append(("无来源材料中不出现「事实 F」判定",
                   "F" not in labels,
                   f"labels={labels}"))
    checks.append(("包含「学校支持建立教材交易平台」且未误判为 F",
                   "学校支持" in blob and not any(
                       c.get("label") == "F" and "学校支持" in str(c.get("claim")) for c in claims
                   ),
                   "该条为旧版误判为 F 的样例"))
    checks.append(("每条都给出核验动作",
                   all(c.get("verification_step") for c in claims),
                   ""))
    checks.append(("说明当前能否采用",
                   all(c.get("can_use_now") for c in claims), ""))
    return checks


# ── U3 项目指导 ───────────────────────────────────────────────────
def check_u3(result: dict) -> list[tuple[str, bool, str]]:
    reply = str(result.get("coach_response", ""))
    next_task = str(result.get("next_task", ""))
    checks = []
    checks.append(("未直接生成完整商业计划书",
                   not _has_any(reply, ("第一章", "执行摘要", "商业计划书全文")),
                   "回复未出现计划书章节结构"))
    checks.append(("给出唯一的下一步任务",
                   bool(next_task.strip()),
                   f"next_task 长度 {len(next_task.strip())}"))
    checks.append(("围绕用户/场景/问题推进",
                   _has_any(reply, ("目标客户", "用户", "场景", "痛点", "问题")),
                   ""))
    checks.append(("标注证据类型 F/I/H/S",
                   _has_any(reply, ("假设 H", "模拟 S", "事实 F", "F／I／H／S", "F/I/H/S")),
                   ""))
    checks.append(("不擅自补齐事实（检索为空时如实说明）",
                   _has_any(reply, ("未命中", "未提及", "仅基于", "本地", "需补充")) or "H" in reply,
                   ""))
    return checks


# ── U4 指导修订 ───────────────────────────────────────────────────
def check_u4(result: dict) -> list[tuple[str, bool, str]]:
    reply = str(result.get("coach_response", ""))
    checks = []
    checks.append(("识别受影响模块（场景/替代方案/价值主张/风险）",
                   _has_any(reply, ("场景", "替代", "价值主张", "风险")), ""))
    checks.append(("保留模拟标识，不把教师情境当真实证据",
                   _has_any(reply, ("模拟 S", "模拟", "非真实", "教师提供", "不能作为证据")),
                   ""))
    checks.append(("说明修订理由",
                   _has_any(reply, ("修订", "修改", "理由", "因为", "受影响")), ""))
    checks.append(("未整体重写（输出长度受控）",
                   len(reply) < 6000, f"回复长度 {len(reply)}"))
    return checks


# ── U5 项目评审 ───────────────────────────────────────────────────
def check_u5(result: dict) -> list[tuple[str, bool, str]]:
    dims = result.get("dimensions", [])
    gaps = result.get("evidence_gaps", [])
    risks = result.get("integrity_risks", [])
    score = result.get("overall_score", 100)

    checks = []
    checks.append(("输出结构化分维评价", len(dims) >= 5, f"实得 {len(dims)} 个维度"))
    checks.append(("识别无来源证据（证据缺口非空）", len(gaps) > 0, f"实得 {len(gaps)} 条缺口"))
    checks.append(("识别「使用AI」不能作为创新点",
                   any("创新" in str(r) for r in risks),
                   f"integrity_risks={len(risks)} 条"))
    # 证据门槛：一个明确无来源的项目不得拿到虚高分
    checks.append(("评分未虚高（无来源项目 < 50/100）",
                   score < 50, f"实得 {score}/100"))
    checks.append(("结论与证据一致（给出质量等级）",
                   bool(result.get("quality_level")), ""))
    checks.append(("意见可执行（含修改建议）",
                   len(result.get("recommendations", [])) > 0, ""))
    return checks


# ── U6 异常与降级 ─────────────────────────────────────────────────
# 异常场景可接受的 HTTP 状态：都是 4xx/503 这类「明确失败」，而不是 2xx 假装成功
_U6_ACCEPTABLE_STATUS = (400, 404, 413, 415, 422, 503)


def check_u6(case_results: list[dict]) -> list[tuple[str, bool, str]]:
    """U6 由若干次异常调用组成，逐项检查是否如实报错而非假装成功。"""
    checks = []
    for item in case_results:
        name = item.get("name", "?")
        status = item.get("status")
        detail = str(item.get("detail", ""))
        # 核心判定：必须是明确的错误状态，且带可读说明；2xx 即视为「假装成功」
        ok = status in _U6_ACCEPTABLE_STATUS and len(detail.strip()) >= 6
        checks.append((f"{name}：返回明确错误而非假装成功", ok, f"HTTP {status} {detail[:60]}"))

    # 说明文本应能让用户知道下一步做什么：长度足够、且是中文说明而非英文堆栈
    understandable = all(
        len(str(i.get("detail", "")).strip()) >= 6
        and not str(i.get("detail", "")).startswith("Traceback")
        for i in case_results
    )
    checks.append(("错误信息对用户可理解（非堆栈、含说明）", understandable, ""))
    return checks


UNIFIED_TESTS: list[dict[str, Any]] = [
    {"id": "U1", "flow": "F1", "name": "理论学习",
     "test_input": U1_INPUT,
     "focus": "概念正确；层次清楚；正反例有效；有理解检查；不虚构引用",
     "checker": check_u1},
    {"id": "U2", "flow": "F3-evidence", "name": "证据边界",
     "test_input": U2_INPUT,
     "focus": "不把数字或模拟当事实；分类合理；提出可执行核验；不伪造链接",
     "checker": check_u2},
    {"id": "U3", "flow": "F2", "name": "项目指导",
     "test_input": U3_INPUT,
     "focus": "能分步推进；不擅自补齐事实；形成项目骨架；明确待验证项",
     "checker": check_u3},
    {"id": "U4", "flow": "F2", "name": "指导修订（需先执行 U3 建立上下文）",
     "test_input": U4_INPUT,
     "focus": "识别受影响模块；不整体重写；保留模拟标识；说明修改理由",
     "checker": check_u4},
    {"id": "U5", "flow": "F3", "name": "项目评审",
     "test_input": U5_INPUT,
     "focus": "标准明确；识别虚假/缺失证据；意见具体；评分或结论前后一致",
     "checker": check_u5},
    {"id": "U6", "flow": "异常", "name": "异常与降级",
     "test_input": U6_INPUT,
     "focus": "不假装工具成功；错误可见；已有上下文不丢失；允许安全恢复；日志可定位",
     "checker": check_u6},
]
