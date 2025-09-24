# -*- coding: utf-8 -*-
"""投资组合经理"""

from datetime import datetime
from typing import Dict, List
from utils.decision import TradingDecision
from .bull_researcher import BullResearcher
from .bear_researcher import BearResearcher
from .debate_manager import DebateManager
import logging

# 目标价格分析器已移除，使用基础价格区间分析

logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self):
        self.decision_weights = {
            "基本面分析": 0.4,
            "技术面分析": 0.35,
            "情感面分析": 0.25
        }
        # 初始化辩论系统组件
        self.bull_researcher = BullResearcher()
        self.bear_researcher = BearResearcher()
        self.debate_manager = DebateManager()
        self.enable_debate = True  # 可配置是否启用辩论模式
        
        # 初始化目标价格分析器
        # 目标价格分析器已移除，改用基础价格区间分析
        logger.info("投资组合管理器初始化完成，使用基础价格区间分析")
        
    def make_decision(self, symbol: str, analyses: List[Dict], risk_assessment: Dict, price_info: Dict = None) -> TradingDecision:
        """
        增强决策方法 - 支持传统模式和辩论模式
        """
        if price_info is None:
            price_info = {}
            
        # 选择决策模式
        if self.enable_debate and len(analyses) >= 2:
            logger.info(f"🎯 启用辩论模式进行决策: {symbol}")
            return self._make_decision_with_debate(symbol, analyses, risk_assessment, price_info)
        else:
            logger.info(f"📊 使用传统模式进行决策: {symbol}")
            return self._make_traditional_decision(symbol, analyses, risk_assessment, price_info)
    
    def _make_traditional_decision(self, symbol: str, analyses: List[Dict], 
                                 risk_assessment: Dict, price_info: Dict) -> TradingDecision:
        """传统决策模式 (原逻辑)"""
        # 计算加权信心度
        weighted_confidence = 0
        recommendation_scores = {"买入": 0, "持有": 0, "卖出": 0}
        
        for analysis in analyses:
            analyst_type = analysis.get("analyst_type", "")
            confidence = analysis.get("confidence", 0.5)
            recommendation = analysis.get("recommendation", "持有")
            weight = self.decision_weights.get(analyst_type, 0.33)
            
            weighted_confidence += confidence * weight
            recommendation_scores[recommendation] += weight
        
        # 确定最终推荐
        final_recommendation = max(recommendation_scores.items(), key=lambda x: x[1])[0]
        
        # 风险调整
        risk_score = risk_assessment.get("risk_score", 0.5)
        adjusted_confidence = weighted_confidence * (1 - risk_score * 0.3)
        
        # 生成决策理由
        reasons = []
        for analysis in analyses:
            reasons.extend(analysis.get("reasoning", []))
        reasons.extend(risk_assessment.get("risk_factors", []))
        
        decision = TradingDecision(
            action=final_recommendation,
            confidence=max(0, min(1, adjusted_confidence)),
            reason=" | ".join(reasons[:3]),
            risk_level=risk_assessment.get("risk_level", "中等"),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            current_price=price_info.get("current_price", 0.0),
            daily_high=price_info.get("daily_high", 0.0),
            daily_low=price_info.get("daily_low", 0.0),
            daily_change=price_info.get("daily_change", 0.0),
            daily_change_percent=price_info.get("daily_change_percent", 0.0)
        )

        # 基于分析结果计算基础价格区间
        current_price = price_info.get("current_price", 0.0)
        if current_price > 0:
            # 基于技术面和基本面分析估算价格区间
            price_range = self._estimate_price_range_from_analyses(analyses, current_price)
            if price_range:
                decision.price_range_low = price_range.get("low", 0.0)
                decision.price_range_high = price_range.get("high", 0.0)
                # 计算上涨空间
                if price_range.get("high", 0) > current_price:
                    decision.upside_potential = (price_range["high"] - current_price) / current_price * 100
        
        return decision
    
    def _make_decision_with_debate(self, symbol: str, analyses: List[Dict], 
                                  risk_assessment: Dict, price_info: Dict) -> TradingDecision:
        """基于辩论的决策模式 (新功能)"""
        try:
            # 准备市场数据
            market_data = {
                "indicators": {},  # 技术指标数据
                "price_info": price_info,
                "risk_assessment": risk_assessment
            }
            
            # 看涨研究员分析
            logger.debug(f"🐂 看涨研究员开始分析 {symbol}")
            bull_arguments = self.bull_researcher.analyze_and_argue(
                symbol, analyses, market_data, price_info
            )
            
            # 看跌研究员分析
            logger.debug(f"🐻 看跌研究员开始分析 {symbol}")
            bear_arguments = self.bear_researcher.analyze_and_argue(
                symbol, analyses, market_data, price_info
            )
            
            # 辩论管理器主持辩论并决策
            logger.debug(f"🎯 辩论管理器开始主持辩论 {symbol}")
            debate_result = self.debate_manager.conduct_debate_and_decide(
                symbol, bull_arguments, bear_arguments, market_data
            )
            
            # 转换为TradingDecision格式
            final_decision = debate_result["final_decision"]
            key_factors = debate_result.get("key_factors", [])
            risk_assessment_result = debate_result.get("risk_assessment", {})
            
            # 构建决策理由
            debate_summary = debate_result.get("debate_summary", {})
            balance = debate_summary.get("debate_balance", {})
            
            reason_parts = [final_decision.get("reason", "")]
            if balance.get("balance"):
                reason_parts.append(f"辩论结果: {balance['balance']}")
            if key_factors:
                reason_parts.append(f"关键因素: {key_factors[0]}")
                
            decision = TradingDecision(
                action=final_decision.get("action", "持有"),
                confidence=final_decision.get("confidence", 0.5),
                reason=" | ".join(filter(None, reason_parts)),
                risk_level=risk_assessment_result.get("risk_level", "中等"),
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                current_price=price_info.get("current_price", 0.0),
                daily_high=price_info.get("daily_high", 0.0),
                daily_low=price_info.get("daily_low", 0.0),
                daily_change=price_info.get("daily_change", 0.0),
                daily_change_percent=price_info.get("daily_change_percent", 0.0)
            )
            
            # 添加辩论特有信息
            decision.debate_summary = debate_summary
            decision.bull_arguments = bull_arguments.get("core_thesis", "")
            decision.bear_arguments = bear_arguments.get("core_thesis", "")
            decision.key_factors = key_factors
            
            # 基于分析结果计算基础价格区间
            current_price = price_info.get("current_price", 0.0)
            if current_price > 0:
                price_range = self._estimate_price_range_from_analyses(analyses, current_price)
                if price_range:
                    decision.price_range_low = price_range.get("low", 0.0)
                    decision.price_range_high = price_range.get("high", 0.0)
                    # 计算上涨空间
                    if price_range.get("high", 0) > current_price:
                        decision.upside_potential = (price_range["high"] - current_price) / current_price * 100
            
            logger.info(f"🎯 辩论决策完成 {symbol}: {decision.action} (信心度: {decision.confidence:.2f})")
            
            return decision
            
        except Exception as e:
            logger.error(f"辩论决策失败 {symbol}: {e}")
            # 返回决策失败结果
            return TradingDecision(
                action="无法决策",
                confidence=0.0,
                reason=f"辩论决策系统失败: {str(e)}",
                risk_level="未知",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
    
    def set_debate_mode(self, enabled: bool):
        """设置是否启用辩论模式"""
        self.enable_debate = enabled
        logger.info(f"辩论模式{'启用' if enabled else '禁用'}")
    
    def get_debate_summary(self, decision: TradingDecision) -> Dict:
        """获取辩论摘要（如果有的话）"""
        if hasattr(decision, 'debate_summary'):
            return {
                "debate_enabled": True,
                "debate_summary": decision.debate_summary,
                "bull_thesis": decision.bull_arguments,
                "bear_thesis": decision.bear_arguments,
                "key_factors": decision.key_factors
            }
        else:
            return {"debate_enabled": False}
    
    def _estimate_price_range_from_analyses(self, analyses: List[Dict], current_price: float) -> Dict:
        """基于分析结果估算价格区间"""
        if current_price <= 0:
            return None

        # 收集各分析师的置信度
        confidences = []
        recommendations = []

        for analysis in analyses:
            confidence = analysis.get("confidence", 0.5)
            recommendation = analysis.get("recommendation", "持有")
            confidences.append(confidence)
            recommendations.append(recommendation)

        # 计算平均置信度
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        # 基于推荐计算买入倾向
        buy_count = sum(1 for r in recommendations if "买入" in r)
        sell_count = sum(1 for r in recommendations if "卖出" in r)
        total = len(recommendations)

        # 计算价格区间
        if buy_count > sell_count:
            # 偏向买入，设置较高的价格区间
            low = current_price * (1 - 0.05 * (1 - avg_confidence))
            high = current_price * (1 + 0.15 * avg_confidence)
        elif sell_count > buy_count:
            # 偏向卖出，设置较低的价格区间
            low = current_price * (1 - 0.15 * avg_confidence)
            high = current_price * (1 + 0.05 * (1 - avg_confidence))
        else:
            # 中性，设置对称区间
            range_factor = 0.1 * avg_confidence
            low = current_price * (1 - range_factor)
            high = current_price * (1 + range_factor)

        return {
            "low": round(low, 2),
            "high": round(high, 2),
            "confidence": avg_confidence
        }
