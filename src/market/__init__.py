# -*- coding: utf-8 -*-
"""
市场监控模块 (Market Monitor Module)

提供市场整体状态监控、系统性风险识别、Beta系数计算等功能
用于将市场因素整合到个股分析决策中
"""

from .market_state import MarketMonitor, MarketTrend, get_market_state
from .beta_calculator import BetaCalculator, calculate_stock_beta
from .market_adjuster import MarketAdjuster, adjust_recommendation_by_market

__all__ = [
    'MarketMonitor',
    'MarketTrend',
    'get_market_state',
    'BetaCalculator',
    'calculate_stock_beta',
    'MarketAdjuster',
    'adjust_recommendation_by_market'
]

__version__ = '1.0.0'