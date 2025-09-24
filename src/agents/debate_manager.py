# -*- coding: utf-8 -*-
"""
辩论管理器 - 协调看涨和看跌研究员的辩论，并做出最终决策
"""

import pandas as pd
from typing import Dict, List, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DebateManager:
    """辩论管理器 - 基于TradingAgents-CN的研究经理模式"""
    
    def __init__(self):
        self.agent_type = "debate_manager"
        self.decision_criteria = {
            "强烈买入": 0.8,
            "买入": 0.6,
            "持有": 0.4,
            "卖出": 0.2,
            "强烈卖出": 0.1
        }
    
    def conduct_debate_and_decide(self, symbol: str, bull_arguments: Dict, 
                                bear_arguments: Dict, market_context: Dict) -> Dict:
        """
        主持辩论并做出最终决策
        
        Args:
            symbol: 股票代码
            bull_arguments: 看涨研究员的论点
            bear_arguments: 看跌研究员的论点
            market_context: 市场背景信息
            
        Returns:
            最终投资决策
        """
        logger.info(f"🎯 辩论管理器开始主持 {symbol} 的投资辩论")
        
        debate_result = {
            "manager_type": "辩论管理器",
            "symbol": symbol,
            "debate_summary": {},
            "final_decision": {},
            "confidence_level": 0.5,
            "key_factors": [],
            "risk_assessment": {},
            "action_plan": {},
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            # 1. 总结双方论点
            debate_summary = self._summarize_debate(bull_arguments, bear_arguments)
            debate_result["debate_summary"] = debate_summary
            
            # 2. 评估论点强度
            argument_evaluation = self._evaluate_arguments(bull_arguments, bear_arguments)
            
            # 3. 结合市场背景
            contextual_factors = self._analyze_market_context(market_context, argument_evaluation)
            
            # 4. 做出最终决策
            final_decision = self._make_final_decision(
                argument_evaluation, contextual_factors, market_context
            )
            debate_result["final_decision"] = final_decision
            debate_result["confidence_level"] = final_decision["confidence"]
            
            # 5. 识别关键因素
            key_factors = self._identify_key_factors(bull_arguments, bear_arguments, final_decision)
            debate_result["key_factors"] = key_factors
            
            # 6. 风险评估
            risk_assessment = self._assess_risks(bull_arguments, bear_arguments, final_decision)
            debate_result["risk_assessment"] = risk_assessment
            
            # 7. 制定行动计划
            action_plan = self._create_action_plan(final_decision, risk_assessment, market_context)
            debate_result["action_plan"] = action_plan
            
            logger.info(f"🎯 辩论管理器决策完成: {symbol} -> {final_decision['action']} "
                       f"(信心度: {final_decision['confidence']:.2f})")
            
        except Exception as e:
            logger.error(f"辩论管理器决策失败 {symbol}: {e}")
            debate_result["final_decision"] = {
                "action": "持有",
                "confidence": 0.1,
                "reason": f"辩论过程出现错误: {str(e)}"
            }
        
        return debate_result
    
    def _summarize_debate(self, bull_args: Dict, bear_args: Dict) -> Dict:
        """总结辩论双方的主要观点"""
        return {
            "bull_summary": {
                "stance": bull_args.get("overall_stance", "看涨"),
                "confidence": bull_args.get("confidence", 0.5),
                "key_points": bull_args.get("key_arguments", [])[:3],
                "target_price": bull_args.get("target_price_range"),
                "core_thesis": bull_args.get("core_thesis", "")
            },
            "bear_summary": {
                "stance": bear_args.get("overall_stance", "看跌"), 
                "confidence": bear_args.get("confidence", 0.5),
                "key_points": bear_args.get("key_arguments", [])[:3],
                "target_price": bear_args.get("target_price_range"),
                "core_thesis": bear_args.get("core_thesis", "")
            },
            "debate_balance": self._calculate_debate_balance(bull_args, bear_args)
        }
    
    def _calculate_debate_balance(self, bull_args: Dict, bear_args: Dict) -> Dict:
        """计算辩论双方的力量对比"""
        bull_strength = len(bull_args.get("key_arguments", [])) * bull_args.get("confidence", 0.5)
        bear_strength = len(bear_args.get("key_arguments", [])) * bear_args.get("confidence", 0.5)
        
        total_strength = bull_strength + bear_strength
        if total_strength == 0:
            return {"bull_weight": 0.5, "bear_weight": 0.5, "balance": "均衡"}
        
        bull_weight = bull_strength / total_strength
        bear_weight = bear_strength / total_strength
        
        if bull_weight > 0.65:
            balance = "看涨占优"
        elif bear_weight > 0.65:
            balance = "看跌占优"
        else:
            balance = "势均力敌"
        
        return {
            "bull_weight": round(bull_weight, 3),
            "bear_weight": round(bear_weight, 3),
            "balance": balance
        }
    
    def _evaluate_arguments(self, bull_args: Dict, bear_args: Dict) -> Dict:
        """评估双方论点的强度和可信度"""
        
        # 看涨论点评估
        bull_evaluation = {
            "argument_count": len(bull_args.get("key_arguments", [])),
            "evidence_count": len(bull_args.get("supporting_evidence", [])),
            "confidence": bull_args.get("confidence", 0.5),
            "risk_awareness": len(bull_args.get("risk_acknowledgment", [])),
            "overall_strength": 0.0
        }
        
        # 看跌论点评估
        bear_evaluation = {
            "argument_count": len(bear_args.get("key_arguments", [])),
            "evidence_count": len(bear_args.get("supporting_evidence", [])),
            "confidence": bear_args.get("confidence", 0.5),
            "opportunity_awareness": len(bear_args.get("opportunity_acknowledgment", [])),
            "overall_strength": 0.0
        }
        
        # 计算综合强度
        bull_evaluation["overall_strength"] = (
            bull_evaluation["argument_count"] * 0.3 +
            bull_evaluation["evidence_count"] * 0.2 +
            bull_evaluation["confidence"] * 0.4 +
            bull_evaluation["risk_awareness"] * 0.1
        )
        
        bear_evaluation["overall_strength"] = (
            bear_evaluation["argument_count"] * 0.3 +
            bear_evaluation["evidence_count"] * 0.2 +
            bear_evaluation["confidence"] * 0.4 +
            bear_evaluation["opportunity_awareness"] * 0.1
        )
        
        return {
            "bull_evaluation": bull_evaluation,
            "bear_evaluation": bear_evaluation,
            "strength_difference": bull_evaluation["overall_strength"] - bear_evaluation["overall_strength"]
        }
    
    def _analyze_market_context(self, market_context: Dict, argument_eval: Dict) -> Dict:
        """分析市场背景对辩论结果的影响"""
        price_info = market_context.get("price_info", {})
        current_price = price_info.get("current_price", 0)
        daily_change_pct = price_info.get("daily_change_percent", 0)
        
        context_factors = {
            "price_momentum": "中性",
            "volatility_signal": "正常",
            "market_sentiment": "中性",
            "context_adjustment": 0.0
        }
        
        # 价格动量分析
        if daily_change_pct > 3:
            context_factors["price_momentum"] = "强势上涨"
            context_factors["context_adjustment"] += 0.05
        elif daily_change_pct < -3:
            context_factors["price_momentum"] = "显著下跌"
            context_factors["context_adjustment"] -= 0.05
        
        # 价格水平分析
        if current_price > 100:
            context_factors["price_level"] = "高价股"
            context_factors["context_adjustment"] -= 0.02  # 高价股风险稍高
        elif current_price < 10:
            context_factors["price_level"] = "低价股"
            context_factors["context_adjustment"] -= 0.02  # 低价股风险稍高
        else:
            context_factors["price_level"] = "中价股"
        
        return context_factors
    
    def _make_final_decision(self, argument_eval: Dict, context_factors: Dict, 
                           market_context: Dict) -> Dict:
        """做出最终投资决策"""
        
        # 获取双方强度
        bull_strength = argument_eval["bull_evaluation"]["overall_strength"]
        bear_strength = argument_eval["bear_evaluation"]["overall_strength"]
        strength_diff = argument_eval["strength_difference"]
        
        # 基础决策倾向
        base_score = 0.5 + (strength_diff * 0.3)  # 转换为0-1分数
        
        # 市场背景调整
        adjusted_score = base_score + context_factors.get("context_adjustment", 0)
        adjusted_score = max(0.0, min(1.0, adjusted_score))  # 限制在0-1范围
        
        # 确定最终行动
        if adjusted_score >= 0.75:
            action = "强烈买入"
        elif adjusted_score >= 0.65:
            action = "买入"
        elif adjusted_score >= 0.45:
            action = "持有"
        elif adjusted_score >= 0.25:
            action = "卖出"
        else:
            action = "强烈卖出"
        
        # 计算信心度
        confidence = max(abs(adjusted_score - 0.5) * 2, 0.1)  # 转换为信心度
        
        # 生成决策理由
        reason_parts = []
        
        if strength_diff > 0.2:
            reason_parts.append("看涨论点更具说服力")
        elif strength_diff < -0.2:
            reason_parts.append("看跌论点更具说服力")
        else:
            reason_parts.append("双方论点势均力敌")
        
        # 添加关键因素
        if bull_strength > bear_strength:
            bull_args = argument_eval["bull_evaluation"]
            if bull_args["argument_count"] > 2:
                reason_parts.append(f"看涨面有{bull_args['argument_count']}个支持因素")
        else:
            bear_args = argument_eval["bear_evaluation"]
            if bear_args["argument_count"] > 2:
                reason_parts.append(f"看跌面有{bear_args['argument_count']}个风险因素")
        
        # 市场背景影响
        if abs(context_factors.get("context_adjustment", 0)) > 0.02:
            reason_parts.append("已考虑市场背景因素")
        
        return {
            "action": action,
            "confidence": round(confidence, 3),
            "reason": " | ".join(reason_parts),
            "base_score": round(base_score, 3),
            "adjusted_score": round(adjusted_score, 3),
            "bull_strength": round(bull_strength, 3),
            "bear_strength": round(bear_strength, 3)
        }
    
    def _identify_key_factors(self, bull_args: Dict, bear_args: Dict, 
                            final_decision: Dict) -> List[str]:
        """识别影响决策的关键因素"""
        key_factors = []
        
        # 根据最终决策方向，优先显示相应的关键因素
        if final_decision["action"] in ["买入", "强烈买入"]:
            # 优先显示看涨因素
            bull_args_list = bull_args.get("key_arguments", [])
            key_factors.extend(bull_args_list[:2])
            
            # 也要提及主要风险
            bear_args_list = bear_args.get("key_arguments", [])
            if bear_args_list:
                key_factors.append(f"主要风险: {bear_args_list[0]}")
                
        elif final_decision["action"] in ["卖出", "强烈卖出"]:
            # 优先显示看跌因素
            bear_args_list = bear_args.get("key_arguments", [])
            key_factors.extend(bear_args_list[:2])
            
            # 也要提及潜在机会
            bull_args_list = bull_args.get("key_arguments", [])
            if bull_args_list:
                key_factors.append(f"潜在机会: {bull_args_list[0]}")
                
        else:  # 持有
            # 平衡显示双方观点
            bull_args_list = bull_args.get("key_arguments", [])
            bear_args_list = bear_args.get("key_arguments", [])
            
            if bull_args_list:
                key_factors.append(f"看涨: {bull_args_list[0]}")
            if bear_args_list:
                key_factors.append(f"看跌: {bear_args_list[0]}")
        
        return key_factors[:3]  # 最多3个关键因素
    
    def _assess_risks(self, bull_args: Dict, bear_args: Dict, 
                     final_decision: Dict) -> Dict:
        """评估投资风险"""
        
        risk_level = "中等"
        risk_factors = []
        
        # 基于决策信心度评估风险
        confidence = final_decision.get("confidence", 0.5)
        if confidence < 0.3:
            risk_level = "高"
            risk_factors.append("决策信心度较低")
        elif confidence > 0.8:
            risk_level = "低"
        
        # 从看跌论点中提取风险因素
        bear_args_list = bear_args.get("key_arguments", [])
        risk_factors.extend(bear_args_list[:2])
        
        # 市场系统性风险
        risk_factors.append("整体市场波动风险")
        
        return {
            "risk_level": risk_level,
            "risk_factors": risk_factors[:3],
            "confidence_risk": confidence < 0.5
        }
    
    def _create_action_plan(self, final_decision: Dict, risk_assessment: Dict, 
                          market_context: Dict) -> Dict:
        """制定具体的行动计划"""
        action = final_decision["action"]
        confidence = final_decision["confidence"]
        price_info = market_context.get("price_info", {})
        
        action_plan = {
            "primary_action": action,
            "execution_strategy": "",
            "position_sizing": "",
            "stop_loss": None,
            "take_profit": None,
            "monitoring_points": [],
            "review_timeline": "1个月"
        }
        
        # 执行策略
        if action in ["买入", "强烈买入"]:
            if confidence > 0.7:
                action_plan["execution_strategy"] = "可考虑分批建仓"
                action_plan["position_sizing"] = "标准仓位"
            else:
                action_plan["execution_strategy"] = "小仓位试探"
                action_plan["position_sizing"] = "轻仓"
                
        elif action in ["卖出", "强烈卖出"]:
            if confidence > 0.7:
                action_plan["execution_strategy"] = "建议及时减仓"
                action_plan["position_sizing"] = "大幅减仓"
            else:
                action_plan["execution_strategy"] = "观察确认后减仓"
                action_plan["position_sizing"] = "适度减仓"
        else:
            action_plan["execution_strategy"] = "维持现有仓位"
            action_plan["position_sizing"] = "保持不变"
        
        # 监控要点
        action_plan["monitoring_points"] = [
            "关注基本面数据变化",
            "监控技术指标信号", 
            "跟踪市场情绪变化"
        ]
        
        return action_plan