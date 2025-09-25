# -*- coding: utf-8 -*-
"""投资组合经理"""

from datetime import datetime
from typing import Dict, List
from utils.decision import TradingDecision
from .bull_researcher import BullResearcher
from .bear_researcher import BearResearcher
from .debate_manager import DebateManager
from .multi_round_debate_manager import MultiRoundDebateManager
import logging

# 目标价格分析器已移除，使用基础价格区间分析

logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self):
        # 内部初始化配置管理器，简化依赖传递
        from config.config_manager import get_config
        self.config_manager = get_config()
        self.decision_weights = {
            "基本面分析": 0.4,
            "技术面分析": 0.35,
            "情感面分析": 0.25
        }
        # 初始化辩论系统组件
        self.bull_researcher = BullResearcher()
        self.bear_researcher = BearResearcher()
        self.debate_manager = DebateManager()
        # 新的多轮辩论系统
        self.multi_round_debate_manager = MultiRoundDebateManager(self.config_manager)
        self.enable_debate = True  # 可配置是否启用辩论模式
        self.use_multi_round_debate = True  # 是否使用多轮辩论（默认启用）
        
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
            if self.use_multi_round_debate and self.config_manager:
                logger.info(f"🎯 启用多轮辩论模式进行决策: {symbol}")
                return self._make_decision_with_multi_round_debate(symbol, analyses, risk_assessment, price_info)
            else:
                logger.info(f"🎯 启用传统辩论模式进行决策: {symbol}")
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

    def _make_decision_with_multi_round_debate(self, symbol: str, analyses: List[Dict],
                                             risk_assessment: Dict, price_info: Dict) -> TradingDecision:
        """基于多轮辩论的决策模式 (新的AI多轮辩论)"""
        try:
            # 获取公司名称
            company_name = symbol  # 可以从数据源获取实际公司名称

            # 准备市场数据
            market_data = {
                "current_price": price_info.get("current_price", 0.0),
                "daily_change_pct": price_info.get("daily_change_percent", 0.0),
                "volume": price_info.get("volume", 0),
                "price_info": price_info,
                "technical_indicators": {}
            }

            # 从技术面分析中提取技术指标
            for analysis in analyses:
                if analysis.get("analyst_type") == "技术面分析":
                    # 提取技术指标数据
                    reasoning = analysis.get("reasoning", [])
                    for reason in reasoning:
                        if "MA5" in str(reason):
                            # 简单提取，实际可能需要更复杂的解析
                            market_data["technical_indicators"]["MA5"] = 0
                        if "RSI" in str(reason):
                            market_data["technical_indicators"]["RSI"] = 50

            logger.info(f"🎯 开始多轮辩论决策: {symbol}({company_name})")

            # 执行多轮辩论
            debate_result = self.multi_round_debate_manager.conduct_multi_round_debate(
                symbol=symbol,
                company_name=company_name,
                analyses=analyses,
                market_data=market_data,
                risk_assessment=risk_assessment
            )

            # 提取最终决策
            final_decision = debate_result.get("final_decision", {})
            debate_summary = debate_result.get("debate_summary", {})
            key_factors = debate_result.get("key_factors", [])
            confidence_level = debate_result.get("confidence_level", 0.5)

            # 构建决策理由
            reason_parts = [final_decision.get("reason", "")]

            # 添加辩论轮次信息
            total_rounds = debate_summary.get("total_exchanges", 0)
            if total_rounds > 0:
                reason_parts.append(f"经过{total_rounds}轮辩论")

            # 添加关键因素
            if key_factors:
                reason_parts.append(f"关键因素: {key_factors[0]}")

            decision = TradingDecision(
                action=final_decision.get("action", "持有"),
                confidence=confidence_level,
                reason=" | ".join(filter(None, reason_parts)),
                risk_level=risk_assessment.get("risk_level", "中等"),
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                current_price=price_info.get("current_price", 0.0),
                daily_high=price_info.get("daily_high", 0.0),
                daily_low=price_info.get("daily_low", 0.0),
                daily_change=price_info.get("daily_change", 0.0),
                daily_change_percent=price_info.get("daily_change_percent", 0.0)
            )

            # 添加多轮辩论特有信息
            logger.info(f"🔍 开始保存多轮辩论结果: {symbol}")
            logger.info(f"🔍 辩论结果对象类型: {type(debate_result)}, 是否为空: {debate_result is None}")
            logger.info(f"🔍 辩论轮次数量: {len(debate_result.get('debate_rounds', []))}")

            decision.multi_round_debate_result = debate_result
            decision.debate_rounds = debate_result.get("debate_rounds", [])
            decision.key_factors = key_factors
            decision.debate_quality = debate_summary.get("debate_quality", "未知")
            decision.final_speaker = debate_summary.get("final_speaker", "")

            logger.info(f"✅ 多轮辩论信息已设置到decision对象: {symbol}")
            logger.info(f"🔍 decision.multi_round_debate_result 是否为空: {decision.multi_round_debate_result is None}")

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

            logger.info(f"🏁 多轮辩论决策完成 {symbol}: {decision.action} (信心度: {decision.confidence:.3f}, 轮次: {total_rounds})")

            return decision

        except Exception as e:
            logger.error(f"多轮辩论决策失败 {symbol}: {e}")
            # 回退到传统辩论模式
            logger.warning(f"回退到传统辩论模式: {symbol}")
            return self._make_decision_with_debate(symbol, analyses, risk_assessment, price_info)
    
    def set_debate_mode(self, enabled: bool, multi_round: bool = True):
        """设置是否启用辩论模式"""
        self.enable_debate = enabled
        self.use_multi_round_debate = multi_round
        debate_type = "多轮辩论" if multi_round else "传统辩论"
        logger.info(f"辩论模式{'启用' if enabled else '禁用'} ({debate_type})")
    
    def get_debate_summary(self, decision: TradingDecision) -> Dict:
        """获取辩论摘要（如果有的话）"""
        # 检查是否有多轮辩论结果
        if hasattr(decision, 'multi_round_debate_result'):
            debate_result = decision.multi_round_debate_result
            return {
                "debate_enabled": True,
                "debate_type": "multi_round",
                "manager_type": debate_result.get("manager_type", "多轮辩论管理器"),
                "total_rounds": len(debate_result.get("debate_rounds", [])),
                "debate_summary": debate_result.get("debate_summary", {}),
                "final_decision": debate_result.get("final_decision", {}),
                "key_factors": debate_result.get("key_factors", []),
                "debate_quality": decision.debate_quality,
                "final_speaker": decision.final_speaker,
                "debate_rounds": decision.debate_rounds
            }
        # 检查传统辩论结果
        elif hasattr(decision, 'debate_summary'):
            return {
                "debate_enabled": True,
                "debate_type": "traditional",
                "debate_summary": decision.debate_summary,
                "bull_thesis": decision.bull_arguments,
                "bear_thesis": decision.bear_arguments,
                "key_factors": decision.key_factors
            }
        else:
            return {"debate_enabled": False}

    def get_multi_round_debate_status(self) -> Dict:
        """获取多轮辩论系统状态"""
        if hasattr(self, 'multi_round_debate_manager'):
            return self.multi_round_debate_manager.get_debate_status()
        else:
            return {"status": "未初始化"}

    def reset_debate_state(self):
        """重置辩论状态"""
        if hasattr(self, 'multi_round_debate_manager'):
            self.multi_round_debate_manager.reset_debate()
            logger.info("多轮辩论状态已重置")
    
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
