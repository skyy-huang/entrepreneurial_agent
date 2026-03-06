"""
H1-H15 逻辑审计规则库
将资深创业导师的经验编码为可机器执行的审计规则
"""
from typing import Dict

RULES: Dict[str, Dict[str, str]] = {
    "H1": {
        "name": "客户-渠道错位",
        "description": "目标客群与所选获客渠道不匹配，渠道无法有效触达目标人群",
        "check_hint": "目标客户是谁？通过什么渠道获客？该渠道是否真能到达这群人？",
        "severity": "high",
        "teaching_topic": "渠道获客与用户触达策略"
    },
    "H2": {
        "name": "竞争壁垒虚假",
        "description": "声称的核心壁垒（技术/关系/品牌）在竞争对手面前形同虚设",
        "check_hint": "竞争优势是否可被复制？大厂入场后是否立即失效？",
        "severity": "high",
        "teaching_topic": "竞争壁垒的构建与评估"
    },
    "H3": {
        "name": "市场规模虚高",
        "description": "使用自上而下方式估算市场，数字好看但无法落地到真实可触达需求",
        "check_hint": "TAM/SAM是否基于整体行业而非真实可触达细分市场？",
        "severity": "medium",
        "teaching_topic": "市场规模的自下而上估算方法（SOM实操）"
    },
    "H4": {
        "name": "收入模型单一脆弱",
        "description": "过度依赖单一收入来源，对市场变化或竞争极度敏感",
        "check_hint": "只有一种收入方式且没有备用计划吗？",
        "severity": "medium",
        "teaching_topic": "多元化收入模型设计"
    },
    "H5": {
        "name": "技术可行性未验证",
        "description": "核心技术或产品功能缺乏原型/POC，仅停留在概念阶段",
        "check_hint": "最核心的技术点有没有做过哪怕一个最小验证？",
        "severity": "high",
        "teaching_topic": "快速原型与MVP验证方法"
    },
    "H6": {
        "name": "团队关键能力缺口",
        "description": "团队明显缺乏执行商业计划所需的核心能力，且无填补计划",
        "check_hint": "谁负责技术？谁负责销售？关键岗位是否有合适的人？",
        "severity": "high",
        "teaching_topic": "创业团队的角色分工与能力互补"
    },
    "H7": {
        "name": "政策法规风险忽视",
        "description": "业务模式存在明显合规风险（如需牌照、涉及监管行业）但未做识别",
        "check_hint": "这个业务需要特殊许可证吗？是否触碰监管红线？",
        "severity": "high",
        "teaching_topic": "创业合规基础知识"
    },
    "H8": {
        "name": "单位经济不成立",
        "description": "单笔交易亏损，或LTV（客户终身价值）< CAC（获客成本）+ 边际运营成本",
        "check_hint": "每完成一笔交易，扣除所有变动成本后是赚钱还是亏钱？获客成本能否被回收？",
        "severity": "high",
        "teaching_topic": "单位经济模型：LTV/CAC/毛利率计算实操"
    },
    "H9": {
        "name": "规模化路径不清",
        "description": "无法清晰解释从0到1之后如何规模化扩张，缺乏增长飞轮设计",
        "check_hint": "获得前100个客户后，如何用同样逻辑获得10000个客户？",
        "severity": "medium",
        "teaching_topic": "从0到1再到100：增长路径规划"
    },
    "H10": {
        "name": "付费意愿假设偏高",
        "description": "定价基于成本加成而非客户感知价值，高估客户实际愿意支付的价格",
        "check_hint": "这个定价是客户调研结果还是自己算出来的？有人真的愿意付这个价吗？",
        "severity": "high",
        "teaching_topic": "基于客户价值的定价策略"
    },
    "H11": {
        "name": "渠道与定价矛盾",
        "description": "定价策略与所选渠道传达的品牌调性不符（如高端定价却走低端渠道）",
        "check_hint": "你的定价暗示什么品牌形象？你的渠道是否传递了同样的品牌信号？",
        "severity": "medium",
        "teaching_topic": "品牌调性与渠道选择的一致性"
    },
    "H12": {
        "name": "竞品分析缺失",
        "description": "未做任何直接或间接竞品研究，对竞争格局缺乏基本了解",
        "check_hint": "你知道你的直接竞争对手是谁吗？他们的优劣势是什么？",
        "severity": "medium",
        "teaching_topic": "竞品分析框架与实操方法"
    },
    "H13": {
        "name": "核心假设未验证",
        "description": "整个商业模式建立在一个或多个未经现实验证的关键假设上",
        "check_hint": "你的计划中哪个假设一旦被推翻，整个模式就崩了？你验证过它吗？",
        "severity": "high",
        "teaching_topic": "如何识别和验证核心商业假设"
    },
    "H14": {
        "name": "现金流断裂风险",
        "description": "盈利预测乐观但忽视实际回款周期、垫资压力和现金流时序",
        "check_hint": "账面盈利但现金什么时候到账？中间断粮怎么办？",
        "severity": "high",
        "teaching_topic": "创业财务：现金流预测与资金管理"
    },
    "H15": {
        "name": "持续性路径缺失",
        "description": "无法解释项目如何实现长期持续竞争力，护城河设计缺失",
        "check_hint": "三年后这个项目靠什么维持竞争力？护城河在哪里？",
        "severity": "medium",
        "teaching_topic": "商业模式的防御性与护城河设计"
    },
}


def get_rules_for_prompt() -> str:
    """将规则格式化为适合嵌入Prompt的文本"""
    lines = ["\n【逻辑审计规则库 H1-H15】"]
    for rule_id, rule in RULES.items():
        lines.append(f"\n{rule_id} [{rule['severity'].upper()}] - {rule['name']}")
        lines.append(f"  定义：{rule['description']}")
        lines.append(f"  审计要点：{rule['check_hint']}")
    return "\n".join(lines)


def get_rule_by_id(rule_id: str) -> Dict[str, str]:
    return RULES.get(rule_id.upper(), {})
