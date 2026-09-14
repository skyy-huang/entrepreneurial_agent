"""
证据边界引擎（Evidence Boundary Engine）

对应三阶段手册的核心概念：
    事实 F —— 可以由资料或案例直接支持（必须能回到来源）
    推断 I —— 基于事实作出的合理解释，仍需验证
    假设 H —— 尚未验证、需要后续检验
    模拟 S —— 由 Agent 或教师情境推演产生，不能作为事实证据

设计原则（这是本模块存在的理由）：
1. **默认保守**。没有明确来源标记的陈述一律不判为 F。旧实现把无法识别的
   陈述默认标为「事实 F」并允许直接采用，实测会把「学校支持建立教材交易
   平台」这类无来源主张判成事实——这会直接触发手册的 G3 证据诚信门槛。
2. **否定感知**。「无来源」「没有调研」「缺乏数据」不能因为字面包含
   「来源」「调研」「数据」就被当作存在证据。旧实现的关键词匹配对否定式
   完全失效，导致一个明确写着「无来源」的项目在评审中 evidence_gaps 为空。
3. **可执行**。每条判定都附带下一步核验动作，而不只是一个标签。
"""
from __future__ import annotations

import re
from typing import Any

# ── 标签定义 ─────────────────────────────────────────────────────────
EVIDENCE_LABELS = {
    "F": "事实：已有可定位来源或明确材料支持",
    "I": "推断：基于事实做出的解释，仍需验证",
    "H": "假设：尚未被材料或数据支持的判断",
    "S": "模拟：课程/教师/Agent设定的情境，不等于真实市场证据",
}

# 每种标签的「现在能否采用」口径
CAN_USE_NOW = {
    "F": "是——仍需标注来源出处",
    "I": "仅可作为待验证输入，不得作为结论依据",
    "H": "仅可作为待验证输入，不得作为结论依据",
    "S": "不得作为证据；只能用于生成待验证假设",
}

# ── 标记词表 ─────────────────────────────────────────────────────────
SIMULATION_MARKERS = (
    "模拟", "假设情境", "情景假设", "情境假设", "教师提供", "教师案例",
    "案例包", "Agent扮演", "Agent认为", "Agent生成", "虚拟用户", "角色扮演",
    "推演", "沙盘", "情景设定", "设定情境", "模拟用户", "模拟反馈",
)

HYPOTHESIS_MARKERS = (
    "假设", "预计", "预估", "预期", "可能", "也许", "或许", "计划", "打算",
    "愿意", "会有", "应该", "希望", "拟", "目标", "预测", "猜想", "判断为",
    "我们认为", "团队认为", "估计", "大致",
)

INFERENCE_MARKERS = (
    "因此", "所以", "因而", "说明", "意味着", "推测", "表明", "可见",
    "由此可见", "推论", "暗示", "反映出", "可以看出", "总的来说",
)

# 来源标记——出现这些才可能构成 F。
# 刻意不使用裸「据」「报告」「通知」「统计」：它们会被「数据」「据我们了解」
# 一类普通表述误命中，把无来源的主张抬成事实。
SOURCE_MARKERS = (
    "来源", "出处", "根据《", "据《", "参考", "引用",
    "统计公报", "统计年鉴", "年鉴", "普查", "白皮书",
    "政策文件", "条例", "法规", "国家标准", "行业标准", "征求意见稿",
    "论文", "期刊", "调研报告", "访谈记录", "问卷结果", "官方发布",
    "民政部", "教育部", "国家统计局", "工信部", "农业农村部", "卫健委",
    "人民政府", "发展和改革委员会",
)

# 数字陈述（无法核实的数字不得进入最终结论）
_NUMBER_RE = re.compile(
    r"\d[\d,.]*\s*(?:%|％|元|万元|亿元|亿|万|人|户|家|所|次|倍|天|小时|分钟|岁)"
)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+|doi\.org/\S+", re.IGNORECASE)
_BOOKTITLE_RE = re.compile(r"《[^》]{2,40}》")

# 否定前缀——用于否定感知
NEGATION_PREFIXES = (
    "没有", "无", "未", "不", "缺乏", "缺少", "暂无", "未见", "尚未",
    "无从", "无法", "不能", "并未", "从没", "并不", "非",
)
# 否定词与关键字的允许距离（字符）
_NEGATION_WINDOW = 8


def is_negated(text: str, keyword: str) -> bool:
    """判断 keyword 在 text 中是否处于否定语境。

    例：is_negated("团队没有调研数据", "调研") -> True
        is_negated("依据民政部调研数据", "调研") -> False
    """
    start = 0
    while True:
        idx = text.find(keyword, start)
        if idx == -1:
            return False
        window = text[max(0, idx - _NEGATION_WINDOW):idx]
        if any(neg in window for neg in NEGATION_PREFIXES):
            return True
        start = idx + len(keyword)


def has_unnegated(text: str, keywords: tuple[str, ...]) -> tuple[bool, str]:
    """返回 (是否存在未被否定的关键词, 命中的关键词)。"""
    for keyword in keywords:
        if keyword in text and not is_negated(text, keyword):
            return True, keyword
    return False, ""


def find_source_marker(text: str) -> str:
    """查找显式来源标记。返回命中的标记，未命中返回空串。"""
    url = _URL_RE.search(text)
    if url:
        return url.group(0)[:60]
    for marker in SOURCE_MARKERS:
        if marker in text and not is_negated(text, marker):
            return marker
    title = _BOOKTITLE_RE.search(text)
    if title:
        return title.group(0)
    return ""


# ── 分句 ─────────────────────────────────────────────────────────────
_SPLIT_RE = re.compile(r"[\n。！？!?；;]+")
_LEADING_NOISE = "0123456789①②③④⑤⑥⑦⑧⑨⑩、.,，：:;；）)】」』\"' \t　"


def segment_claims(text: str, limit: int = 30) -> list[str]:
    """把材料切分为可独立判定的陈述句。"""
    parts = []
    for raw in _SPLIT_RE.split(text or ""):
        claim = raw.strip().strip(_LEADING_NOISE).strip()
        # 过短片段（"综上"、"因此"）不构成独立结论
        if len(claim) >= 6:
            parts.append(claim)
    return parts[:limit]


# ── 核心分类 ─────────────────────────────────────────────────────────
def classify_claim(claim: str) -> dict[str, Any]:
    """对单条陈述做保守的 F/I/H/S 判定。

    判定顺序（先判「不能被当作事实」的情形，最后才考虑 F）：
        S 模拟 → 无来源数字 → I 推断 → H 假设 → F 事实（需来源标记）→ I 兜底

    推断排在假设之前，是因为手册表7把「因此该类机构可能存在……需求」明确
    归为推断 I —— 推断连接词比「可能」这类模糊限定词更能决定陈述性质。
    无来源数字排在推断之前，是为了拦住「因此80%的用户会付费」这类情况。
    """
    source = find_source_marker(claim)
    has_number = bool(_NUMBER_RE.search(claim))

    # 1) 模拟：由情境推演产生的材料
    sim_hit = next((m for m in SIMULATION_MARKERS if m in claim), "")
    if sim_hit:
        return _verdict(
            "S", claim,
            reason=f"出现情境标记「{sim_hit}」，属于课程/教师/Agent 设定的模拟材料",
            verify="把该情境转化为一条待验证假设，并设计课程内可完成的核验动作",
        )

    # 2) 无来源数字：无法核实的数字不得进入最终结论
    if has_number and not source:
        return _verdict(
            "H", claim,
            reason="陈述包含具体数字但没有可定位来源；无法核实的数字不得进入最终结论",
            verify="补充该数字的机构、标题、年份与链接，或改标为假设并给出估算公式",
        )

    # 3) 推断：由其他事实推出的解释
    inf_hit = next((m for m in INFERENCE_MARKERS if m in claim), "")
    if inf_hit:
        return _verdict(
            "I", claim,
            reason=f"出现推断连接词「{inf_hit}」，属于对材料作出的解释",
            verify="写出所依据的前提事实，并说明该解释在什么条件下不成立",
        )

    # 4) 假设：意图、意愿、预测类表述
    hyp_hit = next((m for m in HYPOTHESIS_MARKERS if m in claim), "")
    if hyp_hit:
        return _verdict(
            "H", claim,
            reason=f"出现未验证判断标记「{hyp_hit}」",
            verify="写明核验对象、样本口径与判定标准，作为下一步真实验证任务",
        )

    # 5) 事实：必须能回到来源
    if source:
        return _verdict(
            "F", claim,
            reason=f"命中来源标记「{source}」",
            verify="记录来源标题、机构、年份与链接，确保他人可以复核",
        )

    # 6) 兜底：不能证明有来源，就不给 F
    return _verdict(
        "I", claim,
        reason="未发现可定位来源，按保守口径降级为待核验陈述（不判为事实）",
        verify="补充来源，或明确写为假设并给出验证方法",
    )


def _verdict(label: str, claim: str, reason: str, verify: str) -> dict[str, Any]:
    return {
        "claim": claim,
        "label": label,
        "label_name": EVIDENCE_LABELS[label],
        "can_use_now": CAN_USE_NOW[label],
        "reason": reason,
        "verification_step": verify,
    }


def classify_claims(text: str) -> list[dict[str, Any]]:
    """把一段项目材料拆分为 F/I/H/S 逐条判定。"""
    return [classify_claim(claim) for claim in segment_claims(text)]


def summarize_labels(claims: list[dict[str, Any]]) -> dict[str, Any]:
    """统计标注分布，并给出对项目结论的整体提示。"""
    counts = {"F": 0, "I": 0, "H": 0, "S": 0}
    for item in claims:
        counts[item["label"]] = counts.get(item["label"], 0) + 1
    total = sum(counts.values()) or 1
    notes = []
    if counts["F"] == 0:
        notes.append("全部陈述均未命中来源标记：当前材料不足以支撑「事实」级结论，结论只能作为假设使用。")
    if counts["S"]:
        notes.append(f"存在 {counts['S']} 条模拟材料：不得作为真实市场证据，只能用于生成待验证假设。")
    if counts["H"] >= max(2, total // 2):
        notes.append("假设占比较高：请优先挑出最危险的 3—5 项，逐项写出验证方法。")
    return {
        "counts": counts,
        "total": total,
        "fact_ratio": round(counts["F"] / total, 2),
        "notes": notes,
    }
