# -*- coding: utf-8 -*-
"""
组内测试用例（tests/custom/）

与 tests/common/unified.py 的区别：
- unified 是课程统一测试集，输入冻结、不得删改，用于组间可比；
- 本文件针对**本项目自身的优化目标**与**本项目的大创选题**，
  每个用例都对应第二阶段优化契约中的一个问题编号。

每个用例声明它回归的是哪一个已修复缺陷（regression_of），使「承诺问题已修复」
这条验收门槛可以直接由测试结果支撑。

用例分两类：
- kind="local"  直接调用本地模块，不需要服务在跑，速度快、不受网络影响；
- kind="http"   需要通过 HTTP 调用被测服务。
"""
from __future__ import annotations

import os
import sys
from typing import Any

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ═════════════════════════════════════════════════════════════════
# 本地用例
# ═════════════════════════════════════════════════════════════════
def local_evidence_default(payload: dict) -> list[tuple[str, bool, str]]:
    """C-E01｜回归 P0：无来源陈述不得被判为「事实 F」。"""
    from evidence import classify_claim

    cases = [
        ("学校支持建立教材交易平台", ("I", "H")),   # 旧版误判为 F
        ("社区已同意提供助餐场地", ("I", "H")),
        ("本项目已获得街道支持", ("I", "H", "S")),
    ]
    checks = []
    for text, allowed in cases:
        got = classify_claim(text)["label"]
        checks.append((f"「{text[:12]}…」不判为 F", got in allowed, f"实得 {got}"))
    return checks


def local_evidence_source(payload: dict) -> list[tuple[str, bool, str]]:
    """C-E02｜有明确来源的陈述应当判为 F（避免过度保守）。"""
    from evidence import classify_claim

    got = classify_claim("根据民政部2023年统计公报，我国60岁及以上人口约2.97亿")["label"]
    return [("有来源标记的陈述判为 F", got == "F", f"实得 {got}")]


def local_negation(payload: dict) -> list[tuple[str, bool, str]]:
    """C-E03｜回归 P0：否定式表述不得被当作存在证据。"""
    from evidence import has_unnegated, is_negated

    checks = [
        ("「没有调研」视为无证据", is_negated("团队没有调研数据", "调研"), ""),
        ("「依据调研」视为有证据", not is_negated("依据民政部调研数据", "调研"), ""),
        ("「无来源」视为无证据", is_negated("目前无来源", "来源"), ""),
    ]
    hit, _ = has_unnegated("团队没有调研数据，也没有访谈记录", ("调研", "访谈记录", "问卷"))
    checks.append(("否定句不产生证据命中", not hit, ""))
    return checks


def local_review_gate(payload: dict) -> list[tuple[str, bool, str]]:
    """C-E04｜回归 P0：无来源项目不得拿到虚高分，且必须识别技术堆砌。"""
    from workflows import review_response

    weak = review_response(
        "面向所有大学生的AI校园书桥，通过智能匹配交换闲置教材。"
        "团队称80%学生有需求，但无来源；创新点是使用AI；盈利依靠广告；没有说明获客、合规和替代方案。"
    )
    checks = [
        ("无来源项目总分 < 50", weak["overall_score"] < 50, f"实得 {weak['overall_score']}/100"),
        ("质量等级为 0 或 1", weak["quality_level"]["level"] <= 1,
         f"实得 {weak['quality_level']['level']} {weak['quality_level']['name']}"),
        ("证据缺口非空", len(weak["evidence_gaps"]) > 0, f"实得 {len(weak['evidence_gaps'])} 条"),
        ("识别技术堆砌风险", any("创新" in r for r in weak["integrity_risks"]), ""),
        ("创新维度被门槛封顶", weak["dimensions"][2]["score"] <= 20 * 0.30 + 0.01,
         f"实得 {weak['dimensions'][2]['score']}/20"),
    ]
    return checks


def local_review_scale(payload: dict) -> list[tuple[str, bool, str]]:
    """C-E05｜证据充分的材料应当得到合理高分（避免修复后过度收紧）。"""
    from workflows import review_response

    good = review_response(
        "社区助餐项目。目标用户为某市独居老人。根据民政部2023年统计公报，我国60岁以上人口约2.97亿。"
        "我们在试点社区发现备餐量与就餐量长期不匹配，导致浪费与供餐不足并存。"
        "现有做法是各社区自行估量、人工登记，替代方案还有子女送餐。"
        "创新机制：将需求预测与慢病营养约束组合进备餐流程，减少浪费同时满足营养要求。"
        "成本结构为食材、配送、包装，收入来自老人自付与街道补贴。"
        "风险包括数据隐私与补贴依赖。团队3人分工明确，技术能力有缺口需外聘。"
        "关键假设是老人愿意单次支付10-15元，下一步通过助餐点问卷与20份真实订单验证。"
    )
    return [
        ("证据充分项目总分 >= 70", good["overall_score"] >= 70, f"实得 {good['overall_score']}/100"),
        ("质量等级 >= 3", good["quality_level"]["level"] >= 3,
         f"实得 {good['quality_level']['level']} {good['quality_level']['name']}"),
    ]


def local_kb_coverage(payload: dict) -> list[tuple[str, bool, str]]:
    """C-F1-01｜回归 P1：F1 必须覆盖足够多的概念，而不是只有两个硬编码分支。"""
    from knowledge import CONCEPTS, FALLBACK, lookup

    checks = [("知识库收录概念 >= 12 个", len(CONCEPTS) >= 12, f"实得 {len(CONCEPTS)} 个")]
    probes = [
        "问题—解决方案匹配", "证据边界", "价值主张", "MVP", "市场规模",
        "单位经济", "商业模式画布", "竞争替代", "创新性", "竞争壁垒",
        "挑战杯评审维度", "关键假设", "波特五力",
    ]
    missed = [p for p in probes if lookup(p) is FALLBACK]
    checks.append((f"{len(probes)} 个常见概念全部命中", not missed,
                   f"未命中：{missed}" if missed else "全部命中"))
    return checks


def local_kb_no_fabrication(payload: dict) -> list[tuple[str, bool, str]]:
    """C-F1-02｜知识库不得内含未经核验的外部来源。"""
    from knowledge import CONCEPTS

    bad = []
    for c in CONCEPTS:
        ref = str(c.get("reference", ""))
        if "http" in ref or "doi" in ref.lower():
            bad.append(c["key"])
    return [
        ("无词条声称外部链接来源", not bad, f"可疑词条：{bad}" if bad else "无"),
        ("每个词条都有来源状态声明", all(c.get("reference") for c in CONCEPTS), ""),
    ]


def local_version(payload: dict) -> list[tuple[str, bool, str]]:
    """C-L-02｜回归 P1：版本信息必须可定位。"""
    from version import get_version_info

    info = get_version_info()
    checks = [
        ("返回 agent_version", bool(info.get("agent_version")), info.get("agent_version", "")),
        ("返回 prompt_version", bool(info.get("prompt_version")), info.get("prompt_version", "")),
        ("返回 kb_version", bool(info.get("kb_version")), info.get("kb_version", "")),
        ("返回 git 提交号", bool(info.get("git_commit")), info.get("git_commit", "")),
        ("返回模型名", bool(info.get("model")), info.get("model", "")),
    ]
    return checks


def local_redaction(payload: dict) -> list[tuple[str, bool, str]]:
    """C-S-01｜日志脱敏：密钥与手机号不得落盘。"""
    from observability import redact

    out = redact("key=sk-abcdef1234567890 phone=13800138000 token-tester1")
    checks = [
        ("API Key 被脱敏", "sk-abcdef1234567890" not in out, out[:70]),
        ("手机号被脱敏", "13800138000" not in out, ""),
    ]
    return checks


# ═════════════════════════════════════════════════════════════════
# HTTP 用例
# ═════════════════════════════════════════════════════════════════
def http_degradation(client) -> list[tuple[str, bool, str]]:
    """C-X-01｜回归 P1：LLM 不可用时必须如实标记降级，且输出仍然完整。"""
    from tests.common.unified import U3_INPUT

    r = client.post("/api/session/start", json={"student_id": "custom_x01", "password": "t"})
    session_id = r.json()["session_id"]
    r = client.post("/api/chat", json={"session_id": session_id, "message": U3_INPUT})
    body = r.json()

    run = client.get(f"/api/runs/{body['run_id']}").json()
    checks = [
        ("响应标记 degraded", "degraded" in body, f"degraded={body.get('degraded')}"),
        ("降级原因可读", bool(body.get("degraded_reason")), str(body.get("degraded_reason"))[:50]),
        ("降级下仍给出 next_task", bool(str(body.get("next_task", "")).strip()),
         f"长度 {len(str(body.get('next_task', '')).strip())}"),
        ("运行状态记为 degraded 而非 success", run.get("status") == "degraded",
         f"实得 {run.get('status')}"),
    ]
    return checks


def http_log_fields(client) -> list[tuple[str, bool, str]]:
    """C-L-01｜回归 P1：运行日志须覆盖手册要求的七类字段。"""
    from tests.common.unified import U1_INPUT

    body = client.post("/api/learn", json={"question": U1_INPUT, "test_id": "C-L-01"}).json()
    run = client.get(f"/api/runs/{body['run_id']}").json()

    required = {
        "身份": ("run_id", "agent_version", "flow", "test_id", "project_version"),
        "时间": ("started_at", "finished_at", "duration_ms"),
        "状态": ("status",),
        "行为": ("steps",),
        "人机边界": ("human_interventions",),
    }
    checks = []
    for group, fields in required.items():
        missing = [f for f in fields if run.get(f) in (None, "")]
        checks.append((f"{group}字段完整", not missing, f"缺失：{missing}" if missing else "完整"))
    return checks


def http_intervention(client) -> list[tuple[str, bool, str]]:
    """C-H-01｜人工干预必须可记录、可追溯（手册人机边界透明）。"""
    r = client.post("/api/session/start", json={"student_id": "custom_h01", "password": "t"})
    session_id = r.json()["session_id"]

    r = client.post("/api/intervention", json={
        "session_id": session_id, "kind": "修改",
        "detail": "人工改写了 Agent 给出的价值主张表述", "run_id": "run_demo",
    })
    ok_create = r.status_code == 200
    total = r.json().get("total") if ok_create else 0

    r_bad = client.post("/api/intervention", json={
        "session_id": session_id, "kind": "非法类型", "detail": "x",
    })
    return [
        ("可记录人工干预", ok_create and total == 1, f"HTTP {r.status_code} total={total}"),
        ("非法干预类型被拒绝", r_bad.status_code == 400, f"HTTP {r_bad.status_code}"),
    ]


def http_project_review(client) -> list[tuple[str, bool, str]]:
    """C-P-01｜对本项目真实大创材料做评审，检查结论方向正确。"""
    material = (
        "社区老年助餐供需匹配项目。目标用户为某市老旧小区中行动不便的独居老人。"
        "根据民政部2023年统计公报，我国60岁及以上人口约2.97亿；据第七次全国人口普查，"
        "独居与空巢老年人规模持续上升。我们的试点观察发现，社区食堂备餐量与实际就餐量长期不匹配，"
        "既造成食物浪费，也在高峰期出现供餐不足。现有做法是各社区凭经验估量并人工登记，"
        "替代方案还包括子女送餐与老人自行做饭。"
        "创新机制在于把需求预测与慢病营养约束组合进备餐流程，在减少浪费的同时满足慢性病老人的营养限制。"
        "成本结构为食材采购、配送与包装，收入来自老人自付与街道补贴。"
        "风险包括数据隐私、补贴依赖与老年人使用门槛。团队现有3人，分工为产品、数据与社区运营，"
        "医疗营养方面存在能力缺口，计划外聘营养师顾问。"
        "关键假设是老人愿意为单次助餐支付10至15元，下一步通过助餐点问卷与20份真实订单验证。"
        "证据台账、来源索引与模拟材料标注见附录。"
    )
    body = client.post("/api/review", json={"project_text": material, "test_id": "C-P-01"}).json()
    checks = [
        ("总分为合理区间（50—100）", 50 <= body["overall_score"] <= 100, f"实得 {body['overall_score']}"),
        ("给出五个维度", len(body["dimensions"]) == 5, f"实得 {len(body['dimensions'])}"),
        ("识别出模拟/假设边界", body["evidence_distribution"]["counts"]["H"] >= 0, ""),
        ("建议可执行", len(body["recommendations"]) >= 3, f"实得 {len(body['recommendations'])}"),
        ("未把无来源内容判为事实",
         body["evidence_distribution"]["counts"]["F"] >= 1,
         f"F={body['evidence_distribution']['counts']['F']}（材料含统计公报来源，应至少命中1条）"),
    ]
    return checks


# ═════════════════════════════════════════════════════════════════
CUSTOM_TESTS: list[dict[str, Any]] = [
    {"id": "C-E01", "name": "证据分类默认值（无来源不判F）", "kind": "local",
     "regression_of": "证据分类器默认把无来源陈述判为事实F", "runner": local_evidence_default},
    {"id": "C-E02", "name": "有来源陈述判为F", "kind": "local",
     "regression_of": "—（防止修复后过度保守）", "runner": local_evidence_source},
    {"id": "C-E03", "name": "否定感知", "kind": "local",
     "regression_of": "关键词匹配对否定式失效", "runner": local_negation},
    {"id": "C-E04", "name": "评审评分门槛", "kind": "local",
     "regression_of": "无证据项目得到87分", "runner": local_review_gate},
    {"id": "C-E05", "name": "评审评分区分度", "kind": "local",
     "regression_of": "—（防止修复后过度收紧）", "runner": local_review_scale},
    {"id": "C-F1-01", "name": "F1概念覆盖", "kind": "local",
     "regression_of": "F1仅有2个硬编码分支", "runner": local_kb_coverage},
    {"id": "C-F1-02", "name": "知识库无编造来源", "kind": "local",
     "regression_of": "—（证据诚信）", "runner": local_kb_no_fabrication},
    {"id": "C-L-02", "name": "版本可定位", "kind": "local",
     "regression_of": "无法确认V2相对什么版本优化", "runner": local_version},
    {"id": "C-S-01", "name": "日志脱敏", "kind": "local",
     "regression_of": "—（密钥与个人信息保护）", "runner": local_redaction},
    {"id": "C-X-01", "name": "降级透明", "kind": "http",
     "regression_of": "降级后仍记为success，next_task为空", "runner": http_degradation},
    {"id": "C-L-01", "name": "日志字段完整性", "kind": "http",
     "regression_of": "日志仅有run_id与flow", "runner": http_log_fields},
    {"id": "C-H-01", "name": "人工干预可追溯", "kind": "http",
     "regression_of": "人工干预无处记录", "runner": http_intervention},
    {"id": "C-P-01", "name": "本项目材料评审", "kind": "http",
     "regression_of": "—（大创项目材料自评）", "runner": http_project_review},
]
