"""
三个可独立验收的工作流：理论学习 F1、项目指导 F2、评审反馈 F3。

设计基线
--------
F1 / F3 以**确定性引擎**为主路径，LLM 为可选增强层。理由有三：

1. 手册对这两个流程的最低完整输出要求是「引用可核验或明确无来源」「区分事实与
   假设」。LLM 一旦被要求举例或给引用，很容易生成不存在的报告名和数字——那正
   是 G3 证据诚信门槛要拦的东西。确定性引擎从结构上不可能编造引用。
2. 手册要求 V1/V2 在**相同输入**下可比、可复现。确定性输出不会因为采样随机性
   而在两次运行间漂移，比较结论因此可信。
3. 未配置 API Key、余额不足或服务超时时，F1/F3 仍然完整可用，这本身就是手册
   要求的「异常降级」证据。

F2（项目指导）保持 LLM 主路径 + 规则引擎降级，因为多轮追问天然需要语言生成。
"""
from __future__ import annotations

import os
from typing import Any

from evidence import (
    EVIDENCE_LABELS,
    classify_claims,
    find_source_marker,
    has_unnegated,
    is_negated,
    segment_claims,
    summarize_labels,
)
from knowledge import FALLBACK as CONCEPT_FALLBACK
from knowledge import lookup as lookup_concept

__all__ = ["EVIDENCE_LABELS", "classify_claims", "theory_response", "review_response"]


# ═════════════════════════════════════════════════════════════════════
# F1 理论学习
# ═════════════════════════════════════════════════════════════════════
def theory_response(question: str, allow_llm: bool | None = None) -> dict[str, Any]:
    """F1：解释概念 + 正反例 + 理解检查 + 来源边界声明。

    主路径为本地知识库（knowledge.py）。仅当显式开启 ENABLE_LLM_F1=1 时，
    才在知识库未命中概念的情况下调用 LLM 补一段解释，且明确标注该段未经核验。
    """
    if not question or not question.strip():
        raise ValueError("请先输入一个概念或学习目标，例如：什么是问题—解决方案匹配？")

    question = question.strip()
    concept = lookup_concept(question)
    matched = concept is not CONCEPT_FALLBACK

    result: dict[str, Any] = {
        "flow": "F1",
        "title": concept["title"],
        "explanation": concept["explanation"],
        "how_to_judge": concept["how_to_judge"],
        "common_pitfalls": concept["pitfalls"],
        "positive_example": concept["positive"],
        "negative_example": concept["negative"],
        "understanding_checks": concept["checks"],
        "knowledge_base_hit": matched,
        "llm_enhanced": False,
        "source_note": concept["reference"],
    }

    if not matched:
        result["source_note"] = (
            concept["reference"]
            + " 本地知识库未收录该概念，本回答只提供拆解路径，不提供可能不准确的定义。"
        )
        enhanced = _f1_llm_enhance(question, allow_llm)
        if enhanced:
            result["llm_enhanced"] = True
            result["llm_unverified_note"] = (
                "以下补充说明由大模型生成，未经核验，不得直接写入正式材料；"
                "如需引用，请自行核对来源。"
            )
            result["llm_supplement"] = enhanced

    return result


def _f1_llm_enhance(question: str, allow_llm: bool | None) -> str:
    """可选增强：仅在显式开启且 LLM 可用时调用。失败一律静默返回空串。"""
    enabled = (os.getenv("ENABLE_LLM_F1", "0") == "1") if allow_llm is None else allow_llm
    if not enabled:
        return ""
    try:
        from graph.nodes import _get_llm, _llm_available

        if not _llm_available():
            return ""
        import asyncio

        prompt = (
            "你是一名创新创业课程助教。请用初学者能理解的语言解释下面这个概念，"
            "给出判断方法和一个常见误区。\n"
            "硬性要求：\n"
            "1. 不得编造任何报告名、论文名、政策文件或统计数据；\n"
            "2. 如果某个说法需要外部来源支撑，请直接写「此处需补充可核验来源」；\n"
            "3. 不要给出任何具体数字。\n\n"
            f"概念：{question}"
        )
        llm = _get_llm(temperature=0.2)
        from langchain_core.messages import HumanMessage

        response = asyncio.run(llm.ainvoke([HumanMessage(content=prompt)]))
        return (response.content or "").strip()[:1500]
    except Exception:
        # 增强层失败不影响主路径
        return ""


# ═════════════════════════════════════════════════════════════════════
# F3 评审反馈
# ═════════════════════════════════════════════════════════════════════
# 维度与权重取自第三阶段手册「项目成果100分」表，保证与课程口径一致。
_RUBRIC = [
    {
        "name": "社会价值",
        "max": 20,
        "criterion": "问题重要性、受益对象、公共/产业价值与潜在负面影响",
        "required": [
            ("明确受益对象", ("受益", "用户", "群体", "居民", "老人", "老年人", "学生", "患者", "农民", "残疾人", "家庭")),
            ("具体场景", ("社区", "学校", "医院", "乡村", "家庭", "日常", "每天", "每周", "学期", "场景")),
            ("问题重要性有依据", ("统计", "公报", "政策", "文件", "报告", "数据", "调研", "普查", "年鉴", "根据")),
            ("说明负面影响或边界", ("风险", "负面", "隐私", "伦理", "合规", "副作用", "不服务", "边界")),
        ],
    },
    {
        "name": "实践/证据过程",
        "max": 20,
        "criterion": "事实依据、模拟标注、迭代过程、关键假设与验证方案",
        "required": [
            ("列出可定位来源", ("来源", "出处", "链接", "http", "根据《", "统计公报", "年鉴", "论文", "期刊")),
            ("标注事实/假设边界", ("事实", "假设", "推断", "模拟", "F/I/H/S", "待验证", "未验证")),
            ("说明关键假设与验证方法", ("验证", "核验", "下一步", "访谈", "问卷", "试点", "测试", "MVP")),
            ("承认证据缺口或局限", ("局限", "缺口", "不足", "尚未", "暂无", "没有调研", "缺乏")),
        ],
    },
    {
        "name": "创新意义",
        "max": 20,
        "criterion": "相对替代方案的实质创新及作用",
        "required": [
            ("说明相对替代方案的差异", ("替代", "竞品", "现有做法", "相比", "差异", "不同", "对比")),
            ("说明创新的作用机制", ("机制", "流程", "结构", "组合", "场景", "算法", "定价", "协同", "标准化", "复用")),
            ("创新与用户结果挂钩", ("效率", "成本", "时间", "准确", "覆盖率", "浪费", "等待", "减少", "提升")),
        ],
    },
    {
        "name": "发展前景与可行性",
        "max": 25,
        "criterion": "实施路径、资源、商业/运营机制、财务与风险",
        "required": [
            ("说明触达/实施路径", ("渠道", "触达", "推广", "合作", "居委会", "街道", "落地", "试点", "实施")),
            ("说明成本或收入结构", ("成本", "收入", "付费", "定价", "毛利", "资金", "补贴", "预算")),
            ("说明资源与团队条件", ("团队", "资源", "技术路线", "设备", "场地", "人力", "伙伴")),
            ("说明风险与应对", ("风险", "合规", "隐私", "政策", "依赖", "应对")),
        ],
    },
    {
        "name": "团队协作与材料一致性",
        "max": 15,
        "criterion": "分工、理解程度、材料完整性与跨材料一致",
        "required": [
            ("说明分工", ("分工", "负责", "成员", "团队", "协作", "角色")),
            ("说明能力缺口", ("缺口", "不足", "缺乏", "补齐", "招募", "外聘", "学习")),
            ("材料完整可追溯", ("版本", "索引", "台账", "记录", "目录", "附录")),
        ],
    },
]

# 只写技术名词而不说明机制的「技术堆砌」特征
_TECH_ONLY = ("使用ai", "用ai", "人工智能", "大数据", "互联网+", "区块链", "智能化", "数字化", "云计算")
_MECHANISM = ("机制", "流程", "结构", "组合", "场景", "算法", "定价", "协同", "标准化", "复用", "模式")

# 0—4 质量等级锚点（第二阶段手册 7.3）
_QUALITY_ANCHORS = [
    (0, "不可用", "核心结论错误，或存在虚构来源、伪造调研、严重越权建议"),
    (1, "严重缺陷", "多项关键错误；证据不可追溯；需要人工重做大部分内容"),
    (2, "基本可用", "主要结构存在，但需要人工纠正重要错误或补足证据边界"),
    (3, "良好", "核心结论基本正确；来源可定位；事实、推断与假设边界较清楚"),
    (4, "可靠", "结论正确且自洽；证据可追溯；主动暴露不确定性并给出核验路径"),
]


def _quality_level(score_5: float) -> dict[str, Any]:
    """把 0—5 分映射到手册的 0—4 质量等级。"""
    level = int(round(score_5 * 4 / 5))
    level = max(0, min(4, level))
    for value, name, anchor in _QUALITY_ANCHORS:
        if value == level:
            return {"level": value, "name": name, "anchor": anchor}
    return {"level": 0, "name": "不可用", "anchor": ""}


# 指令性语句的特征：以祈使动词开头，且包含评审动作词。
# 这类句子是测试者/用户对 Agent 的要求，不是被评审的项目内容，必须剔除，
# 否则「请给出证据缺口和下一步建议」会被当成项目自己写了证据缺口分析。
_INSTRUCTION_HEAD = ("请", "要求", "给出", "需要", "希望", "按照", "依据", "评审", "分析", "输出", "帮")
_INSTRUCTION_BODY = ("评审", "评价", "建议", "维度", "分析", "说明", "输出", "打分", "评分")


def _strip_instructions(text: str) -> str:
    """剔除输入中的指令性语句与测试引导语，只保留项目内容。"""
    kept = []
    for sentence in segment_claims(text, limit=200):
        stripped = sentence.strip()
        if any(stripped.startswith(head) for head in _INSTRUCTION_HEAD) and any(
            body in stripped for body in _INSTRUCTION_BODY
        ):
            continue
        kept.append(stripped)
    return "。".join(kept)


def _dimension_score(spec: dict, text: str, global_cap: float | None) -> dict[str, Any]:
    """按「命中多少项必备证据」打分，再施加证据门槛上限。"""
    satisfied, missing = [], []
    for label, keywords in spec["required"]:
        hit, _ = has_unnegated(text, keywords)
        (satisfied if hit else missing).append(label)

    ratio = len(satisfied) / len(spec["required"])
    # 确定性引擎最高给到 90%：剩余空间留给 LLM 增强层与人工判断，
    # 避免「机器算满分」这种在评审中站不住脚的结论。
    # 0 项命中保留 5% 基础分（结构完整本身有价值，但在证据口径下几乎不计分）。
    factor = 0.05 + 0.85 * ratio
    raw = spec["max"] * factor

    cap = spec["max"]
    cap_reason = ""
    if global_cap is not None:
        # global_cap 是比例（如 0.5 = 不超过满分一半），需换算成该维度的绝对上限
        absolute_cap = round(spec["max"] * global_cap, 1)
        if absolute_cap < cap:
            cap = absolute_cap
            cap_reason = "全篇未发现任何可定位来源，按证据门槛限制本维度得分上限"

    score = round(min(raw, cap), 1)
    score_5 = round(score / spec["max"] * 5, 2)

    if not satisfied:
        status = "证据缺口"
    elif missing:
        status = "部分具备"
    else:
        status = "已有线索"

    return {
        "dimension": spec["name"],
        "max": spec["max"],
        "score": score,
        "score_5": score_5,
        "criterion": spec["criterion"],
        "status": status,
        "basis": "已具备：" + ("、".join(satisfied) if satisfied else "无") ,
        "missing": missing,
        "cap_reason": cap_reason,
    }


def _detect_integrity_risks(text: str, claims: list[dict]) -> list[str]:
    """识别手册列出的证据诚信风险，作为独立提示输出。"""
    risks = []

    # 风险1：断言型数字但全篇无来源
    number_claims = [
        c for c in claims
        if c["label"] == "H" and "数字" in c["reason"] and not find_source_marker(c["claim"])
    ]
    if number_claims and not find_source_marker(text):
        risks.append(
            f"存在 {len(number_claims)} 处无来源数字（例如「{number_claims[0]['claim'][:30]}」）。"
            "无法核实的数字不得进入最终结论，请补充来源或改写为假设。"
        )

    # 风险2：把模拟材料当作真实反馈表述
    has_sim = any(c["label"] == "S" for c in claims)
    feedback_words = ("用户反馈", "用户调研", "访谈显示", "问卷显示", "市场调研", "客户反馈")
    if has_sim:
        for word in feedback_words:
            if word in text and not is_negated(text, word):
                risks.append(
                    f"材料同时包含模拟内容与「{word}」表述。若该反馈来自 Agent 或情境推演，"
                    "必须标为 S；把它写成真实调研会触发手册的证据诚信红线。"
                )
                break

    # 风险3：技术堆砌被当作创新点
    lowered = text.lower()
    if any(t in lowered for t in _TECH_ONLY) and not any(m in text for m in _MECHANISM):
        risks.append(
            "材料把「使用AI/大数据」等技术采用作为创新点，但没有说明新的作用机制或带来何种可测变化。"
            "手册评分表将这类表述列为明确扣分项。"
        )

    return risks


def review_response(project_text: str, rubric: str = "创业项目基础评审") -> dict[str, Any]:
    """F3：按课程量规给出有证据门槛约束的结构化评审。

    与旧实现的区别：不再用「关键词是否出现」直接给分。旧实现会因为
    「无来源」字面包含「来源」而判定证据充分，实测让一个明确写着无来源、
    创新点仅「使用AI」的项目拿到 87/100 且证据缺口为空。
    """
    text = (project_text or "").strip()
    if len(text) < 20:
        raise ValueError("评审至少需要项目描述、目标用户或方案中的两项内容，当前输入过短。")

    claims = classify_claims(text)
    distribution = summarize_labels(claims)

    # 评审只针对项目内容；先把「请按…给出评价」这类指令句剔除
    content = _strip_instructions(text)
    if len(content) < 20:
        content = text

    has_any_source = bool(find_source_marker(content))
    # 证据门槛：全篇无来源时，任何维度不得超过满分的 40%
    global_cap = None if has_any_source else 0.4

    dimensions = [_dimension_score(spec, content, global_cap) for spec in _RUBRIC]

    # 创新维度的技术堆砌封顶
    lowered = content.lower()
    tech_only = any(t in lowered for t in _TECH_ONLY) and not any(m in content for m in _MECHANISM)
    if tech_only:
        for dim in dimensions:
            if dim["dimension"] == "创新意义":
                capped = round(dim["max"] * 0.30, 1)
                if dim["score"] > capped:
                    dim["score"] = capped
                    dim["score_5"] = round(capped / dim["max"] * 5, 2)
                    dim["status"] = "证据缺口"
                dim["cap_reason"] = (
                    dim["cap_reason"] + "；" if dim["cap_reason"] else ""
                ) + "创新点仅落在「使用AI/大数据」等技术采用上，未说明新的作用机制，按评分口径封顶"

    total = round(sum(d["score"] for d in dimensions), 1)
    quality_5 = round(sum(d["score_5"] for d in dimensions) / len(dimensions), 2)
    quality = _quality_level(quality_5)

    # 证据缺口 = 各维度缺失项去重，再补齐全局缺口
    gaps: list[str] = []
    for dim in dimensions:
        for item in dim["missing"]:
            entry = f"【{dim['dimension']}】{item}"
            if entry not in gaps:
                gaps.append(entry)
    if not has_any_source:
        gaps.insert(0, "全篇没有任何可定位来源（机构/标题/年份/链接），所有结论目前只能作为假设。")
    if distribution["counts"]["S"]:
        gaps.append(
            f"存在 {distribution['counts']['S']} 条模拟材料，只能用于生成待验证假设，不能作为市场证据。"
        )

    integrity_risks = _detect_integrity_risks(content, claims)

    # 修改建议：优先给最弱维度，再给通用动作
    weakest = min(dimensions, key=lambda d: d["score_5"])
    recommendations = [
        f"优先补强最弱维度【{weakest['dimension']}】：{ '、'.join(weakest['missing']) or '结构基本完整，转为补充可核验来源' }。",
        "把最危险的 3—5 个假设单独列出，为每个假设写出课程内可完成的核验动作与失败判定标准。",
        "每个关键数字补充来源、计算式或明确的假设标记；不要将 Agent 输出直接当作市场事实。",
        "用「结论—依据—边界—下一步验证」重写最重要的项目结论。",
    ]
    if tech_only:
        recommendations.insert(1, "重写创新点：去掉所有技术名词后，说明你的新机制让对方哪个指标发生了变化。")

    return {
        "flow": "F3",
        "rubric": rubric,
        "overall_score": total,
        "overall_5": quality_5,
        "quality_level": quality,
        "dimensions": dimensions,
        "evidence_gaps": gaps,
        "evidence_distribution": distribution,
        "integrity_risks": integrity_risks,
        "recommendations": recommendations,
        "claim_labels": claims,
        "integrity_note": (
            "本评审在本地完成，未核验外部来源，也不会把输入中的数字、访谈、订单或政策自动认定为事实。"
            "来源标记只代表文本中出现了「来源/出处/机构名」等线索，不构成对内容真实性的认定。"
        ),
        "scoring_note": (
            "各维度先按必备证据的命中比例打分，再施加证据门槛：全篇无可定位来源时，"
            "任何维度不超过满分的 50%；创新点若仅落在技术采用上，创新维度不超过满分的 30%。"
        ),
    }
