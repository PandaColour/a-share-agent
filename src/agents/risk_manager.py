# -*- coding: utf-8 -*-
"""风险管理器"""

import pandas as pd
from typing import Dict, List

class RiskManager:
    def __init__(self):
        self.max_position_size = 0.1
        
    def assess_risk(self, symbol: str, data: pd.DataFrame, indicators: Dict, analyses: List[Dict]) -> Dict:
        risk_assessment = {
            "risk_level": "中等",
            "risk_score": 0.5,
            "risk_factors": [],
            "position_recommendation": 0.05
        }
        
        # 波动率风险
        volatility = indicators.get('volatility', 0.2)
        if volatility and not pd.isna(volatility):
            if volatility > 0.4:
                risk_assessment["risk_factors"].append("高波动率")
                risk_assessment["risk_score"] += 0.2
        
        # 价格位置风险
        price_position = indicators.get('price_position', 0.5)
        if price_position and not pd.isna(price_position) and price_position > 0.9:
            risk_assessment["risk_factors"].append("价格高位")
            risk_assessment["risk_score"] += 0.15
        
        # 确定风险等级
        if risk_assessment["risk_score"] > 0.7:
            risk_assessment["risk_level"] = "高"
            risk_assessment["position_recommendation"] = 0.02
        elif risk_assessment["risk_score"] < 0.3:
            risk_assessment["risk_level"] = "低"
            risk_assessment["position_recommendation"] = 0.08
            
        return risk_assessment
