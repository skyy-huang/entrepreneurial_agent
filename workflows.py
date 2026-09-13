"""三个可独立验收的工作流：理论学习、项目指导、评审反馈。"""
from __future__ import annotations

import re
from typing import Any


EVIDENCE_LABELS = {
    "F": "事实：已有可定位来源或明确材料支持",
    "I": "推断：基于事实做出的解释，仍需验证",
    "H": "假设：尚未被材料或数据支持的判断",
    "S": "模拟：课程/教师/Agent设定的情境，不等于真实市场证据",
}


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def classify_claims(text: str) -> list[dict[str, str]]:
    """保守地标记常见陈述，宁可提示核验，也不把数字当作事实。"""
    claims = [part.strip(" ：:;；。\n") for part in re.split(r"[\n。！？!?；;]+", text) if part.strip()]
    result = []
    for claim in claims[:20]:
        if _has_any(claim, ("模拟", "假设情境", "教师提供", "Agent认为", "模拟用户")):
            label = "S"
        elif _has_any(claim, ("假设", "预计", "可能", "计划", "愿意", "会有", "应该")) or re.search(r"\d+%|\d+元|\d+万|80%", claim):
            label = "H"
        elif _has_any(claim, ("因此", "说明", "意味着", "推测", "表明")):
            label = "I"
        else:
            label = "F"
        result.append({"claim": claim, "label": label, "label_name": EVIDENCE_LABELS[label], "can_use_now": "是" if label == "F" else "仅可作为待验证输入"})
    return result


def theory_response(question: str) -> dict[str, Any]:
    """F1：固定结构输出，避免理论学习退化成长篇自由问答。"""
    if not question.strip():
        raise ValueError("请先输入一个概念或学习目标，例如：什么是问题—解决方案匹配？")
    lower = question.lower()
    if _has_any(lower, ("问题", "解决方案", "匹配", "problem", "solution")):
        concept = "问题—解决方案匹配"
        explanation = "它要求方案直接回应一个具体用户在具体场景中的关键问题，而不是把技术功能当成价值。判断时依次看：用户是谁、何时遇到问题、现有做法是什么、方案改变了什么结果。"
        positive = "面向期末集中整理教材的本科生，用校内可检索的教材交换流程减少找书和沟通时间。"
        negative = "面向所有人，用AI匹配一切闲置物品，默认用户会因为“智能”而使用。"
        checks = ["你的目标用户能否缩小到一个具体角色？", "他们现在用什么替代方案，具体损失是什么？", "你的方案改变的是任务结果，还是只是增加了一个技术功能？"]
    elif _has_any(lower, ("证据", "事实", "假设", "推断", "模拟")):
        concept = "证据边界 F/I/H/S"
        explanation = "事实可回到来源，推断是对事实的解释，假设是尚未证实的判断，模拟是课程或系统设定的情境。它们可以同时进入项目分析，但不能用后面三类冒充真实市场证据。"
        positive = "“教师提供的模拟情境显示，学生在学期末集中处理教材”应标记为模拟 S。"
        negative = "“80%的大学生每学期都有需求”如果没有来源，不能因为有数字就标记为事实 F。"
        checks = ["这句话能否定位到原始来源？", "它是材料本身，还是你对材料的解释？", "下一步要用什么资料或测试把它变成更可靠的证据？"]
    else:
        concept = "创业项目的证据化思考"
        explanation = "先把任务拆成用户、场景、问题、替代方案、方案和关键假设，再为每个结论标记事实、推断、假设或模拟。没有证据时应明确缺口，而不是补写一个听起来完整的市场故事。"
        positive = "把“用户刚需”改写为“目标用户在某场景下每周遇到一次问题，当前用微信群解决，仍有等待时间”，并注明来源或待验证。"
        negative = "直接写出市场规模、支付意愿和用户比例，但没有来源、公式或验证计划。"
        checks = ["你的结论对应哪个具体用户和场景？", "哪些内容目前只是假设？", "你准备先验证哪一个最危险的假设？"]
    return {"flow": "F1", "title": concept, "explanation": explanation, "positive_example": positive, "negative_example": negative, "understanding_checks": checks, "source_note": "本回答未调用外部资料；涉及具体政策、市场数字或赛事规则时，请补充可核验来源。"}


def review_response(project_text: str, rubric: str = "创业项目基础评审") -> dict[str, Any]:
    """F3：按第三阶段量规生成可执行、边界透明的确定性评审。"""
    text = project_text.strip()
    if len(text) < 20:
        raise ValueError("评审至少需要项目描述、目标用户或方案中的两项内容，当前输入过短。")
    checks = {
        "社会价值": ("问题是否对明确受益者产生可说明的改善", _has_any(text, ("学生", "老人", "患者", "农民", "环保", "公共", "效率"))),
        "实践/证据过程": ("是否提供来源、材料、数字的口径与证据边界", _has_any(text, ("来源", "数据", "调研", "访谈", "资料", "证据", "模拟"))),
        "创新意义": ("是否说明相对替代方案的实质差异", _has_any(text, ("创新", "替代", "竞品", "区别", "机制", "效率"))),
        "发展前景": ("是否说明触达方式、成本、收入或持续方式", _has_any(text, ("渠道", "成本", "收入", "付费", "运营", "规模"))),
        "团队/实施条件": ("是否说明团队能力、资源、技术路线与风险", _has_any(text, ("团队", "技术", "资源", "风险", "合规", "实施"))),
    }
    dimensions = []
    for name, (criterion, passed) in checks.items():
        dimensions.append({"dimension": name, "score": 3 if passed else 1, "criterion": criterion, "status": "已有线索" if passed else "证据缺口"})
    gaps = []
    if not _has_any(text, ("用户", "学生", "客户", "受益者")): gaps.append("没有明确具体目标用户，不应使用“所有人”。")
    if not _has_any(text, ("来源", "数据", "调研", "访谈", "资料", "证据")): gaps.append("没有可定位证据；数字、需求和政策表述只能标记为假设。")
    if not _has_any(text, ("替代", "竞品", "现有", "微信群", "人工")): gaps.append("没有比较现有做法，包括“不使用产品”的替代方案。")
    if not _has_any(text, ("风险", "合规", "隐私", "伦理")): gaps.append("没有呈现技术、数据、伦理或合规风险。")
    claims = classify_claims(text)
    recommendations = [
        "把最危险的 3—5 个假设单独列出，并为每个假设写出课程内可做的核验动作。",
        "每个关键数字补充来源、计算式或明确的模拟标记；不要将 Agent 输出直接当作市场事实。",
        "用“结论—依据—边界—下一步验证”重写最重要的项目结论。",
    ]
    if gaps:
        recommendations.insert(0, f"先修复首要缺口：{gaps[0]}")
    total = round(sum(item["score"] for item in dimensions) / len(dimensions) / 3 * 100)
    return {"flow": "F3", "rubric": rubric, "overall_score": total, "dimensions": dimensions, "evidence_gaps": gaps, "recommendations": recommendations, "claim_labels": claims, "integrity_note": "本评审未核验外部来源，不会把输入中的数字、访谈、订单或政策自动认定为事实。"}
