# -*- coding: utf-8 -*-
"""
优化版决策引擎 - 支持买点优化信息集成
根据趋势确认和右侧交易信号优化投资决策
"""

from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)

@dataclass
class OptimizationInsights:
    """优化洞察数据结构"""
    trend_status: str
    expected_wait_days: float
    right_side_signals_count: int
    optimized_score: float
    position_strategy: Dict
    signal_quality: str
    buy_recommendation: str

class OptimizedDecisionEngine:
    """优化版决策引擎"""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager

        # 基础权重配置
        self.base_weights = {
            "基本面分析": 0.3,
            "技术面分析": 0.5,  # 提高技术面权重
            "情感面分析": 0.2
        }

        # 右侧交易奖励权重
        self.right_side_bonus_weights = {
            "trend_confirmed": 0.2,    # 趋势确认奖励
            "right_side_signals": 0.15, # 右侧信号奖励
            "signal_quality": 0.1      # 信号质量奖励
        }

        logger.info("优化版决策引擎初始化完成")

    def make_optimized_decision(self, symbol: str, analyses: List[Dict],
                              risk_assessment: Dict, price_info: Dict) -> Dict:
        """
        生成优化版投资决策

        Args:
            symbol: 股票代码
            analyses: 各分析师的分析结果
            risk_assessment: 风险评估
            price_info: 价格信息

        Returns:
            Dict: 包含优化洞察的决策结果
        """
        try:
            # 1. 提取优化信息
            optimization_insights = self._extract_optimization_insights(analyses)

            # 2. 计算传统决策分数
            traditional_decision = self._calculate_traditional_decision(analyses)

            # 3. 计算右侧交易加成
            right_side_bonus = self._calculate_right_side_bonus(optimization_insights)

            # 4. 风险调整
            risk_adjusted_score = self._apply_risk_adjustment(
                traditional_decision["score"], right_side_bonus, risk_assessment, optimization_insights
            )

            # 5. 生成最终决策
            final_decision = self._generate_final_decision(
                risk_adjusted_score, optimization_insights, traditional_decision
            )

            # 6. 构建完整决策结果
            decision_result = {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "final_recommendation": final_decision["recommendation"],
                "confidence": final_decision["confidence"],
                "decision_score": risk_adjusted_score,
                "reasoning": final_decision["reasoning"],
                "traditional_analysis": traditional_decision,
                "optimization_insights": optimization_insights,
                "right_side_bonus": right_side_bonus,
                "risk_adjustment": {
                    "original_score": traditional_decision["score"],
                    "adjusted_score": risk_adjusted_score,
                    "adjustment_factors": final_decision.get("adjustment_factors", [])
                },
                "position_strategy": optimization_insights.position_strategy if optimization_insights else {},
                "execution_plan": self._generate_execution_plan(final_decision, optimization_insights)
            }

            return decision_result

        except Exception as e:
            logger.error(f"优化决策失败 {symbol}: {e}")
            return self._create_fallback_decision(symbol, analyses)

    def _extract_optimization_insights(self, analyses: List[Dict]) -> Optional[OptimizationInsights]:
        """提取优化洞察信息"""
        try:
            for analysis in analyses:
                # 查找优化版技术分析
                if "优化版" in analysis.get("analyst_type", ""):
                    buy_optimization = analysis.get("buy_optimization", {})
                    if buy_optimization:
                        trend_confirmation = buy_optimization.get("trend_confirmation", {})
                        position_strategy = buy_optimization.get("position_strategy", {})
                        signal_analysis = buy_optimization.get("signal_analysis", {})

                        return OptimizationInsights(
                            trend_status=trend_confirmation.get("status", {}).get("value", "未知"),
                            expected_wait_days=trend_confirmation.get("expected_wait_days", 7.0),
                            right_side_signals_count=len(signal_analysis.get("right_side_signals", [])),
                            optimized_score=buy_optimization.get("optimized_score", 0.0),
                            position_strategy=position_strategy,
                            signal_quality=buy_optimization.get("signal_analysis", {}).get("signal_quality", "一般"),
                            buy_recommendation=buy_optimization.get("buy_recommendation", "持有")
                        )

            return None

        except Exception as e:
            logger.error(f"提取优化信息失败: {e}")
            return None

    def _calculate_traditional_decision(self, analyses: List[Dict]) -> Dict:
        """计算传统决策分数"""
        try:
            total_score = 0.0
            total_weight = 0.0
            analysis_summary = {}

            for analysis in analyses:
                analyst_type = analysis.get("analyst_type", "")
                confidence = analysis.get("confidence", 0.5)
                recommendation = analysis.get("recommendation", "持有")

                # 获取对应权重
                weight = self.base_weights.get(analyst_type, 0.1)

                # 根据建议调整分数
                rec_score = self._recommendation_to_score(recommendation)
                weighted_score = rec_score * confidence * weight

                total_score += weighted_score
                total_weight += weight

                analysis_summary[analyst_type] = {
                    "recommendation": recommendation,
                    "confidence": confidence,
                    "weight": weight,
                    "score": weighted_score
                }

            # 计算最终分数
            final_score = total_score / total_weight if total_weight > 0 else 0.5

            return {
                "score": final_score,
                "total_weight": total_weight,
                "analysis_summary": analysis_summary
            }

        except Exception as e:
            logger.error(f"计算传统决策失败: {e}")
            return {"score": 0.5, "total_weight": 1.0, "analysis_summary": {}}

    def _recommendation_to_score(self, recommendation: str) -> float:
        """将建议转换为分数"""
        score_map = {
            "强烈买入": 1.0,
            "买入": 0.8,
            "持有": 0.5,
            "卖出": 0.2,
            "强烈卖出": 0.0
        }
        return score_map.get(recommendation, 0.5)

    def _calculate_right_side_bonus(self, optimization_insights: Optional[OptimizationInsights]) -> Dict:
        """计算右侧交易加成"""
        if not optimization_insights:
            return {"total_bonus": 0.0, "bonus_breakdown": {}}

        bonus_breakdown = {}

        # 1. 趋势确认奖励
        trend_bonus = 0.0
        trend_status = optimization_insights.trend_status
        if "确认上涨" in trend_status:
            trend_bonus = self.right_side_bonus_weights["trend_confirmed"]
            bonus_breakdown["trend_confirmed"] = trend_bonus
        elif "早期上涨" in trend_status:
            trend_bonus = self.right_side_bonus_weights["trend_confirmed"] * 0.6
            bonus_breakdown["early_uptrend"] = trend_bonus

        # 2. 右侧信号数量奖励
        signal_bonus = 0.0
        right_signals = optimization_insights.right_side_signals_count
        if right_signals >= 2:
            signal_bonus = self.right_side_bonus_weights["right_side_signals"]
            bonus_breakdown["multiple_right_signals"] = signal_bonus
        elif right_signals >= 1:
            signal_bonus = self.right_side_bonus_weights["right_side_signals"] * 0.5
            bonus_breakdown["single_right_signal"] = signal_bonus

        # 3. 信号质量奖励
        quality_bonus = 0.0
        signal_quality = optimization_insights.signal_quality
        if signal_quality == "优秀":
            quality_bonus = self.right_side_bonus_weights["signal_quality"]
            bonus_breakdown["excellent_quality"] = quality_bonus
        elif signal_quality == "良好":
            quality_bonus = self.right_side_bonus_weights["signal_quality"] * 0.6
            bonus_breakdown["good_quality"] = quality_bonus

        # 4. 优化评分奖励
        score_bonus = optimization_insights.optimized_score * 0.1  # 10%的优化评分作为奖励
        if score_bonus > 0:
            bonus_breakdown["optimization_score"] = score_bonus

        total_bonus = trend_bonus + signal_bonus + quality_bonus + score_bonus

        return {
            "total_bonus": min(total_bonus, 0.3),  # 限制最大加成30%
            "bonus_breakdown": bonus_breakdown,
            "bonus_sources": list(bonus_breakdown.keys())
        }

    def _apply_risk_adjustment(self, traditional_score: float, right_side_bonus: Dict,
                             risk_assessment: Dict, optimization_insights: Optional[OptimizationInsights]) -> float:
        """应用风险调整"""
        try:
            # 基础分数
            adjusted_score = traditional_score

            # 应用右侧交易加成
            adjusted_score += right_side_bonus["total_bonus"]

            # 趋势风险调整
            if optimization_insights:
                trend_status = optimization_insights.trend_status
                if "强势下跌" in trend_status:
                    adjusted_score *= 0.6  # 强势下跌大幅扣分
                elif "弱势下跌" in trend_status:
                    adjusted_score *= 0.8  # 弱势下跌小幅扣分

            # 风险评估调整
            risk_level = risk_assessment.get("risk_level", "中")
            if risk_level == "高":
                adjusted_score *= 0.85
            elif risk_level == "低":
                adjusted_score *= 1.1

            # 限制分数范围
            return max(0.0, min(1.0, adjusted_score))

        except Exception as e:
            logger.error(f"风险调整失败: {e}")
            return traditional_score

    def _generate_final_decision(self, risk_adjusted_score: float,
                               optimization_insights: Optional[OptimizationInsights],
                               traditional_decision: Dict) -> Dict:
        """生成最终决策"""
        try:
            # 根据分数确定建议
            if risk_adjusted_score >= 0.8:
                recommendation = "强烈买入"
            elif risk_adjusted_score >= 0.65:
                recommendation = "买入"
            elif risk_adjusted_score >= 0.45:
                recommendation = "持有"
            elif risk_adjusted_score >= 0.3:
                recommendation = "谨慎"
            else:
                recommendation = "卖出"

            # 置信度计算
            confidence = min(0.95, risk_adjusted_score + 0.1)

            # 生成推理理由
            reasoning = []

            # 基础决策理由
            if risk_adjusted_score >= 0.7:
                reasoning.append(f"📊 综合评分{risk_adjusted_score:.2f}，表现优秀")
            elif risk_adjusted_score >= 0.5:
                reasoning.append(f"📈 综合评分{risk_adjusted_score:.2f}，表现良好")
            else:
                reasoning.append(f"⚠️ 综合评分{risk_adjusted_score:.2f}，信号较弱")

            # 优化洞察理由
            if optimization_insights:
                reasoning.append(f"🎯 趋势状态：{optimization_insights.trend_status}")
                reasoning.append(f"⚡ 右侧信号数量：{optimization_insights.right_side_signals_count}个")
                reasoning.append(f"💡 信号质量：{optimization_insights.signal_quality}")

                if optimization_insights.expected_wait_days <= 3:
                    reasoning.append("🚀 短期确认信号，等待时间较短")
                elif optimization_insights.expected_wait_days > 7:
                    reasoning.append(f"⏰ 预期等待时间较长：{optimization_insights.expected_wait_days:.1f}天")

            # 调整因素
            adjustment_factors = []
            if optimization_insights and optimization_insights.right_side_signals_count >= 2:
                adjustment_factors.append("右侧交易确认加成")
            if optimization_insights and "确认上涨" in optimization_insights.trend_status:
                adjustment_factors.append("趋势确认加成")

            return {
                "recommendation": recommendation,
                "confidence": confidence,
                "reasoning": reasoning,
                "adjustment_factors": adjustment_factors
            }

        except Exception as e:
            logger.error(f"生成最终决策失败: {e}")
            return {
                "recommendation": "持有",
                "confidence": 0.5,
                "reasoning": ["决策生成异常，采用保守策略"],
                "adjustment_factors": []
            }

    def _generate_execution_plan(self, final_decision: Dict,
                               optimization_insights: Optional[OptimizationInsights]) -> Dict:
        """生成执行计划"""
        try:
            recommendation = final_decision["recommendation"]
            confidence = final_decision["confidence"]

            plan = {
                "action": "观望",
                "urgency": "低",
                "position_sizing": "小仓位",
                "timing": "观察为主",
                "risk_management": ["严格止损", "控制仓位"]
            }

            if recommendation in ["强烈买入", "买入"]:
                plan["action"] = "建仓"
                plan["urgency"] = "高" if recommendation == "强烈买入" else "中"

                if optimization_insights:
                    position_strategy = optimization_insights.position_strategy
                    plan["position_sizing"] = f"{position_strategy.get('recommended_position', 0.1)*100:.0f}%"
                    plan["risk_level"] = position_strategy.get('risk_level', '中')

                    scaling_plan = position_strategy.get('scaling_plan', {})
                    if scaling_plan.get("strategy") == "分批建仓":
                        plan["timing"] = f"分批建仓 - {scaling_plan.get('time_horizon', '2周内')}"
                    else:
                        wait_days = optimization_insights.expected_wait_days
                        if wait_days <= 3:
                            plan["timing"] = "立即执行"
                        elif wait_days <= 7:
                            plan["timing"] = "1周内执行"
                        else:
                            plan["timing"] = "等待更好时机"

            elif recommendation == "持有":
                plan["action"] = "保持现有仓位"
                plan["urgency"] = "低"

            elif recommendation in ["谨慎", "卖出"]:
                plan["action"] = "减仓或观望"
                plan["urgency"] = "低"
                plan["position_sizing"] = "最小仓位或清仓"

            return plan

        except Exception as e:
            logger.error(f"生成执行计划失败: {e}")
            return {
                "action": "观望",
                "urgency": "低",
                "position_sizing": "保守",
                "timing": "进一步观察",
                "risk_management": ["严格控制风险"]
            }

    def _create_fallback_decision(self, symbol: str, analyses: List[Dict]) -> Dict:
        """创建备用决策"""
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "final_recommendation": "持有",
            "confidence": 0.5,
            "decision_score": 0.5,
            "reasoning": ["⚠️ 优化决策引擎异常，使用保守策略"],
            "traditional_analysis": {},
            "optimization_insights": None,
            "right_side_bonus": {"total_bonus": 0.0, "bonus_breakdown": {}},
            "risk_adjustment": {
                "original_score": 0.5,
                "adjusted_score": 0.5,
                "adjustment_factors": []
            },
            "position_strategy": {"recommended_position": 0.05, "risk_level": "高"},
            "execution_plan": {
                "action": "观望",
                "urgency": "低",
                "position_sizing": "保守",
                "timing": "等待系统恢复",
                "risk_management": ["严格控制风险"]
            }
        }