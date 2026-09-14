# -*- coding: utf-8 -*-
"""
生成《01_验收PPT》交付文档。

设计约定（依据数据可视化规范）：
- 幻灯片底色 #fcfcfb；文字用文本色，不用系列色
- 分类色板仅取前两槽：蓝 #2a78d6（已修复）、橙 #eb6834（延期）
  该两色已通过校验器检查（浅色底：亮度带 / 色度下限 / 色盲分离 ΔE 24.7 /
  常视分离 ΔE 33.6 / 对比度 ≥3:1 全部通过）
- 仅 1 张真正的图表（缺陷处置）；其余用「数字块」而非图表——
  两个数值的「前/后」对比做成条形图会被误读成「越短越好」，
  因此改用数字块并显式写明方向。
- ≥2 个系列必带图例，并同时直接标注数值，识别不依赖颜色单一通道。

用法：python deliverables/build/generate_pptx.py
"""
from __future__ import annotations

import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(_ROOT, "deliverables", "01_验收PPT.pptx")

# ── 设计令牌 ──────────────────────────────────────────────────────
SURFACE = RGBColor(0xFC, 0xFC, 0xFB)
INK = RGBColor(0x0B, 0x0B, 0x0B)          # 文本主色
INK_2 = RGBColor(0x52, 0x51, 0x4E)        # 文本次色
INK_3 = RGBColor(0x8A, 0x89, 0x85)        # 弱化文本
RULE = RGBColor(0xDE, 0xDD, 0xD8)         # 分隔线 / 网格
SERIES_1 = RGBColor(0x2A, 0x78, 0xD6)     # 已修复（蓝）
SERIES_2 = RGBColor(0xEB, 0x68, 0x34)     # 延期（橙）
PANEL = RGBColor(0xF3, 0xF3, 0xF0)        # 浅面板
WARN_BG = RGBColor(0xFD, 0xF1, 0xE8)      # 提示底色（与橙同族，仅作背景）

FONT = "微软雅黑"
W, H = Inches(13.333), Inches(7.5)


def set_font(run, size: int, bold: bool = False, color=INK, font: str = FONT) -> None:
    """设置字体，同时写入 latin 与东亚字形，避免中文回退成宋体。"""
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        el = rPr.find(f"{{http://schemas.openxmlformats.org/drawingml/2006/main}}{tag.split(':')[1]}")
        if el is None:
            from lxml import etree

            el = etree.SubElement(
                rPr, f"{{http://schemas.openxmlformats.org/drawingml/2006/main}}{tag.split(':')[1]}"
            )
        el.set("typeface", font)


def textbox(slide, l, t, w, h, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return box, tf


def para(tf, text, size, bold=False, color=INK, align=PP_ALIGN.LEFT,
         space_before=0, space_after=4, first=False, line=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    if line:
        p.line_spacing = line
    run = p.add_run()
    run.text = text
    set_font(run, size, bold, color)
    return p


def rect(slide, l, t, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE, radius=None):
    s = slide.shapes.add_shape(shape, l, t, w, h)
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    s.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    return s


def blank(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    rect(slide, 0, 0, W, H, SURFACE)
    return slide


def header(slide, title, kicker=None):
    """统一页眉：小标签 + 标题 + 细分隔线。"""
    if kicker:
        _, tf = textbox(slide, Inches(0.7), Inches(0.42), Inches(11), Inches(0.3))
        para(tf, kicker, 11, True, INK_3, first=True, space_after=0)
    _, tf = textbox(slide, Inches(0.7), Inches(0.72), Inches(11.9), Inches(0.6))
    para(tf, title, 25, True, INK, first=True, space_after=0)
    rect(slide, Inches(0.7), Inches(1.42), Inches(11.93), Emu(9525), RULE)


def footer(slide, text):
    _, tf = textbox(slide, Inches(0.7), Inches(6.95), Inches(11.9), Inches(0.3))
    para(tf, text, 10, False, INK_3, first=True, space_after=0)


def stat_tile(slide, l, t, w, h, value, label, note="", accent=SERIES_1):
    """数字块：单一头条数字用数字块而不是图表。"""
    rect(slide, l, t, w, h, PANEL)
    rect(slide, l, t, Emu(45720), h, accent)  # 左侧色条，非数据编码
    _, tf = textbox(slide, l + Inches(0.28), t + Inches(0.18), w - Inches(0.45), h - Inches(0.3))
    para(tf, value, 34, True, INK, first=True, space_after=2)
    para(tf, label, 12, True, INK_2, space_after=2)
    if note:
        para(tf, note, 10, False, INK_3, space_after=0, line=1.15)


def grouped_bars(slide, l, t, w, h, categories, series, max_val):
    """
    分组条形图（唯一的真实图表）。

    categories: [(标签, [v1, v2]), ...]
    series:     [(系列名, 颜色), ...]
    规范：细条、2px 底色间隙、直接标注数值、网格弱化、带图例。
    """
    plot_l = l + Inches(0.95)          # 给左侧类别标签留位
    plot_w = w - Inches(0.95)
    plot_t = t + Inches(0.42)          # 给图例留位
    plot_h = h - Inches(0.42)

    # 网格线（弱化）：4 条
    for i in range(5):
        y = plot_t + Emu(int(plot_h * i / 4))
        rect(slide, plot_l, y, plot_w, Emu(9525), RULE)
    # 基线刻度
    _, tf = textbox(slide, plot_l, plot_t + plot_h + Inches(0.04), plot_w, Inches(0.25))
    para(tf, f"0　　　　　　　　（单位：项）　　　　　　　　　{max_val}", 9, False, INK_3, first=True, space_after=0)

    row_h = Emu(int(plot_h / len(categories)))
    bar_h = Emu(int(row_h * 0.24))       # 细条
    gap = Emu(15240)                     # 2px 底色间隙

    for ci, (cat, values) in enumerate(categories):
        cy = plot_t + Emu(int(row_h * ci)) + Emu(int(row_h * 0.16))
        # 类别标签
        _, tf = textbox(slide, l, cy + Emu(int(bar_h * 0.2)), Inches(0.85), Inches(0.3))
        para(tf, cat, 12, True, INK_2, first=True, space_after=0)
        for si, (sname, color) in enumerate(series):
            v = values[si]
            bw = Emu(int(plot_w * (v / max_val))) if max_val else Emu(0)
            by = cy + Emu(int((bar_h + gap) * si))
            if v > 0:
                rect(slide, plot_l, by, bw, bar_h, color,
                     shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.35)
            # 直接标注数值——识别不依赖颜色。
            # 零值用弱化色：长度为 0 的条没有视觉锚点，深色数字容易被误读成上一根条的值。
            _, tf = textbox(slide, plot_l + bw + Inches(0.08), by - Emu(int(bar_h * 0.1)),
                            Inches(0.8), Inches(0.3))
            para(tf, str(v), 12, v > 0, INK if v > 0 else INK_3, first=True, space_after=0)

    # 图例（≥2 系列必须有）
    lx = l
    for sname, color in series:
        rect(slide, lx, t + Inches(0.08), Inches(0.13), Inches(0.13), color)
        _, tf = textbox(slide, lx + Inches(0.2), t + Inches(0.02), Inches(1.6), Inches(0.28))
        para(tf, sname, 11, True, INK_2, first=True, space_after=0)
        lx += Inches(1.5)


def build() -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # ── 1 封面 ────────────────────────────────────────────────────
    s = blank(prs)
    rect(s, Inches(0.7), Inches(2.05), Inches(1.4), Emu(38100), SERIES_1)
    _, tf = textbox(s, Inches(0.7), Inches(2.35), Inches(11), Inches(1.0))
    para(tf, "食刻准", 44, True, INK, first=True, space_after=6)
    para(tf, "社区老年助餐的需求预测与营养约束备餐辅助系统", 18, False, INK_2, space_after=0)
    _, tf = textbox(s, Inches(0.7), Inches(4.0), Inches(11.5), Inches(1.4))
    para(tf, "验收汇报　|　大创项目成果 ＋ Agent 优化效果", 14, True, INK_2, first=True, space_after=10)
    para(tf, "Agent：双创智能教练 V2.1.0　·　方向：社会治理和公共服务", 12, False, INK_3, space_after=0)
    footer(s, "全部结论标注证据类型：F 事实 / I 推断 / H 假设 / S 模拟")

    # ── 2 一句话 ──────────────────────────────────────────────────
    s = blank(prs)
    header(s, "我们要解决的问题", "项目定位")
    _, tf = textbox(s, Inches(0.7), Inches(1.75), Inches(5.6), Inches(3.4))
    para(tf, "问题", 13, True, INK_3, first=True, space_after=8)
    para(tf, "社区助餐点的经营者无法预知明天有多少老人来吃饭，只能凭经验备餐——"
             "备多了浪费、备少了老人吃不上。", 16, True, INK, space_after=14, line=1.35)
    para(tf, "而最需要助餐的高龄独居老人，恰恰是最不会用手机预订的那群人。",
         14, False, INK_2, space_after=0, line=1.35)
    _, tf = textbox(s, Inches(7.1), Inches(1.75), Inches(5.5), Inches(3.4))
    para(tf, "方案", 13, True, INK_3, first=True, space_after=8)
    para(tf, "用历史就餐规律与助餐点登记信息做次日需求预测，并叠加慢病营养约束，"
             "向经营者输出一张「明日备餐建议单」。", 16, True, INK, space_after=14, line=1.35)
    para(tf, "把凭经验的备餐，变成可解释、可复核、可追溯的定量决策。",
         14, False, INK_2, space_after=0, line=1.35)
    rect(s, Inches(6.75), Inches(1.9), Emu(9525), Inches(3.1), RULE)
    footer(s, "服务对象：助餐点经营者（B端）　｜　明确不服务：不面向老人做App、不做送餐履约、不做医疗建议")

    # ── 3 用户与场景 ──────────────────────────────────────────────
    s = blank(prs)
    header(s, "谁在什么场景下遇到什么问题", "用户与场景")
    rows = [
        ("角色", "社区助餐点经营者／后厨负责人，通常同时负责采购与排班"),
        ("任务", "每天决定次日采购多少食材、做多少份餐"),
        ("情境", "前一天下午下单采购，次日上午备餐；就餐人数受天气、季节、身体状况影响"),
        ("障碍", "没有任何可靠的次日需求信息；老人不预订，现有微信群接龙覆盖不到不会用手机的高龄老人"),
        ("后果", "备多了食材浪费、成本上升；备少了老人吃不上、口碑受损——两者同时发生"),
    ]
    y = Inches(1.75)
    for k, v in rows:
        _, tf = textbox(s, Inches(0.7), y, Inches(1.3), Inches(0.5))
        para(tf, k, 14, True, SERIES_1, first=True, space_after=0)
        _, tf = textbox(s, Inches(2.1), y, Inches(10.5), Inches(0.72))
        para(tf, v, 14, False, INK, first=True, space_after=0, line=1.3)
        y += Inches(0.85)
    _, tf = textbox(s, Inches(0.7), Inches(6.35), Inches(11.9), Inches(0.5))
    para(tf, "不适用场景：已实行全预订制且人数稳定的助餐点／服务对象都会用智能手机的社区／日就餐不足10人的极小点位",
         11, False, INK_3, first=True, space_after=0)

    # ── 4 问题依据 ────────────────────────────────────────────────
    s = blank(prs)
    header(s, "问题依据与证据边界", "证据分层")
    _, tf = textbox(s, Inches(0.7), Inches(1.7), Inches(5.6), Inches(4.4))
    para(tf, "A 级 · 权威公开来源（支撑人口规模与政策要求）", 13, True, INK, first=True, space_after=8)
    para(tf, "民政部《2023年民政事业发展统计公报》", 12, True, INK_2, space_after=2)
    para(tf, "全国60周岁及以上老年人口 29697 万人，占总人口 21.1%", 12, False, INK, space_after=10)
    para(tf, "民政部等11部门《积极发展老年助餐服务行动方案》（民发〔2023〕58号）", 12, True, INK_2, space_after=2)
    para(tf, "明确两阶段目标，要求到2026年底「多元供给格局基本形成，可持续发展能力得到巩固」",
         12, False, INK, space_after=0)
    _, tf = textbox(s, Inches(7.1), Inches(1.7), Inches(5.5), Inches(4.4))
    para(tf, "B 级 · 媒体报道（支撑「备餐浪费」这一具体判断）", 13, True, INK, first=True, space_after=8)
    para(tf, "中国农业大学团队调研（经媒体转述）", 12, True, INK_2, space_after=2)
    para(tf, "客流波动大 → 经营者难以确定备餐量 → 备餐不足或食材浪费", 12, False, INK, space_after=10)
    para(tf, "其余：国家统计局北京调查总队40家调研、青岛985处助餐机构数据、重庆单店账本等",
         12, False, INK, space_after=0)
    rect(s, Inches(0.7), Inches(6.05), Inches(11.93), Inches(0.78), WARN_BG)
    _, tf = textbox(s, Inches(0.95), Inches(6.18), Inches(11.5), Inches(0.6))
    para(tf, "⚠ 最重要的证据缺口：A级来源只支撑人口规模与政策要求，不支撑「备餐浪费严重」这一具体结论——"
             "后者目前仅有 B 级支撑，且所有比例数字均为媒体转述，未取得原始统计口径。",
         11, True, INK, first=True, space_after=0, line=1.25)

    # ── 5 现有做法 ────────────────────────────────────────────────
    s = blank(prs)
    header(s, "现有做法与它的不足", "替代方案分析")
    data = [
        ("替代方案", "优点", "不足"),
        ("微信群接龙预订", "显著提高备餐准确度，成本极低", "只覆盖会用智能手机的老人；依赖提前一天决定"),
        ("经营者经验估量", "无需额外工具", "无法应对天气、季节、临时事件带来的波动"),
        ("政府统一定量配餐", "规模效应、管理简单", "灵活性差，易造成区域整体供给过剩"),
        ("不使用任何产品", "无学习成本", "浪费与缺餐同时存在，在亏损点位上放大存亡风险"),
    ]
    tb = s.shapes.add_table(len(data), 3, Inches(0.7), Inches(1.75), Inches(11.93), Inches(3.5)).table
    tb.columns[0].width = Inches(2.6)
    tb.columns[1].width = Inches(4.0)
    tb.columns[2].width = Inches(5.33)
    for ri, row in enumerate(data):
        for ci, val in enumerate(row):
            cell = tb.cell(ri, ci)
            cell.text = ""
            cell.fill.solid()
            cell.fill.fore_color.rgb = SURFACE if ri == 0 else PANEL
            cell.margin_left = cell.margin_right = Inches(0.1)
            p = cell.text_frame.paragraphs[0]
            r = p.add_run()
            r.text = val
            set_font(r, 12, ri == 0, INK if ri == 0 else INK_2)
    rect(s, Inches(0.7), Inches(5.6), Inches(11.93), Inches(1.05), PANEL)
    _, tf = textbox(s, Inches(0.95), Inches(5.74), Inches(11.5), Inches(0.85))
    para(tf, "必须承认：微信群接龙预订已经解决了「愿意预订群体」的备餐准确性问题。",
         13, True, INK, first=True, space_after=4)
    para(tf, "本项目的创新不在于「我们也做预订」，而在于覆盖接龙预订覆盖不到的人。",
         12, False, INK_2, space_after=0)

    # ── 6 核心机制 ────────────────────────────────────────────────
    s = blank(prs)
    header(s, "方案的核心机制", "解决方案")
    steps = [
        ("历史就餐台账", "人数、菜品、实耗食材"),
        ("需求预测引擎", "历史规律 + 星期效应 + 天气/节假日修正"),
        ("慢病营养约束", "份数与菜品结构的联合决策"),
        ("明日备餐建议单", "经营者可调整，调整被记录"),
        ("实际数据回流", "回算误差，修正模型"),
    ]
    y = Inches(1.8)
    for i, (title, desc) in enumerate(steps):
        rect(s, Inches(0.7), y, Inches(3.5), Inches(0.72), PANEL)
        rect(s, Inches(0.7), y, Emu(45720), Inches(0.72), SERIES_1)
        _, tf = textbox(s, Inches(0.95), y + Inches(0.11), Inches(3.2), Inches(0.55))
        para(tf, title, 13, True, INK, first=True, space_after=1)
        para(tf, desc, 10, False, INK_2, space_after=0)
        if i < len(steps) - 1:
            _, tf = textbox(s, Inches(4.35), y + Inches(0.18), Inches(0.4), Inches(0.4))
            para(tf, "→", 16, True, INK_3, first=True, space_after=0)
        y += Inches(0.92)
    _, tf = textbox(s, Inches(5.4), Inches(1.8), Inches(7.2), Inches(4.2))
    para(tf, "三个关键设计", 14, True, INK, first=True, space_after=10)
    para(tf, "① 老人端零操作", 13, True, SERIES_1, space_after=3)
    para(tf, "预测能力放在经营者一侧，不要求老年人使用任何数字工具，"
             "从而覆盖数字能力最弱的高龄、独居老人。", 12, False, INK_2, space_after=12, line=1.3)
    para(tf, "② 份数与菜品结构联合决策", 13, True, SERIES_1, space_after=3)
    para(tf, "慢病营养约束会反过来限制可行的份数区间。把「做多少」和「做什么」"
             "分开决策，备餐计划在菜品层面无法执行。", 12, False, INK_2, space_after=12, line=1.3)
    para(tf, "③ 输出建议值而非配额", 13, True, SERIES_1, space_after=3)
    para(tf, "保留经营者调整权并记录调整，系统不替代人的判断，避免被用于削减老人餐食供应。",
         12, False, INK_2, space_after=0, line=1.3)

    # ── 7 创新点 ──────────────────────────────────────────────────
    s = blank(prs)
    header(s, "去掉所有技术名词之后，还剩什么", "创新性")
    _, tf = textbox(s, Inches(0.7), Inches(1.7), Inches(11.9), Inches(0.8))
    para(tf, "需求预测与慢病营养约束的组合机制 —— 二者都是可独立成立的方法，不依赖任何大模型。",
         16, True, INK, first=True, space_after=0, line=1.3)
    cols = [
        ("新机制", "需求预测与营养约束的耦合决策"),
        ("新组合", "统计预测方法 + 营养约束规则 + 社区供餐场景"),
        ("新场景", "预测能力放在经营者侧，规避数字鸿沟"),
        ("新效率", "降低食材浪费率、减少缺餐，均可测量"),
    ]
    x = Inches(0.7)
    for title, desc in cols:
        rect(s, x, Inches(2.85), Inches(2.86), Inches(1.85), PANEL)
        _, tf = textbox(s, x + Inches(0.25), Inches(3.1), Inches(2.4), Inches(1.4))
        para(tf, title, 15, True, SERIES_1, first=True, space_after=6)
        para(tf, desc, 12, False, INK_2, space_after=0, line=1.3)
        x += Inches(3.03)
    rect(s, Inches(0.7), Inches(5.05), Inches(11.93), Inches(1.35), WARN_BG)
    _, tf = textbox(s, Inches(0.95), Inches(5.2), Inches(11.5), Inches(1.1))
    para(tf, "我们不主张的部分", 13, True, INK, first=True, space_after=5)
    para(tf, "不含技术发明，不主张技术领先；AI 只承担台账录入与建议理由生成等体验层工作，不是价值层；"
             "本阶段未开展真实试点，所有浪费率下降幅度均为假设 H。", 12, False, INK_2, space_after=0, line=1.3)

    # ── 8 关键证据：修复前 vs 修复后（数字块，不是图表）────────────
    s = blank(prs)
    header(s, "Agent 最严重缺陷的修复效果", "Agent 优化效果 · 关键证据")
    _, tf = textbox(s, Inches(0.7), Inches(1.65), Inches(11.9), Inches(0.6))
    para(tf, "测试输入：U5 项目评审材料（明确写明「无来源」「创新点是使用AI」「盈利依靠广告」）"
             "——正确行为应当是给出低分并指出证据缺口。", 12, False, INK_2, first=True, space_after=0, line=1.3)
    stat_tile(s, Inches(0.7), Inches(2.35), Inches(3.7), Inches(2.15),
              "87 / 100", "修复前给出的分数",
              "证据缺口：0 条\n错误地认可了这个项目", SERIES_2)
    stat_tile(s, Inches(4.65), Inches(2.35), Inches(3.7), Inches(2.15),
              "23.8 / 100", "修复后给出的分数",
              "证据缺口：15 条\n质量等级 1（严重缺陷）", SERIES_1)
    stat_tile(s, Inches(8.6), Inches(2.35), Inches(4.03), Inches(2.15),
              "2 条", "主动提示的诚信风险",
              "无来源数字 · 把「使用AI」当作创新点", SERIES_1)
    rect(s, Inches(0.7), Inches(4.85), Inches(11.93), Inches(1.72), PANEL)
    _, tf = textbox(s, Inches(0.95), Inches(5.02), Inches(11.45), Inches(1.45))
    para(tf, "修复前的根因：关键词匹配对否定式失效", 13, True, INK, first=True, space_after=6)
    para(tf, "输入里「无来源」三个字包含「来源」，于是系统判定「该项目提供了来源」。"
             "同一逻辑让「创新点是使用AI」通过了创新维度。", 12, False, INK_2, space_after=10, line=1.3)
    para(tf, "修复方式：证据门槛约束评分", 13, True, INK, space_after=6)
    para(tf, "全篇没有可定位来源时，任何维度不得超过满分的 40%；创新点若只落在技术采用上，"
             "创新维度不得超过 30%。", 12, False, INK_2, space_after=0, line=1.3)

    # ── 9 缺陷处置（唯一的图表）───────────────────────────────────
    s = blank(prs)
    header(s, "V1 → V2：缺陷识别与处置", "Agent 优化效果")
    _, tf = textbox(s, Inches(0.7), Inches(1.6), Inches(11.9), Inches(0.35))
    para(tf, "按严重度统计的缺陷数量与处置结果", 12, False, INK_2, first=True, space_after=0)
    grouped_bars(
        s, Inches(0.7), Inches(2.15), Inches(7.4), Inches(3.6),
        [("P0 阻断", [3, 0]), ("P1 严重", [6, 0]), ("P2 一般", [3, 1])],
        [("已修复", SERIES_1), ("延期", SERIES_2)],
        max_val=6,
    )
    _, tf = textbox(s, Inches(8.5), Inches(2.3), Inches(4.13), Inches(3.6))
    para(tf, "读法", 13, True, INK, first=True, space_after=8)
    para(tf, "3 项 P0 阻断与 6 项 P1 严重缺陷全部修复；", 12, False, INK_2, space_after=4, line=1.3)
    para(tf, "4 项 P2 一般缺陷中修复 3 项，", 12, False, INK_2, space_after=4, line=1.3)
    para(tf, "1 项明确延期（F1/F3 会话归属），", 12, False, INK_2, space_after=4, line=1.3)
    para(tf, "已在迭代文档中说明理由与风险。", 12, False, INK_2, space_after=14, line=1.3)
    para(tf, "AI 与人工的边界", 13, True, INK, space_after=8)
    para(tf, "缺陷由项目组在真实使用中识别，修复方案由项目组确定；"
             "Agent 用于辅助生成测试用例与文档草稿，最终判断与核验由成员负责。",
         11, False, INK_3, space_after=0, line=1.3)
    footer(s, "数据来源：04_智能体迭代开发文档　·　全部原始记录保留在 tests/reports/ 与 logs/runs.jsonl")

    # ── 10 自测试结果 ─────────────────────────────────────────────
    s = blank(prs)
    header(s, "自测试结果", "Agent 质量证据")
    stat_tile(s, Inches(0.7), Inches(1.75), Inches(3.7), Inches(1.9),
              "77 / 77", "全部校验项通过", "统一测试集 U1—U6：35 项校验\n组内回归 13 例：42 项校验", SERIES_1)
    _, tf = textbox(s, Inches(4.75), Inches(1.85), Inches(7.9), Inches(1.8))
    para(tf, "测试集构成", 13, True, INK, first=True, space_after=8)
    para(tf, "U1—U6 统一测试集：输入逐字取自课程手册附录B，冻结后不得修改，用于组间可比。",
         12, False, INK_2, space_after=5, line=1.3)
    para(tf, "组内回归测试 13 例：每条对应优化契约中的一个已修复缺陷，用于证明「承诺问题已修复」。",
         12, False, INK_2, space_after=5, line=1.3)
    para(tf, "异常测试覆盖：不支持的文件类型、文件无法解析、会话不存在、输入超长、评审输入过短、学习问题为空。",
         12, False, INK_2, space_after=0, line=1.3)
    rect(s, Inches(0.7), Inches(3.95), Inches(11.93), Inches(1.55), WARN_BG)
    _, tf = textbox(s, Inches(0.95), Inches(4.1), Inches(11.5), Inches(1.3))
    para(tf, "这份成绩不能说明系统没有问题", 13, True, INK, first=True, space_after=6)
    para(tf, "① 存在自证偏差，全部用例由开发者自行设计，只覆盖已识别的问题；"
             "② 测试期间大模型服务余额不足，F2 始终运行在降级模式，大模型主路径未被验证；"
             "③ 测试输入规模有限。以上局限已如实写入自测试报告。",
         12, False, INK_2, space_after=0, line=1.3)

    # ── 11 发展与风险 ─────────────────────────────────────────────
    s = blank(prs)
    header(s, "能否持续：收入逻辑与风险边界", "发展前景")
    _, tf = textbox(s, Inches(0.7), Inches(1.85), Inches(5.7), Inches(4.4))
    para(tf, "单位经济测算（单个助餐点，全部为假设）", 13, True, INK, first=True, space_after=12)
    for k, v in [("日均就餐", "100 人次（H）"), ("单份食材成本", "8 元（H）"),
                 ("当前浪费率", "10%（H）"), ("目标浪费率", "5%（H）"),
                 ("月节约", "约 1200 元"), ("按 30% 分成", "单点月收入约 360 元")]:
        p = tf.add_paragraph()
        p.space_after = Pt(7)
        r1 = p.add_run(); r1.text = f"{k}　"
        set_font(r1, 13, False, INK_2)
        r2 = p.add_run(); r2.text = v
        set_font(r2, 13, True, INK)
    para(tf, "诚实的判断：单点年收入约 4320 元，客单价很低。要形成可持续业务必须做到相当规模，"
             "或转向街道／民政侧的付费模式。这是本商业模式最大的弱点。",
         12, False, SERIES_2, space_before=10, space_after=0, line=1.35)
    _, tf = textbox(s, Inches(6.9), Inches(1.85), Inches(5.7), Inches(4.4))
    para(tf, "主要风险与应对", 13, True, INK, first=True, space_after=12)
    for k, v in [("市场风险（高）", "助餐点普遍亏损、付费能力弱 → 按节约分成共担风险"),
                 ("需求假设风险（高）", "H-17 若不成立则痛点削弱 → 列为最高优先级验证"),
                 ("技术风险（中）", "预测精度不足 → 先用历史台账做回溯测试再投入开发"),
                 ("数据合规（高）", "涉老人健康与就餐信息 → 只处理去标识化聚合数据，营养约束以人群比例为单位"),
                 ("伦理风险（中）", "预测被用于削减供应 → 输出建议值而非配额，保留并记录调整")]:
        p = tf.add_paragraph()
        p.space_after = Pt(10)
        p.line_spacing = 1.3
        r1 = p.add_run(); r1.text = f"{k}："
        set_font(r1, 12.5, True, INK)
        r2 = p.add_run(); r2.text = v
        set_font(r2, 12, False, INK_2)
    footer(s, "全部数字均为假设 H，本阶段未开展真实试点，不作为已实现效果陈述")

    # ── 12 下一步 ─────────────────────────────────────────────────
    s = blank(prs)
    header(s, "局限与下一步", "收尾")
    _, tf = textbox(s, Inches(0.7), Inches(1.72), Inches(5.7), Inches(4.3))
    para(tf, "必须承认的局限", 13, True, INK, first=True, space_after=10)
    for t in ["自测存在自证偏差，只覆盖开发者已识别的问题",
              "大模型主路径因余额不足未经验证，验证的是降级路径",
              "F1/F3 无会话归属，教师端看不到这两个流程的使用记录",
              "大创项目的核心问题判断目前只有 B 级证据支撑",
              "营养约束仅有概念设计，缺营养学专业能力",
              "商业模式偏弱，第一年悲观情景下明确亏损"]:
        p = tf.add_paragraph()
        p.space_after = Pt(6)
        p.line_spacing = 1.25
        r = p.add_run(); r.text = "· " + t
        set_font(r, 12, False, INK_2)
    _, tf = textbox(s, Inches(6.9), Inches(1.72), Inches(5.7), Inches(4.3))
    para(tf, "下一步（按优先级）", 13, True, INK, first=True, space_after=10)
    for i, t in enumerate(["扩大测试输入范围，降低自证偏差",
                           "用助餐点历史台账做需求预测回溯测试，验证核心机制",
                           "实地观察 2—3 天，验证最危险的假设 H-17",
                           "补齐 F1/F3 会话归属",
                           "联系营养师顾问，推进营养约束规则设计",
                           "大模型额度恢复后补测 F2 主路径"], 1):
        p = tf.add_paragraph()
        p.space_after = Pt(6)
        p.line_spacing = 1.25
        r1 = p.add_run(); r1.text = f"{i}. "
        set_font(r1, 12, True, SERIES_1)
        r2 = p.add_run(); r2.text = t
        set_font(r2, 12, False, INK_2)
    rect(s, Inches(0.7), Inches(6.15), Inches(11.93), Inches(0.72), PANEL)
    _, tf = textbox(s, Inches(0.95), Inches(6.28), Inches(11.5), Inches(0.5))
    para(tf, "这门课真正训练我们的，是区分「看起来对」和「有证据」——"
             "一个系统输出流畅、结构完整，和它说的东西有依据，是完全不同的两件事。",
         12, True, INK, first=True, space_after=0, line=1.25)

    # ── 13 备查（附录）────────────────────────────────────────────
    s = blank(prs)
    header(s, "备查：交付物与证据索引", "附录")
    items = [
        ("02 源代码", "完整仓库；三个流程 + 证据引擎 + 测试集"),
        ("03 创新性项目开发文档", "证据台账、决策矩阵、商业逻辑、风险"),
        ("04 智能体迭代开发文档", "优化契约、13 项缺陷、V1/V2 对比方法"),
        ("05 创新性说明", "三项创新、与替代方案的实质差异、诚实边界"),
        ("06 自测试报告", "77/77 结果、未通过项、测试局限"),
        ("07 用户手册", "安装、启动、三个流程、故障排查"),
        ("08 小组总结 / 09 个人总结", "过程复盘与个人贡献"),
    ]
    y = Inches(1.8)
    for a, b in items:
        _, tf = textbox(s, Inches(0.7), y, Inches(4.3), Inches(0.45))
        para(tf, a, 12, True, INK, first=True, space_after=0)
        _, tf = textbox(s, Inches(5.2), y, Inches(7.4), Inches(0.45))
        para(tf, b, 12, False, INK_2, first=True, space_after=0)
        y += Inches(0.52)
    rect(s, Inches(0.7), Inches(5.72), Inches(11.93), Inches(1.0), PANEL)
    _, tf = textbox(s, Inches(0.95), Inches(5.88), Inches(11.5), Inches(0.8))
    para(tf, "可复现性：Agent 版本 2.1.0 ｜ 版本快照接口 GET /api/version ｜ "
             "运行记录 logs/runs.jsonl ｜ 测试报告 tests/reports/",
         11, False, INK_2, first=True, space_after=4, line=1.3)
    para(tf, "所有原始对话、失败记录与人工干预均已保留，未做筛选。", 11, False, INK_3, space_after=0)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    prs.save(OUT)
    print(f"已生成：{OUT}")
    print(f"页数：{len(prs.slides.__iter__.__self__._sldIdLst)}")


if __name__ == "__main__":
    build()
