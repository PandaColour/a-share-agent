# -*- coding: utf-8 -*-
"""风险管理器 - 增强版"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self):
        self.max_position_size = 0.1

    def assess_risk(self, data: pd.DataFrame, indicators: Dict = None,
                   symbol: str = None, analyses: List[Dict] = None) -> Dict:
        """
        风险评估 - 兼容多种调用方式

        Args:
            data: 价格数据 (必需)
            indicators: 技术指标字典 (可选)
            symbol: 股票代码 (可选)
            analyses: 分析结果列表 (可选)

        Returns:
            风险评估结果字典
        """
        if indicators is None:
            indicators = {}

        risk_assessment = {
            "risk_level": "中等",
            "risk_score": 0.5,
            "risk_factors": [],
            "position_recommendation": 0.05
        }

        # 1. 波动率风险评估
        volatility = indicators.get('volatility')
        if volatility is None and len(data) >= 20:
            # 自动计算波动率
            returns = data['Close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)  # 年化波动率
            indicators['volatility'] = volatility

        if volatility and not pd.isna(volatility):
            if volatility > 0.6:
                risk_assessment["risk_factors"].append(f"极高波动率({volatility:.1%})")
                risk_assessment["risk_score"] += 0.3
            elif volatility > 0.4:
                risk_assessment["risk_factors"].append(f"高波动率({volatility:.1%})")
                risk_assessment["risk_score"] += 0.2
            elif volatility > 0.3:
                risk_assessment["risk_factors"].append(f"波动率偏高({volatility:.1%})")
                risk_assessment["risk_score"] += 0.1

        # 2. 价格位置风险评估
        price_position = indicators.get('price_position')
        if price_position is None and len(data) >= 60:
            # 自动计算价格位置
            high_60 = data['High'].tail(60).max()
            low_60 = data['Low'].tail(60).min()
            current = data['Close'].iloc[-1]

            if high_60 > low_60:
                price_position = (current - low_60) / (high_60 - low_60)
                indicators['price_position'] = price_position

        if price_position and not pd.isna(price_position):
            if price_position > 0.9:
                risk_assessment["risk_factors"].append(f"价格高位({price_position:.1%})")
                risk_assessment["risk_score"] += 0.2
            elif price_position > 0.8:
                risk_assessment["risk_factors"].append(f"价格偏高({price_position:.1%})")
                risk_assessment["risk_score"] += 0.1

        # 3. 近期涨幅风险评估
        if len(data) >= 20:
            price_20d_ago = data['Close'].iloc[-20]
            current = data['Close'].iloc[-1]
            gain_20d = (current - price_20d_ago) / price_20d_ago

            if gain_20d > 0.5:
                risk_assessment["risk_factors"].append(f"近期大涨({gain_20d:.1%})")
                risk_assessment["risk_score"] += 0.25
            elif gain_20d > 0.3:
                risk_assessment["risk_factors"].append(f"近期涨幅较大({gain_20d:.1%})")
                risk_assessment["risk_score"] += 0.15

        # 4. 确定最终风险等级
        risk_score = risk_assessment["risk_score"]
        if risk_score > 0.8:
            risk_assessment["risk_level"] = "极高"
            risk_assessment["position_recommendation"] = 0.01
        elif risk_score > 0.6:
            risk_assessment["risk_level"] = "高"
            risk_assessment["position_recommendation"] = 0.02
        elif risk_score < 0.3:
            risk_assessment["risk_level"] = "低"
            risk_assessment["position_recommendation"] = 0.08
        else:
            risk_assessment["risk_level"] = "中等"
            risk_assessment["position_recommendation"] = 0.05

        return risk_assessment
