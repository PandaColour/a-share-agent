# -*- coding: utf-8 -*-
"""
高级决策引擎 - 多层次、多维度智能决策系统
"""

from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """市场状态枚举"""
    BULL_MARKET = "牛市"
    BEAR_MARKET = "熊市" 
    SIDEWAYS = "震荡市"
    VOLATILE = "高波动"

class SectorRotation(Enum):
    """板块轮动枚举"""
    GROWTH = "成长股"
    VALUE = "价值股"
    DEFENSIVE = "防御股"
    CYCLICAL = "周期股"

@dataclass
class MarketContext:
    """市场环境上下文"""
    regime: MarketRegime
    volatility_level: float  # 0-1
    sector_preference: SectorRotation
    risk_appetite: float  # 0-1
    macro_sentiment: str
    
@dataclass 
class DecisionCriteria:
    """决策标准"""
    min_confidence_threshold: float = 0.6
    max_risk_tolerance: float = 0.7
    sector_alignment_weight: float = 0.2
    momentum_weight: float = 0.15
    value_weight: float = 0.25
    quality_weight: float = 0.4

class AdvancedDecisionEngine:
    """高级决策引擎"""
    
    def __init__(self):
        self.market_context = self._analyze_market_context()
        self.decision_criteria = DecisionCriteria()
        
        # 动态权重系统
        self.base_weights = {
            "基本面分析": 0.4,
            "技术面分析": 0.35, 
            "情感面分析": 0.25
        }
        
        # 情景特定的权重调整
        self.regime_adjustments = {
            MarketRegime.BULL_MARKET: {"技术面分析": 0.1, "情感面分析": 0.1},
            MarketRegime.BEAR_MARKET: {"基本面分析": 0.15, "技术面分析": -0.05},
            MarketRegime.VOLATILE: {"情感面分析": -0.1, "基本面分析": 0.05}
        }
        
    def make_advanced_decision(self, symbol: str, analyses: List[Dict], 
                             risk_assessment: Dict, price_info: Dict,
                             market_data: Optional[Dict] = None) -> Dict:
        """
        高级决策制定
        
        Args:
            symbol: 股票代码
            analyses: 各分析师的分析结果
            risk_assessment: 风险评估
            price_info: 价格信息
            market_data: 市场数据
            
        Returns:
            包含详细决策逻辑的决策结果
        """
        try:
            # 1. 更新市场环境
            if market_data:
                self.market_context = self._update_market_context(market_data)
            
            # 2. 多维度一致性检查
            consistency_check = self._analyze_consistency(analyses)
            
            # 3. 动态权重计算
            dynamic_weights = self._calculate_dynamic_weights(
                analyses, risk_assessment, consistency_check
            )
            
            # 4. 情景分析决策
            scenario_decisions = self._scenario_based_decision(
                symbol, analyses, risk_assessment, dynamic_weights
            )
            
            # 5. 风险调整和仓位建议
            risk_adjusted_decision = self._apply_advanced_risk_management(
                scenario_decisions, risk_assessment, price_info
            )
            
            # 6. 决策置信度和质量评估
            decision_quality = self._evaluate_decision_quality(
                risk_adjusted_decision, analyses, consistency_check
            )
            
            # 7. 生成详细决策报告
            decision_report = self._generate_decision_report(
                symbol, risk_adjusted_decision, decision_quality, 
                consistency_check, dynamic_weights
            )
            
            return decision_report
            
        except Exception as e:
            logger.error(f"高级决策制定失败 {symbol}: {e}")
            return self._fallback_decision(symbol, analyses, risk_assessment)
    
    def _analyze_consistency(self, analyses: List[Dict]) -> Dict:
        """分析各分析师意见一致性"""
        recommendations = [a.get("recommendation", "持有") for a in analyses]
        confidences = [a.get("confidence", 0.5) for a in analyses]
        
        # 计算一致性指标
        unique_recommendations = set(recommendations)
        consistency_score = 1.0 - (len(unique_recommendations) - 1) * 0.3
        
        # 分析分歧点
        disagreement_details = {}
        if len(unique_recommendations) > 1:
            for rec in unique_recommendations:
                count = recommendations.count(rec)
                avg_conf = np.mean([confidences[i] for i, r in enumerate(recommendations) if r == rec])
                disagreement_details[rec] = {"count": count, "avg_confidence": avg_conf}
        
        # 计算加权一致性
        weighted_consistency = np.std(confidences) < 0.2  # 置信度标准差小表示更一致
        
        return {
            "consistency_score": consistency_score,
            "has_disagreement": len(unique_recommendations) > 1,
            "disagreement_details": disagreement_details,
            "weighted_consistency": weighted_consistency,
            "confidence_range": [min(confidences), max(confidences)],
            "dominant_view": max(set(recommendations), key=recommendations.count) if recommendations else "持有"
        }
    
    def _calculate_dynamic_weights(self, analyses: List[Dict], risk_assessment: Dict, 
                                 consistency_check: Dict) -> Dict:
        """计算动态权重"""
        weights = self.base_weights.copy()
        
        # 1. 基于市场状态调整
        regime_adj = self.regime_adjustments.get(self.market_context.regime, {})
        for analyst_type, adjustment in regime_adj.items():
            if analyst_type in weights:
                weights[analyst_type] += adjustment
        
        # 2. 基于一致性调整
        if consistency_check["has_disagreement"]:
            # 如有分歧，提高基本面分析权重
            weights["基本面分析"] += 0.1
            weights["情感面分析"] -= 0.05
        
        # 3. 基于各分析师的历史准确性调整（如果有记忆系统）
        for analysis in analyses:
            analyst_type = analysis.get("analyst_type", "")
            if analyst_type in weights and "historical_accuracy" in analysis:
                accuracy = analysis["historical_accuracy"]
                adjustment = (accuracy - 0.5) * 0.2  # ±10%调整
                weights[analyst_type] += adjustment
        
        # 4. 归一化权重
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v/total_weight for k, v in weights.items()}
        
        return weights
    
    def _scenario_based_decision(self, symbol: str, analyses: List[Dict], 
                               risk_assessment: Dict, weights: Dict) -> Dict:
        """基于情景的决策分析"""
        scenarios = ["牛市情景", "熊市情景", "基准情景"]
        scenario_results = {}
        
        for scenario in scenarios:
            scenario_factor = self._get_scenario_factor(scenario)
            
            # 调整各分析师的置信度和建议
            adjusted_analyses = []
            for analysis in analyses:
                adjusted_analysis = analysis.copy()
                adjusted_analysis["confidence"] *= scenario_factor
                adjusted_analyses.append(adjusted_analysis)
            
            # 计算该情景下的决策
            scenario_decision = self._calculate_weighted_decision(
                adjusted_analyses, weights, risk_assessment
            )
            scenario_results[scenario] = scenario_decision
        
        # 计算综合决策
        final_decision = self._aggregate_scenario_decisions(scenario_results)
        return final_decision
    
    def _apply_advanced_risk_management(self, decision: Dict, risk_assessment: Dict, 
                                      price_info: Dict) -> Dict:
        """应用高级风险管理"""
        base_recommendation = decision["recommendation"]
        confidence = decision["confidence"]
        
        # 1. 基于波动率调整仓位
        volatility = risk_assessment.get("volatility", 0.3)
        if volatility > 0.4:
            position_size = 0.5  # 高波动时减半仓位
        elif volatility > 0.25:
            position_size = 0.75
        else:
            position_size = 1.0
        
        # 2. 基于市场状态调整
        if self.market_context.regime == MarketRegime.BEAR_MARKET:
            if base_recommendation == "买入":
                base_recommendation = "观望"  # 熊市中避免激进买入
            position_size *= 0.7
        
        # 3. 基于技术面支撑阻力调整
        current_price = price_info.get("current_price", 0)
        if current_price > 0:
            # 简化的支撑阻力判断
            daily_high = price_info.get("daily_high", current_price)
            daily_low = price_info.get("daily_low", current_price)
            price_position = (current_price - daily_low) / max(daily_high - daily_low, 0.01)
            
            if price_position > 0.9 and base_recommendation == "买入":
                confidence *= 0.8  # 接近阻力位时降低买入信心
            elif price_position < 0.1 and base_recommendation == "卖出":
                confidence *= 0.8  # 接近支撑位时降低卖出信心
        
        return {
            "recommendation": base_recommendation,
            "confidence": min(confidence, 0.95),  # 最高置信度限制
            "position_size": position_size,
            "risk_level": self._calculate_risk_level(risk_assessment, position_size),
            "stop_loss": self._calculate_stop_loss(current_price, volatility),
            "take_profit": self._calculate_take_profit(current_price, base_recommendation),
            "reasoning": decision.get("reasoning", [])
        }
    
    def _evaluate_decision_quality(self, decision: Dict, analyses: List[Dict], 
                                 consistency_check: Dict) -> Dict:
        """评估决策质量"""
        quality_score = 0.0
        quality_factors = []
        
        # 1. 数据质量评估
        data_quality = min([len(a.get("reasoning", [])) for a in analyses]) / 3
        quality_score += data_quality * 0.2
        if data_quality > 0.8:
            quality_factors.append("数据完整性高")
        
        # 2. 分析师一致性评估
        consistency_score = consistency_check["consistency_score"]
        quality_score += consistency_score * 0.3
        if consistency_score > 0.7:
            quality_factors.append("分析师观点一致")
        
        # 3. 置信度合理性评估
        confidence = decision["confidence"]
        if 0.6 <= confidence <= 0.85:
            quality_score += 0.25
            quality_factors.append("置信度合理")
        elif confidence > 0.9:
            quality_factors.append("过度自信风险")
        
        # 4. 市场环境适应性评估
        regime_alignment = self._check_regime_alignment(decision)
        quality_score += regime_alignment * 0.25
        if regime_alignment > 0.7:
            quality_factors.append("策略符合市场环境")
        
        return {
            "quality_score": min(quality_score, 1.0),
            "quality_factors": quality_factors,
            "reliability": "高" if quality_score > 0.7 else "中" if quality_score > 0.5 else "低"
        }
    
    def _generate_decision_report(self, symbol: str, decision: Dict, quality: Dict,
                                consistency: Dict, weights: Dict) -> Dict:
        """生成详细决策报告"""
        return {
            "symbol": symbol,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "final_recommendation": decision["recommendation"],
            "confidence": round(decision["confidence"], 3),
            "position_size": round(decision["position_size"], 2),
            "risk_level": decision["risk_level"],
            "stop_loss": decision.get("stop_loss"),
            "take_profit": decision.get("take_profit"),
            
            # 决策质量
            "decision_quality": quality,
            
            # 分析师一致性
            "analyst_consistency": consistency,
            
            # 动态权重
            "dynamic_weights": {k: round(v, 3) for k, v in weights.items()},
            
            # 市场环境
            "market_context": {
                "regime": self.market_context.regime.value,
                "volatility_level": round(self.market_context.volatility_level, 3),
                "risk_appetite": round(self.market_context.risk_appetite, 3)
            },
            
            # 决策理由（更结构化）
            "reasoning": {
                "primary_factors": decision.get("reasoning", [])[:3],
                "risk_considerations": [f"风险等级: {decision['risk_level']}"],
                "market_factors": [f"市场状态: {self.market_context.regime.value}"],
                "quality_assessment": quality["quality_factors"]
            }
        }
    
    def _analyze_market_context(self) -> MarketContext:
        """分析市场环境（简化版本）"""
        # 这里可以集成真实的市场数据分析
        return MarketContext(
            regime=MarketRegime.SIDEWAYS,
            volatility_level=0.3,
            sector_preference=SectorRotation.VALUE,
            risk_appetite=0.6,
            macro_sentiment="中性"
        )
    
    def _update_market_context(self, market_data: Dict) -> MarketContext:
        """更新市场环境"""
        # 基于实时市场数据更新环境判断
        return self.market_context
    
    def _get_scenario_factor(self, scenario: str) -> float:
        """获取情景调整因子"""
        factors = {
            "牛市情景": 1.1,
            "熊市情景": 0.8,
            "基准情景": 1.0
        }
        return factors.get(scenario, 1.0)
    
    def _calculate_weighted_decision(self, analyses: List[Dict], weights: Dict, 
                                   risk_assessment: Dict) -> Dict:
        """计算加权决策"""
        # 实现加权计算逻辑
        weighted_confidence = 0
        recommendation_scores = {"买入": 0, "持有": 0, "卖出": 0}
        reasons = []
        
        for analysis in analyses:
            analyst_type = analysis.get("analyst_type", "")
            confidence = analysis.get("confidence", 0.5)
            recommendation = analysis.get("recommendation", "持有")
            weight = weights.get(analyst_type, 0.33)
            
            weighted_confidence += confidence * weight
            recommendation_scores[recommendation] += weight
            reasons.extend(analysis.get("reasoning", []))
        
        final_recommendation = max(recommendation_scores.items(), key=lambda x: x[1])[0]
        
        return {
            "recommendation": final_recommendation,
            "confidence": weighted_confidence,
            "reasoning": reasons[:5]  # 取前5个理由
        }
    
    def _aggregate_scenario_decisions(self, scenario_results: Dict) -> Dict:
        """聚合情景决策"""
        # 简化实现，实际可以更复杂
        base_decision = scenario_results.get("基准情景", {})
        return base_decision
    
    def _calculate_risk_level(self, risk_assessment: Dict, position_size: float) -> str:
        """计算风险等级"""
        base_risk = risk_assessment.get("risk_score", 0.5)
        adjusted_risk = base_risk * (1 + (1 - position_size))
        
        if adjusted_risk > 0.7:
            return "高"
        elif adjusted_risk > 0.4:
            return "中"
        else:
            return "低"
    
    def _calculate_stop_loss(self, current_price: float, volatility: float) -> float:
        """计算止损价"""
        if current_price <= 0:
            return 0
        return current_price * (1 - min(0.15, volatility * 0.5))
    
    def _calculate_take_profit(self, current_price: float, recommendation: str) -> float:
        """计算止盈价"""
        if current_price <= 0 or recommendation == "卖出":
            return 0
        
        multipliers = {"买入": 1.15, "持有": 1.08, "卖出": 1.0}
        return current_price * multipliers.get(recommendation, 1.0)
    
    def _check_regime_alignment(self, decision: Dict) -> float:
        """检查策略与市场环境的匹配度"""
        recommendation = decision["recommendation"]
        regime = self.market_context.regime
        
        alignments = {
            MarketRegime.BULL_MARKET: {"买入": 1.0, "持有": 0.7, "卖出": 0.2},
            MarketRegime.BEAR_MARKET: {"买入": 0.3, "持有": 0.8, "卖出": 1.0},
            MarketRegime.SIDEWAYS: {"买入": 0.6, "持有": 1.0, "卖出": 0.6},
        }
        
        return alignments.get(regime, {}).get(recommendation, 0.5)
    
    def _fallback_decision(self, symbol: str, analyses: List[Dict], 
                          risk_assessment: Dict) -> Dict:
        """备选决策"""
        return {
            "symbol": symbol,
            "final_recommendation": "持有",
            "confidence": 0.3,
            "position_size": 0.5,
            "risk_level": "中",
            "reasoning": {"primary_factors": ["决策引擎故障，采用保守策略"]}
        }