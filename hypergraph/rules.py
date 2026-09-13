"""
H1-H20+ 逻辑审计规则库（V2 升级版）
按照 V1 文档规范，采用完整 JSON 格式，包含 type / nodes / constraint / impact / fix_task
"""
from typing import Dict, Any

RULES: Dict[str, Dict[str, Any]] = {
    "H1": {
        "name": "客户-价值主张错位",
        "type": "BusinessModelConsistency",
        "description": "目标客户群体与产品价值主张存在根本性错配，客户不认可该价值",
        "nodes": {"customer": "Concept", "value_proposition": "Concept", "channel": "Concept"},
        "constraint": "value_proposition.must_solve(customer.pain_point)",
        "check_hint": "客户真实的最大痛点是什么？你的产品解决的是否正是这个痛点？",
        "severity": "high",
        "trigger_message": "Customer and value proposition are fundamentally misaligned.",
        "impact": "客户无购买动机，商业模式无法成立",
        "fix_task": "访谈 ≥5 位真实目标客户，记录其最高频痛点，与现有价值主张做对比验证",
        "teaching_topic": "客户价值主张与痛点匹配验证"
    },
    "H2": {
        "name": "渠道不可达",
        "type": "BusinessModelConsistency",
        "description": "所选获客渠道无法有效触达目标客群，导致获客在结构上失败",
        "nodes": {"customer": "Concept", "channel": "Concept"},
        "constraint": "channel.must_reach(customer)",
        "check_hint": "目标客户日常在哪里？你选择的渠道能否触达他们？有证据吗？",
        "severity": "high",
        "trigger_message": "The chosen channel cannot effectively reach the target customer.",
        "impact": "无论产品多好，客户无法被找到，获客成本无限高",
        "fix_task": "列出目标客户最高频的信息获取渠道（前3个），并验证你是否能在这些渠道投放",
        "teaching_topic": "渠道获客与用户触达策略"
    },
    "H3": {
        "name": "定价无支付意愿证据",
        "type": "CustomerMarketFit",
        "description": "定价基于成本或竞品对标，而非真实用户支付意愿验证，高估WTP",
        "nodes": {"pricing": "Metric", "customer": "Concept", "willingness_to_pay": "Metric"},
        "constraint": "pricing.must_be_validated_by(customer.willingness_to_pay)",
        "check_hint": "有多少真实用户在看到这个价格后表示愿意付款？用什么方式验证的？",
        "severity": "high",
        "trigger_message": "Pricing lacks evidence of customers' willingness to pay.",
        "impact": "上线后转化率极低，定价策略需要大幅调整",
        "fix_task": "设计 Landing Page 测试或报价访谈，获取 ≥30 份用户真实报价反馈",
        "teaching_topic": "基于客户价值的定价策略与支付意愿验证"
    },
    "H4": {
        "name": "TAM/SAM/SOM 口径混乱",
        "type": "MarketSizingError",
        "description": "市场规模使用宏观行业总量（TAM）代替可实际触达规模（SOM），制造数字幻觉",
        "nodes": {"market": "Market", "TAM": "Metric", "SAM": "Metric", "SOM": "Metric"},
        "constraint": "market_claim.must_use_SOM_not_TAM",
        "check_hint": "你引用的市场规模数字是全行业总量还是你真正能抢到的份额？",
        "severity": "medium",
        "trigger_message": "Market sizing conflates TAM with realistic addressable market (SOM).",
        "impact": "投资人一眼识破，信任崩塌；实际经营与预期严重脱节",
        "fix_task": "用自下而上法重新估算：目标城市 × 目标人群密度 × 转化率 = 真实SOM",
        "teaching_topic": "市场规模自下而上估算方法（TAM/SAM/SOM 实操）"
    },
    "H5": {
        "name": "需求证据不足",
        "type": "EvidenceInsufficiency",
        "description": "需求判断基于臆测或少量样本，缺乏系统性用户调研证据",
        "nodes": {"problem": "Concept", "evidence": "Evidence", "user_interview": "Task"},
        "constraint": "problem.must_be_evidenced_by(user_interview OR survey)",
        "check_hint": "你说用户有这个痛点，这个结论是怎么来的？访谈了多少人？有录音或记录吗？",
        "severity": "high",
        "trigger_message": "Demand claims are not supported by sufficient user research evidence.",
        "impact": "整个项目建立在未经验证的假设上，一旦需求不真实则全盘皆输",
        "fix_task": "完成 ≥10 次深度用户访谈，记录原话，输出亲和图（Affinity Map）",
        "teaching_topic": "用户调研方法论（访谈 + 问卷 + 数据驱动）"
    },
    "H6": {
        "name": "竞品对比不可比",
        "type": "CompetitiveAnalysisGap",
        "description": "竞品对比维度错误或仅对比表面功能，未触及真实竞争护城河",
        "nodes": {"competitor": "Case", "differentiation": "Concept"},
        "constraint": "competitor_analysis.must_address(real_moat_not_features)",
        "check_hint": "你选的对比维度是客户真正决策时最看重的吗？还是在展示你自己擅长的维度？",
        "severity": "medium",
        "trigger_message": "Competitive analysis uses incomparable or misleading dimensions.",
        "impact": "评委认为团队对市场理解肤浅，评分大幅下降",
        "fix_task": "重建竞品矩阵：选取 ≥3 个真实替代方案，从客户视角选5个决策维度进行对比",
        "teaching_topic": "竞品分析框架与差异化壁垒构建"
    },
    "H7": {
        "name": "创新点不可验证",
        "type": "InnovationClaim",
        "description": "声称的创新点无法被客观验证，属于主观描述而非可测量的技术/商业突破",
        "nodes": {"innovation": "Concept", "technology": "Technology", "evidence": "Evidence"},
        "constraint": "innovation_claim.must_be_measurable_and_verifiable",
        "check_hint": "你说的创新点，能用什么实验或数据证明它真的比现有方案优秀？",
        "severity": "medium",
        "trigger_message": "Innovation claims cannot be verified or measured objectively.",
        "impact": "在技术评审环节无法说服评委，被认定为伪创新",
        "fix_task": "设计对照实验或提供第三方测评报告，量化创新带来的性能提升指标",
        "teaching_topic": "技术创新验证方法与专利/论文支撑"
    },
    "H8": {
        "name": "单位经济不成立",
        "type": "UnitEconomics",
        "description": "单笔交易亏损，或LTV（客户终身价值）< CAC（获客成本）+ 边际运营成本",
        "nodes": {"LTV": "Metric", "CAC": "Metric", "unit_margin": "Metric"},
        "constraint": "LTV > CAC + marginal_cost AND unit_margin > 0",
        "check_hint": "每完成一笔交易，减去所有变动成本后是赚钱还是亏钱？获客成本怎么测算的？",
        "severity": "high",
        "trigger_message": "Unit economics do not hold: LTV < CAC or per-transaction margin is negative.",
        "impact": "规模越大亏损越多，商业模式在数学上不成立",
        "fix_task": "逐项列出单笔交易的收入与变动成本，计算真实毛利率，并估算 LTV/CAC 比值",
        "teaching_topic": "单位经济模型：LTV/CAC/毛利率计算实操"
    },
    "H9": {
        "name": "增长逻辑跳跃",
        "type": "GrowthPathGap",
        "description": "从初始用户到规模化增长缺乏具体路径，存在不可实现的跳跃式假设",
        "nodes": {"growth_path": "Method", "milestones": "Task", "scaling": "Concept"},
        "constraint": "growth_path.must_have_concrete_steps(from_0_to_100)",
        "check_hint": "获得前100个客户后，如何用同样逻辑获得10000个客户？增长飞轮在哪里？",
        "severity": "medium",
        "trigger_message": "Growth path contains unrealistic leaps without concrete mechanisms.",
        "impact": "初期增长后陷入瓶颈，无法规模化复制",
        "fix_task": "设计增长飞轮图：标注每个增长阶段的核心驱动力和瓶颈突破方式",
        "teaching_topic": "从0到1再到100：增长路径规划与飞轮设计"
    },
    "H10": {
        "name": "里程碑不可交付",
        "type": "ExecutionFeasibility",
        "description": "计划里程碑在给定时间和资源约束下根本无法实现",
        "nodes": {"milestone": "Task", "resources": "Resource", "timeline": "Metric"},
        "constraint": "milestone.must_be_achievable_within(resources AND timeline)",
        "check_hint": "用你现有的人力、资金和时间，这个里程碑真的3个月内能完成吗？",
        "severity": "high",
        "trigger_message": "Milestones are not achievable given the team's current resources and timeline.",
        "impact": "项目推进失速，融资节点无法兑现，信用受损",
        "fix_task": "重新拆分里程碑：每个节点必须注明负责人、所需资源和验收标准",
        "teaching_topic": "敏捷项目管理与里程碑设置方法"
    },
    "H11": {
        "name": "合规/伦理缺口",
        "type": "ComplianceRisk",
        "description": "业务模式存在明显合规风险（数据隐私、版权授权、行业牌照等），未被识别或规避",
        "nodes": {"business_model": "Concept", "regulation": "Concept", "ethics": "Concept"},
        "constraint": "business_model.must_comply_with(applicable_regulations AND ethical_standards)",
        "check_hint": "这个业务涉及用户数据吗？需要哪些许可证？用到的素材是否已获授权？",
        "severity": "high",
        "trigger_message": "Business model has identifiable compliance or ethics gaps.",
        "impact": "强制下架或法律追责，企业声誉受损",
        "fix_task": "列出业务所有可能触碰的法规清单，逐条标注合规状态和解决方案",
        "teaching_topic": "创业合规基础：数据隐私、知识产权与行业准入"
    },
    "H12": {
        "name": "技术路线与资源不匹配",
        "type": "TechFeasibility",
        "description": "选择的技术路线对团队现有能力和资源要求远超实际，存在系统性风险",
        "nodes": {"technology": "Technology", "team": "Participant", "resource": "Resource"},
        "constraint": "technology.complexity.must_match(team.capability AND resource.availability)",
        "check_hint": "这个技术路线里最难的那个环节，你们团队里谁有能力做？做过类似项目吗？",
        "severity": "high",
        "trigger_message": "Technology roadmap far exceeds the team's actual capabilities and resources.",
        "impact": "技术债务累积，关键节点无法交付，项目烂尾",
        "fix_task": "识别技术栈中最高风险点，制定 POC 验证计划，并评估是否需要引入外部技术顾问",
        "teaching_topic": "技术可行性评估与MVP边界设定"
    },
    "H13": {
        "name": "实验设计不合格",
        "type": "ValidationMethodology",
        "description": "所设计的验证实验存在样本偏差、控制变量缺失等方法论问题，结论不可信",
        "nodes": {"experiment": "Task", "evidence": "Evidence", "methodology": "Method"},
        "constraint": "experiment.must_have(control_group AND sufficient_sample AND clear_metrics)",
        "check_hint": "你这个实验的样本量够吗？怎么控制干扰变量？结论能推广到多大范围？",
        "severity": "medium",
        "trigger_message": "Validation experiment design is methodologically flawed.",
        "impact": "基于错误实验的决策导致资源浪费，无法被投资人或学术评委认可",
        "fix_task": "重新设计实验：明确假设、样本规模计算（统计显著性）、对照组设置",
        "teaching_topic": "科学实验设计方法与商业假设验证"
    },
    "H14": {
        "name": "路演叙事断裂",
        "type": "PitchNarrativeGap",
        "description": "路演叙事逻辑不连贯，痛点→解决方案→商业模式→团队之间缺乏因果链接",
        "nodes": {"pitch_deck": "Artifact", "narrative": "Method", "story_flow": "Concept"},
        "constraint": "pitch.narrative.must_have_causal_flow(problem -> solution -> business -> team)",
        "check_hint": "听你的 pitch，能否在听完之后自然推导出'所以你们能成'这个结论？断点在哪？",
        "severity": "medium",
        "trigger_message": "Pitch narrative has logical breaks between key sections.",
        "impact": "评委在路演结束时仍不理解项目价值，打低分",
        "fix_task": "用5句话讲完项目（痛点→方案→市场→赚钱→为什么是你们），确保每句话都是上一句的必然结果",
        "teaching_topic": "创业叙事与故事结构设计（Storytelling）"
    },
    "H15": {
        "name": "评分项证据覆盖不足",
        "type": "RubricEvidenceGap",
        "description": "项目材料中缺乏 Rubric 评分所要求的必要证据文件，导致丢分",
        "nodes": {"rubric_item": "RubricItem", "evidence": "Evidence", "artifact": "Artifact"},
        "constraint": "project.must_provide(all_required_evidence_per_rubric_item)",
        "check_hint": "评分标准里要求的用户访谈记录、竞品矩阵、财务模型，你们都准备好了吗？",
        "severity": "medium",
        "trigger_message": "Project lacks evidence required by one or more Rubric items.",
        "impact": "在评审环节因证据缺失被直接扣分，影响最终名次",
        "fix_task": "逐条对照评分 Rubric，列出缺失证据清单，制定72小时补充计划",
        "teaching_topic": "竞赛材料准备与证据链建设"
    },
    "H16": {
        "name": "隐性替代方案忽视",
        "type": "CompetitiveBlindspot",
        "description": "只关注直接竞品，忽视用户当前采用的替代解决方案（含零成本惰性方案）",
        "nodes": {"competitor": "Case", "substitute": "Concept", "switching_cost": "Metric"},
        "constraint": "competitor_analysis.must_include(indirect_substitutes AND status_quo)",
        "check_hint": "如果不用你的产品，用户现在是怎么解决这个问题的？这个现有方法有什么根本缺陷？",
        "severity": "high",
        "trigger_message": "Analysis ignores indirect substitutes and the user's current workaround.",
        "impact": "产品推出后用户不切换，获客成本远高于预期",
        "fix_task": "列出用户现有5种替代行为，分析每种替代方案的缺点，证明你的方案有足够的迁移动机",
        "teaching_topic": "广义竞争逻辑：隐形替代品与用户惰性识别"
    },
    "H17": {
        "name": "巨头入场风险未评估",
        "type": "StrategicRisk",
        "description": "未分析行业巨头如果入场的应对策略，存在被降维打击的系统性风险",
        "nodes": {"competitor": "Case", "moat": "Concept", "technology": "Technology"},
        "constraint": "project.must_have(giant_entry_scenario AND defense_strategy)",
        "check_hint": "如果字节跳动/腾讯/美团下个月进入你的赛道并且免费，你的护城河是什么？",
        "severity": "high",
        "trigger_message": "No contingency plan for market entry by large incumbents.",
        "impact": "一旦巨头入场，项目立即失去竞争力且无退路",
        "fix_task": "制作'巨头入场推演图'：列出3家最可能的巨头、入场方式和你的差异化生存策略",
        "teaching_topic": "护城河理论（Moat Strategy）与差异化防御"
    },
    "H18": {
        "name": "现金流断裂风险",
        "type": "FinancialViability",
        "description": "盈利预测乐观但忽视实际回款周期、垫资压力和现金流时序，隐藏断粮风险",
        "nodes": {"cash_flow": "Metric", "burn_rate": "Metric", "revenue": "Metric"},
        "constraint": "cash_flow.must_not_go_negative_before(next_funding_round OR BEP)",
        "check_hint": "如果没有外部融资，账上的钱能支撑多少个月？What is your monthly burn rate?",
        "severity": "high",
        "trigger_message": "Cash flow analysis reveals risk of running out of cash before breakeven.",
        "impact": "运营中途断粮，被迫低价出售或关停，所有努力付之东流",
        "fix_task": "制作12个月现金流预测表，标注每月收支和账上余额，找出最危险的月份",
        "teaching_topic": "创业财务：现金流预测与资金管理"
    },
    "H19": {
        "name": "获客成本幻觉（大数法则误用）",
        "type": "FinancialHallucination",
        "description": "用宏观市场百分比（如'只要1%的人买'）替代真实获客路径分析，制造财务幻觉",
        "nodes": {"CAC": "Metric", "customer": "Concept", "market": "Market"},
        "constraint": "customer_acquisition.must_use_concrete_CAC_not_percentage_of_TAM",
        "check_hint": "这1%的人散落在哪里？你打算花多少钱找到第一个付费客户？CAC是多少？",
        "severity": "high",
        "trigger_message": "Customer acquisition plan relies on 'percentage of market' fallacy rather than concrete CAC.",
        "impact": "实际获客成本是预期的10-100倍，商业模式崩溃",
        "fix_task": "估算具体的单人获客成本（CAC）：选一个渠道，计算触达人数、转化率和每次触达成本",
        "teaching_topic": "精准获客逻辑：CAC计算与渠道ROI分析"
    },
    "H20": {
        "name": "持续竞争力路径缺失",
        "type": "SustainabilityGap",
        "description": "无法解释项目如何建立长期持续竞争力，护城河随时间自然加深的机制缺失",
        "nodes": {"moat": "Concept", "network_effect": "Concept", "switching_cost": "Metric"},
        "constraint": "project.must_have(sustainable_moat_mechanism_over_time)",
        "check_hint": "三年后你的竞争力比现在更强还是更弱？什么机制让你的优势随时间累积？",
        "severity": "medium",
        "trigger_message": "No clear mechanism for building durable competitive advantage over time.",
        "impact": "短期成功后护城河被侵蚀，市场份额被蚕食",
        "fix_task": "设计一项'护城河积累机制'：数据壁垒、网络效应、转换成本或规模经济，选其一并量化",
        "teaching_topic": "商业模式防御性与护城河设计（巴菲特经济护城河框架）"
    },
}

# ── Rubric 评分项（R1-R9）────────────────────────────────────
RUBRIC_ITEMS = [
    {
        "id": "R1", "name": "Problem Definition", "weight": 0.10,
        "description": "Problem is clear, specific, and grounded in real user pain",
        "required_evidence": ["User Interview", "Survey"],
        "common_mistakes": ["Vague problem", "Assumed pain point"],
        "score_floor_criteria": "Has conducted ≥5 user interviews with documented quotes",
    },
    {
        "id": "R2", "name": "User Evidence Strength", "weight": 0.15,
        "description": "Claims are supported by sufficient and relevant evidence",
        "required_evidence": ["Interview Quotes", "Behavioral Data"],
        "common_mistakes": ["Opinion-based validation", "Sample size < 10"],
        "score_floor_criteria": "Has ≥10 data points from real users (not team members)",
    },
    {
        "id": "R3", "name": "Solution Feasibility", "weight": 0.10,
        "description": "Solution is technically and operationally feasible",
        "required_evidence": ["Technical Roadmap", "Resource Match", "POC/Prototype"],
        "common_mistakes": ["Over-engineering", "No prototype evidence"],
        "score_floor_criteria": "Has a working prototype or POC, even minimal",
    },
    {
        "id": "R4", "name": "Business Model Consistency", "weight": 0.15,
        "description": "Customer, value, channel, revenue, and cost are consistent",
        "required_evidence": ["Business Model Canvas", "Unit Economics"],
        "common_mistakes": ["Channel-user mismatch", "Revenue not tied to value delivered"],
        "score_floor_criteria": "All 5 business model blocks are filled and internally consistent",
    },
    {
        "id": "R5", "name": "Market & Competition", "weight": 0.10,
        "description": "Market sizing and competition analysis are reasonable",
        "required_evidence": ["TAM/SAM/SOM breakdown", "Competitor Table"],
        "common_mistakes": ["Inflated market size using TAM", "Missing indirect competitors"],
        "score_floor_criteria": "SOM estimated with bottom-up logic; ≥3 competitors analyzed",
    },
    {
        "id": "R6", "name": "Financial Logic", "weight": 0.10,
        "description": "Unit economics and financial assumptions are reasonable",
        "required_evidence": ["Unit Economics Table", "Cash Flow Projection"],
        "common_mistakes": ["LTV < CAC", "CAC assumed to be 0", "Missing burn rate"],
        "score_floor_criteria": "LTV > CAC demonstrated; 12-month cash flow projected",
    },
    {
        "id": "R7", "name": "Innovation & Differentiation", "weight": 0.10,
        "description": "Clear differentiation with verifiable advantages over substitutes",
        "required_evidence": ["Comparison Matrix", "Patent/Paper (for tech projects)"],
        "common_mistakes": ["Pseudo-innovation", "No measurable performance delta"],
        "score_floor_criteria": "Differentiation is measurable, not just claimed",
    },
    {
        "id": "R8", "name": "Team & Execution", "weight": 0.05,
        "description": "Team capability matches project ambition with concrete milestones",
        "required_evidence": ["Team Profile with roles", "Milestone Chart"],
        "common_mistakes": ["Skill mismatch", "Milestones without owners or acceptance criteria"],
        "score_floor_criteria": "Each milestone has an owner, timeline, and deliverable",
    },
    {
        "id": "R9", "name": "Presentation & Material Quality", "weight": 0.05,
        "description": "Materials are clear, logical, and persuasive with causal narrative flow",
        "required_evidence": ["Pitch Deck", "Demo/Prototype Video"],
        "common_mistakes": ["Story breaks", "Data without context", "Missing call-to-action"],
        "score_floor_criteria": "Narrative flows: Problem→Solution→Market→Finance→Team",
    },
]

# ── 追问策略库（≥15种）────────────────────────────────────────
INTERROGATION_STRATEGIES = {
    "invisible_substitutes": {
        "name": "隐形替代品策略",
        "trigger": ["没有对手", "第一家", "唯一", "独创", "没有竞争"],
        "logic": "广义竞争逻辑：引导从产品形态转向用户任务目标，揭示零成本替代方案",
        "template": "你解决的核心任务是'[TASK]'。但用户现在解决这个任务的方式是什么？即便没有你，他们能'凑合'吗？凑合方案的成本是多少？你的方案比凑合贵多少？"
    },
    "giant_shadow": {
        "name": "巨头阴影策略",
        "trigger": ["技术壁垒", "领先", "独家", "护城河", "技术门槛"],
        "logic": "商业降维逻辑：技术领先≠市场领先，巨头资本碾压速度 vs 技术迭代速度",
        "template": "你的超图里有'[TECH_NODE]'节点。如果[GIANT]用'暴力拆解+资源碾压'复制这个技术并免费开放，你的护城河还剩什么？"
    },
    "switching_cost": {
        "name": "迁移成本测试",
        "trigger": ["用户会喜欢", "体验更好", "比现在好"],
        "logic": "关注用户从旧方案迁移到新方案的实际痛苦程度",
        "template": "即便你的方案好[X]%，用户需要改变哪些习惯或购买哪些新设备才能用上？这个迁移成本能被[X]%的提升覆盖吗？"
    },
    "cac_reality": {
        "name": "精准获客逻辑",
        "trigger": ["1%", "只要一点用户", "病毒传播", "刷屏", "自然流量"],
        "logic": "拆解流量成本与转化率，破除'大数幻觉'和'免费获客幻觉'",
        "template": "这[X]%的用户散落在哪里？你打算花多少钱找到第一个付费用户？请给我一个具体的**单人获客成本（CAC）**估算，精确到元。"
    },
    "unit_economics_drill": {
        "name": "单位经济压力测试",
        "trigger": ["肯定赚钱", "利润很高", "成本很低", "毛利"],
        "logic": "逐笔核算成本与收入，找出隐性成本和财务漏洞",
        "template": "我们来算一笔账：完成一单交易，你的直接成本是[A]，间接成本是[B]，获客成本分摊是[C]，收入是[D]。D > A+B+C 吗？如果不是，你什么时候能达到盈亏平衡？"
    },
    "bep_cashflow": {
        "name": "现金流生存逻辑",
        "trigger": ["先免费", "后期再赚钱", "积累用户", "融资后"],
        "logic": "区分'公益项目'与'商业项目'，暴露现金流断裂风险",
        "template": "如果没有外部融资，你账上的钱能支撑你'不赚钱'跑多久？**盈亏平衡点（BEP）**在哪里？每月烧多少钱？"
    },
    "pain_specificity": {
        "name": "痛点精准探测",
        "trigger": ["用户需要", "用户想要", "解决问题", "帮助用户"],
        "logic": "区分'真需求'与'伪需求'，要求具体的人群、场景、频率",
        "template": "你说的那个'痛点'，能描述成这样吗：'[具体人群]在[具体场景]下每[频率]需要[具体任务]，但现在的方法让他们付出了[具体损失]'？能用你自己的项目填进去吗？"
    },
    "evidence_challenge": {
        "name": "证据链质疑",
        "trigger": ["我们认为", "应该会", "感觉用户", "我觉得"],
        "logic": "区分主观假设与客观证据，要求可验证的第一手数据",
        "template": "这个判断是你们团队开会得出的，还是来自真实用户的第一手反馈？有多少人告诉过你他在这件事上愿意付钱？"
    },
    "mvp_boundary": {
        "name": "MVP边界设定",
        "trigger": ["功能很多", "全面", "智能", "一站式", "全都有"],
        "logic": "引导聚焦最小可验证产品，削减非核心功能",
        "template": "如果只保留一个功能，能让你的第一批用户愿意付钱的那个功能是什么？其他的功能，在第一个月不存在的话，会有用户因此拒绝使用吗？"
    },
    "team_capability_gap": {
        "name": "团队能力缺口诊断",
        "trigger": ["团队", "我们有", "成员", "负责人"],
        "logic": "识别团队能力分布中的角色盲区或严重缺失",
        "template": "你们团队里谁负责找第一个付费客户？谁负责和供应商谈判？如果这两件事没人做，技术有多好都没用。"
    },
    "compliance_probe": {
        "name": "合规风险探测",
        "trigger": ["数据", "用户信息", "采集", "AI", "医疗", "金融", "无人机", "跨境"],
        "logic": "主动探测潜在合规盲区，防止在实际运营中触法",
        "template": "这个业务涉及[数据类型/行业]。在你所在的法律管辖区，这类业务需要哪些许可证或资质？你查过相关法规吗？"
    },
    "milestone_stress": {
        "name": "里程碑可行性压测",
        "trigger": ["三个月", "一个月", "半年", "很快", "马上"],
        "logic": "评估里程碑的可实现性，暴露过度乐观的时间估算",
        "template": "你说[时间]内要完成[里程碑]。现在团队有几人在全职做这件事？[最关键的环节]需要多少工时？算出来吗？"
    },
    "market_size_bottom_up": {
        "name": "市场规模向下拆解",
        "trigger": ["万亿", "千亿", "百亿", "巨大市场", "潜力很大"],
        "logic": "强制从宏观市场降落到真实可触达规模",
        "template": "你说市场有[X]亿。但你第一年能触达的城市是哪几个？那些城市里有多少你的目标用户？他们的转化率是多少？算下来你第一年的真实SOM是多少？"
    },
    "differentiation_depth": {
        "name": "差异化深度追问",
        "trigger": ["我们更好", "功能更多", "体验更优", "更便宜"],
        "logic": "区分表面功能差异与真正的结构性竞争优势",
        "template": "你说你比竞品'体验更好'。但如果竞品花3个月把这个体验也做好了，你的差异化还在吗？什么是他们3年内也复制不了的？"
    },
    "intellectual_property": {
        "name": "知识产权合法性检查",
        "trigger": ["使用", "参考", "基于", "改进", "扫描", "原材料", "模型"],
        "logic": "检测潜在的版权、专利或数据授权问题",
        "template": "你们用到的[素材/数据/模型]，有办法确认使用权吗？原作者/版权方是否授权了商业使用？如果没有，这可能是一个法律风险点。"
    },
}


# ── 赛事评分模板（≥4套）──────────────────────────────────────
COMPETITION_RUBRICS = {
    "internet_plus": {
        "name": "中国国际大学生创新大赛（原互联网+）",
        "focus": ["商业模式闭环", "财务真实性", "团队股权结构", "社会影响力", "带动就业"],
        "weight_overrides": {"R6": 0.20, "R4": 0.20, "R2": 0.15, "R8": 0.10},
        "key_deductions": ["单位经济不成立", "获客渠道错位", "财务数据虚假", "团队兼职比例过高"],
        "special_requirements": ["需提供税务登记或工商注册证明", "营收数据须有银行流水支撑"],
    },
    "challenge_cup": {
        "name": "挑战杯全国大学生课外学术科技作品竞赛",
        "focus": ["学术深度", "技术创新壁垒", "社会调查严谨性", "论文/专利支撑"],
        "weight_overrides": {"R7": 0.25, "R2": 0.20, "R3": 0.20},
        "key_deductions": ["技术实现路径模糊", "缺乏论文或专利支撑", "社会调查样本量不足"],
        "special_requirements": ["建议附上相关领域SCI/EI论文或专利申请受理通知书"],
    },
    "chuangqing": {
        "name": "全国大学生创业大赛（创青春）",
        "focus": ["创业精神", "社会价值", "实际落地证明", "导师资源"],
        "weight_overrides": {"R8": 0.20, "R1": 0.20, "R4": 0.15},
        "key_deductions": ["仅有想法无任何实际行动", "社会效益描述过于空洞"],
        "special_requirements": ["需提供已注册公司或在校创业孵化证明"],
    },
    "math_modeling": {
        "name": "全国大学生数学建模竞赛（含双创建模方向）",
        "focus": ["模型严谨性", "数据来源可信度", "算法创新性", "结论可重现性"],
        "weight_overrides": {"R7": 0.30, "R3": 0.25, "R6": 0.20},
        "key_deductions": ["模型假设不合理", "数据来源不可考", "无敏感性分析"],
        "special_requirements": ["必须提供完整的算法描述和数据集，结论须能被独立复现"],
    },
}


def get_rules_for_prompt() -> str:
    """将规则格式化为适合嵌入Prompt的文本"""
    lines = ["\n【逻辑审计规则库 H1-H20】"]
    for rule_id, rule in RULES.items():
        sev = rule['severity'].upper()
        lines.append(f"\n{rule_id} [{sev}] - {rule['name']}")
        lines.append(f"  定义：{rule['description']}")
        lines.append(f"  审计要点：{rule['check_hint']}")
        lines.append(f"  不修复影响：{rule['impact']}")
    return "\n".join(lines)


def get_rule_by_id(rule_id: str) -> Dict[str, Any]:
    return RULES.get(rule_id.upper(), {})


def get_strategy_for_fallacy(fallacy_keywords: list) -> str:
    """根据关键词匹配追问策略"""
    for strategy_id, strategy in INTERROGATION_STRATEGIES.items():
        for trigger in strategy.get("trigger", []):
            for kw in fallacy_keywords:
                if trigger in kw or kw in trigger:
                    return strategy_id
    return "evidence_challenge"


def get_competition_rubric(competition_name: str) -> dict:
    """根据赛事名称模糊匹配对应的评分模板"""
    name_lower = competition_name.lower()
    if "互联网" in competition_name or "internet" in name_lower:
        return COMPETITION_RUBRICS["internet_plus"]
    elif "挑战杯" in competition_name or "challenge" in name_lower:
        return COMPETITION_RUBRICS["challenge_cup"]
    elif "创青春" in competition_name or "chuangqing" in name_lower:
        return COMPETITION_RUBRICS["chuangqing"]
    elif "数学建模" in competition_name or "modeling" in name_lower:
        return COMPETITION_RUBRICS["math_modeling"]
    else:
        return COMPETITION_RUBRICS["internet_plus"]  # 默认使用互联网+
