# -*- coding: utf-8 -*-
"""模拟AI客户端，仅用于测试环境"""

from typing import Dict, Any

from .base import AIModelInterface


class MockAIClient(AIModelInterface):
    """
    模拟AI客户端，仅用于测试环境

    警告: 此类仅用于开发和测试，生产环境中不应使用Mock数据
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.responses = {
            "fundamental": "基于基本面数据，该股票财务状况良好，建议关注。",
            "technical": "技术指标显示该股票处于上升通道，短期看涨。",
            "sentiment": "市场情绪积极，投资者信心较强，适合持有。",
            "prediction": "预测分析：基于历史数据，该股票未来14天预期上涨5-8%。"
        }

    def generate_analysis(self, prompt: str, context: Dict = None) -> str:
        """生成模拟分析结果 - 仅用于测试"""
        # 简单的关键词匹配
        if "基本面" in prompt or "财务" in prompt:
            return self.responses["fundamental"]
        elif "技术面" in prompt or "指标" in prompt:
            return self.responses["technical"]
        elif "情感" in prompt or "情绪" in prompt:
            return self.responses["sentiment"]
        elif "预测" in prompt or "prediction" in prompt.lower():
            return self.responses["prediction"]
        else:
            return "AI分析：综合各项指标，该股票值得关注。"

    def generate_response(self, prompt: str, context: Dict = None) -> str:
        """生成模拟回应 - 用于辩论和对话场景"""
        # 辩论场景的模拟回应
        if "看涨" in prompt or "Bull" in prompt or "🐂" in prompt:
            return """🐂 看涨观点：

💡 核心论证：基于当前市场环境和数据分析，该股票具备明显的投资价值和上涨潜力。

📊 数据支撑：
- 当前估值水平相对合理，存在低估空间
- 技术面显示积极信号，支撑位稳固
- 行业基本面向好，政策环境有利

🎯 目标价位：建议关注15-20%的上涨空间

🛡️ 风险应对：建议分批建仓，设置合理止损位

🔥 反驳要点：市场短期波动不改变长期价值，当前调整为较好的入场机会。"""
        elif "看跌" in prompt or "Bear" in prompt or "🐻" in prompt:
            return """🐻 看跌观点：

⚠️ 核心风险：基于当前市场环境和风险分析，该股票面临多重下行压力和投资风险。

📉 数据警示：
- 估值水平可能存在高估风险，缺乏足够安全边际
- 技术面显示疲软信号，支撑位面临考验
- 行业周期性风险和政策不确定性增加

🎯 价格预期：建议关注10-15%的下行风险

🛡️ 防御策略：建议谨慎观望，或考虑适度减仓

🔍 质疑要点：当前乐观预期可能过于激进，需要更多时间验证基本面改善的可持续性。"""
        else:
            # 通用回应，调用原有逻辑
            return self.generate_analysis(prompt, context)

    def is_available(self) -> bool:
        return True