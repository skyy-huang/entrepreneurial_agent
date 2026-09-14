# -*- coding: utf-8 -*-
"""
生成《06_自测试报告》交付文档。

数据来源：tests/reports/ 下最新一次的运行结果（由 tests/run_tests.py 产出）。
本脚本不做任何美化或筛选：通过项与未通过项全部保留，未通过项单列成待改进清单。

用法：
    python deliverables/build/generate_selftest.py
    python deliverables/build/generate_selftest.py --report tests/reports/V2_xxx.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)

OUT_PATH = os.path.join(_ROOT, "deliverables", "src", "06_自测试报告.md")

QUALITY_ANCHORS = [
    (0, "不可用", "核心结论错误，或存在虚构来源、伪造调研、严重越权建议"),
    (1, "严重缺陷", "多项关键错误；证据不可追溯；需要人工重做大部分内容"),
    (2, "基本可用", "主要结构存在，但需要人工纠正重要错误或补足证据边界"),
    (3, "良好", "核心结论基本正确；来源可定位；事实、推断与假设边界较清楚"),
    (4, "可靠", "结论正确且自洽；证据可追溯；主动暴露不确定性并给出核验路径"),
]


def latest_report() -> str:
    """取最新一份测试结果。

    按修改时间排序而不是按文件名：标签里含 `-` 时字典序会排到 `_` 之前，
    按名字取「最后一个」会拿到过期报告。
    """
    pattern = os.path.join(_ROOT, "tests", "reports", "*.json")
    files = glob.glob(pattern)
    if not files:
        raise SystemExit("未找到测试报告，请先运行：python tests/run_tests.py --label V2 --suite both")
    return max(files, key=os.path.getmtime)


def render(data: dict, source_path: str) -> str:
    v = data.get("version", {})
    s = data.get("summary", {})
    unified = [r for r in data["results"] if r.get("suite") != "custom"]
    custom = [r for r in data["results"] if r.get("suite") == "custom"]
    failed = [
        (r["id"], r["name"], c["name"], c.get("detail", ""))
        for r in data["results"] for c in r["checks"] if not c["passed"]
    ]
    errors = [(r["id"], r["name"], r["error"]) for r in data["results"] if r.get("error")]

    L: list[str] = []
    add = L.append

    add("# 自测试报告")
    add("")
    add("**被测系统**：双创智能教练（Agent V2）  ")
    add(f"**Agent 版本**：`{v.get('agent_version', '-')}`（阶段 `{v.get('agent_stage', '-')}`）  ")
    add(f"**报告标签**：{data.get('label', '-')}  ")
    add(f"**服务地址**：{data.get('base_url', '-')}")
    add("")

    # ── 测试环境 ──────────────────────────────────────────────
    add("## 一、测试环境与版本")
    add("")
    add("> 手册要求：测试结果必须带 Agent 版本、测试编号、时间、模型和项目材料版本，")
    add("> 使结论能够回到具体版本与运行记录。")
    add("")
    add("| 项目 | 值 |")
    add("|------|-----|")
    add(f"| Agent 版本 | {v.get('agent_version', '-')} |")
    add(f"| 提示词版本 | {v.get('prompt_version', '-')} |")
    add(f"| 知识库版本 | {v.get('kb_version', '-')} |")
    add(f"| 模型 | {v.get('model', '-')} |")
    add(f"| git 提交号 | `{v.get('git_commit', '-')}` |")
    add(f"| 工作区存在未提交改动 | {v.get('git_dirty', '-')} |")
    add(f"| 开始时间 | {data.get('started_at', '-')} |")
    add(f"| 结束时间 | {data.get('finished_at', '-')} |")
    add(f"| 原始结果文件 | `{os.path.relpath(source_path, _ROOT)}` |")
    add("")
    if v.get("git_dirty"):
        add("> ⚠️ 本次测试时工作区存在未提交改动，因此提交号不能单独作为版本凭证，"
            "需与目录快照或压缩包一并留存。")
        add("")

    # ── 评分锚点 ──────────────────────────────────────────────
    add("## 二、质量评分锚点")
    add("")
    add("测试中的主观判定统一采用课程手册的 0—4 质量等级：")
    add("")
    add("| 分值 | 等级 | 判断锚点 |")
    add("|-----:|------|----------|")
    for value, name, anchor in QUALITY_ANCHORS:
        add(f"| {value} | {name} | {anchor} |")
    add("")
    add("自动化校验项的输出为「通过／未通过」，不参与 0—4 打分；0—4 分仅用于")
    add("《附录A》中 F3 评审流程对项目材料的评价结果。")
    add("")

    # ── 结果汇总 ──────────────────────────────────────────────
    add("## 三、结果汇总")
    add("")
    add(f"本次共执行统一测试集 U1—U6（{len(unified)} 个用例）与组内回归测试"
        f"（{len(custom)} 个用例），合计 **{s.get('total', 0)}** 项校验，"
        f"通过 **{s.get('passed', 0)}** 项，通过率 **{s.get('pass_rate', 0) * 100:.1f}%**，"
        f"耗时 {s.get('duration_sec', '-')} 秒。")
    add("")
    add("| 用例 | 名称 | 通过/总数 | 结果 |")
    add("|------|------|-----------|------|")
    for r in data["results"]:
        ok = (not r.get("error")) and r["passed"] == r["total"] and r["total"] > 0
        add(f"| {r['id']} | {r['name']} | {r['passed']}/{r['total']} | {'通过' if ok else '**未通过**'} |")
    add("")

    # ── 统一测试集 ────────────────────────────────────────────
    add("## 四、统一测试集 U1—U6 逐项结果")
    add("")
    add("> 测试输入取自课程手册附录B，**逐字照抄，未做任何删减**。")
    add("> 原始输入被完整保留在 `tests/common/unified.py` 中，冻结后不得修改。")
    add("")
    for r in unified:
        add(f"### {r['id']}　{r['name']}")
        add("")
        add(f"**观察重点**：{r['focus']}")
        add("")
        if r.get("error"):
            add(f"> ⚠️ 运行出错：{r['error']}")
            add("")
            continue
        add("| 校验项 | 结果 | 证据 |")
        add("|--------|------|------|")
        for c in r["checks"]:
            mark = "通过" if c["passed"] else "**未通过**"
            detail = str(c.get("detail", "")).replace("|", "\\|").replace("\n", " ")[:90]
            add(f"| {c['name']} | {mark} | {detail} |")
        add("")

    # ── 组内测试 ──────────────────────────────────────────────
    add("## 五、组内回归测试逐项结果")
    add("")
    add("> 组内用例对应第二阶段**优化契约**中的问题编号，用于证明「承诺问题已修复」。")
    add("> 每条用例标明它回归的是哪一个已修复缺陷。")
    add("")
    for r in custom:
        add(f"### {r['id']}　{r['name']}")
        add("")
        add(f"**回归目标**：{r['focus']}")
        add("")
        if r.get("error"):
            add(f"> ⚠️ 运行出错：{r['error']}")
            add("")
            continue
        add("| 校验项 | 结果 | 证据 |")
        add("|--------|------|------|")
        for c in r["checks"]:
            mark = "通过" if c["passed"] else "**未通过**"
            detail = str(c.get("detail", "")).replace("|", "\\|").replace("\n", " ")[:90]
            add(f"| {c['name']} | {mark} | {detail} |")
        add("")

    # ── 关键回归对照 ──────────────────────────────────────────
    add("## 六、关键回归对照（修复前 → 修复后）")
    add("")
    add("| 缺陷 | 修复前表现 | 修复后表现 | 对应用例 |")
    add("|------|-----------|-----------|----------|")
    add("| 无来源陈述被判定为「事实 F」 | 「学校支持建立教材交易平台」判为 F，"
        "`can_use_now=是` | 判为 I（待核验），并给出核验动作 | U2、C-E01 |")
    add("| 评审对无证据项目虚高打分 | U5 输入得 **87/100**，证据缺口为空 | "
        "同一输入得 **23.8/100**，等级 1（严重缺陷），证据缺口 15 条 | U5、C-E04 |")
    add("| 关键词匹配对否定式失效 | 「无来源」因含「来源」被当作存在证据 | "
        "否定感知生效，「没有调研」不再产生证据命中 | U2、C-E03 |")
    add("| 降级后仍记为 success | LLM 失败后运行状态仍为 `success`，`next_task` 为空 | "
        "状态记为 `degraded`，原因可读，`next_task` 完整 | U6、C-X-01 |")
    add("| 日志字段缺失 | 仅有 run_id / flow | 补全身份、时间、状态、行为、人机边界五组字段 | C-L-01 |")
    add("")

    # ── 未通过项 ──────────────────────────────────────────────
    add("## 七、未通过项与待改进清单")
    add("")
    add("> 手册明确要求**不得删除失败样本**。以下清单如实保留本次运行的全部未通过项。")
    add("")
    if failed or errors:
        if failed:
            add("| 用例 | 用例名称 | 未通过校验项 | 证据 |")
            add("|------|----------|--------------|------|")
            for tid, tname, cname, detail in failed:
                add(f"| {tid} | {tname} | {cname} | {str(detail).replace('|', chr(92) + '|')[:70]} |")
            add("")
        if errors:
            add("**运行出错项**：")
            add("")
            for tid, tname, err in errors:
                add(f"- `{tid}` {tname}：{err}")
            add("")
    else:
        add("本次运行**无未通过项**。")
        add("")
        add("> ⚠️ 但这**不等于系统没有问题**。自测只能证明「已定义的校验项通过」，")
        add("> 无法覆盖未预想到的失败模式——用例由开发者自己设计，存在自证偏差。")
        add("> 因此本报告的全部结论仅在「已定义的校验项」范围内成立。")
        add("")

    # ── 局限 ──────────────────────────────────────────────────
    add("## 八、本次测试的局限（诚实声明）")
    add("")
    add("1. **存在自证偏差**。全部用例均由开发者自行设计，容易只覆盖自己预想到的问题；"
        "覆盖范围之外的行为未经检验。")
    add("2. **LLM 路径未被充分覆盖**。测试时 DeepSeek API 返回 402（Insufficient Balance），")
    add("   因此 F2 项目指导始终运行在本地确定性降级模式下。LLM 主路径的行为**未经验证**。")
    add("3. **F1/F3 为确定性引擎**，其输出不随采样变化，因此重复运行结果的方差极小，")
    add("   但这**不代表**在更广泛输入上的稳定性已被证明。")
    add("4. **测试输入规模有限**。统一测试集仅 6 个用例，组内测试 13 个用例，"
        "覆盖的是已识别的问题，不能代表全部失败模式。")
    add("5. **未进行真实用户测试**。课程不要求真实调研，本报告中的所有用户相关判断")
    add("   均为假设，不得作为市场证据使用。")
    add("")

    add("---")
    add("")
    add(f"*本报告由 `deliverables/build/generate_selftest.py` 依据原始测试结果自动生成，"
        f"生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M')}。*")
    add("")
    add("*原始结果未经任何筛选，全部保留在 `tests/reports/` 目录下。*")

    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=None, help="指定测试结果 JSON；默认取最新一份")
    args = parser.parse_args()

    path = args.report or latest_report()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(render(data, path))

    print(f"已生成：{OUT_PATH}")
    print(f"数据来源：{path}")
    print(f"结果：{data['summary']['passed']}/{data['summary']['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
