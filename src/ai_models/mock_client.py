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

    def is_available(self) -> bool:
        return True