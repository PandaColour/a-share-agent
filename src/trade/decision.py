# -*- coding: utf-8 -*-
"""交易决策数据类"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class TradingDecision:
    action: str          # 买入、持有、卖出
    confidence: float    # 信心度 0-1
    reason: str         # 决策理由
    risk_level: str     # 风险等级：低、中等、高
    timestamp: str      # 决策时间
    current_price: float = 0.0      # 当前价格
    daily_high: float = 0.0         # 当日最高价
    daily_low: float = 0.0          # 当日最低价
    daily_change: float = 0.0       # 日涨跌额
    daily_change_percent: float = 0.0  # 日涨跌幅
    
    # 价格区间分析字段（保留基础价格区间信息）
    price_range_low: float = 0.0        # 价格区间下限
    price_range_high: float = 0.0       # 价格区间上限
    upside_potential: float = 0.0       # 上涨空间百分比

    # 多轮辩论结果字段
    multi_round_debate_result: Optional[Dict[str, Any]] = None  # 多轮辩论完整结果
    debate_rounds: Optional[list] = None                        # 辩论轮次数据
    key_factors: Optional[list] = None                          # 关键决策因素
    debate_quality: Optional[str] = None                        # 辩论质量评估

    # 执行状态和错误跟踪字段
    analysis_status: str = "initialized"                        # 分析状态: initialized, in_progress, completed, timeout, error
    timeout_info: Optional[Dict[str, Any]] = None               # 超时信息记录
    error_info: Optional[Dict[str, Any]] = None                 # 错误信息记录
    execution_time: float = 0.0                                 # 执行耗时(秒)
