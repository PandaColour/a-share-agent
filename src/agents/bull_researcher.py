# -*- coding: utf-8 -*-
"""
看涨研究员 - 专注于挖掘股票的积极因素
"""

import pandas as pd
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class BullResearcher:
    """看涨研究员 - 专注于寻找买入理由"""
    
    def __init__(self):
        self.agent_type = "bull_researcher"
        self.focus_areas = [
            "业绩增长潜力",
            "技术突破信号", 
            "估值优势",
            "行业地位",
            "政策利好",
            "资金流入"
        ]
    
    def analyze_and_argue(self, symbol: str, analyses: List[Dict], 
                         market_data: Dict, price_info: Dict) -> Dict:
        """
        分析并提出看涨论点
        
        Args:
            symbol: 股票代码
            analyses: 各分析师的分析结果
            market_data: 市场数据
            price_info: 价格信息
            
        Returns:
            看涨论点和支持理由
        """
        logger.info(f"🐂 看涨研究员开始分析 {symbol}")
        
        bull_arguments = {
            "researcher_type": "看涨研究员",
            "overall_stance": "看涨",
            "confidence": 0.5,
            "key_arguments": [],
            "supporting_evidence": [],
            "risk_acknowledgment": [],
            "recommendation": "买入",
            "time_horizon": "3-6个月"
        }
        
        try:
            # 1. 从基本面寻找积极因素
            fundamental_bulls = self._find_fundamental_bulls(analyses)
            if fundamental_bulls:
                bull_arguments["key_arguments"].extend(fundamental_bulls["arguments"])
                bull_arguments["supporting_evidence"].extend(fundamental_bulls["evidence"])
                bull_arguments["confidence"] += fundamental_bulls["confidence_boost"]
            
            # 2. 从技术面寻找买入信号
            technical_bulls = self._find_technical_bulls(analyses, market_data)
            if technical_bulls:
                bull_arguments["key_arguments"].extend(technical_bulls["arguments"])
                bull_arguments["supporting_evidence"].extend(technical_bulls["evidence"])
                bull_arguments["confidence"] += technical_bulls["confidence_boost"]
            
            # 3. 从情感面寻找积极情绪
            sentiment_bulls = self._find_sentiment_bulls(analyses)
            if sentiment_bulls:
                bull_arguments["key_arguments"].extend(sentiment_bulls["arguments"])
                bull_arguments["supporting_evidence"].extend(sentiment_bulls["evidence"])
                bull_arguments["confidence"] += sentiment_bulls["confidence_boost"]
            
            # 4. 估算目标价格
            # 目标价格分析已移除
            
            # 5. 承认潜在风险 (保持客观)
            risks = self._acknowledge_risks(analyses, bull_arguments["confidence"])
            bull_arguments["risk_acknowledgment"] = risks
            
            # 6. 调整最终信心度
            bull_arguments["confidence"] = max(0.1, min(0.95, bull_arguments["confidence"]))
            
            # 7. 生成核心论点摘要
            core_thesis = self._generate_core_thesis(bull_arguments)
            bull_arguments["core_thesis"] = core_thesis
            
            logger.info(f"🐂 看涨研究员分析完成: {symbol}, 信心度: {bull_arguments['confidence']:.2f}")
            
        except Exception as e:
            logger.error(f"看涨研究员分析失败 {symbol}: {e}")
            bull_arguments["key_arguments"] = ["分析过程出现错误，无法提供可靠的看涨观点"]
            bull_arguments["confidence"] = 0.1
        
        return bull_arguments
    
    def _find_fundamental_bulls(self, analyses: List[Dict]) -> Dict:
        """从基本面分析中寻找看涨因素"""
        fundamental_analysis = None
        for analysis in analyses:
            if analysis.get("analyst_type") == "基本面分析":
                fundamental_analysis = analysis
                break
        
        if not fundamental_analysis:
            return None
        
        bull_factors = {
            "arguments": [],
            "evidence": [],
            "confidence_boost": 0.0
        }
        
        # 检查推荐结果
        if fundamental_analysis.get("recommendation") == "买入":
            bull_factors["confidence_boost"] += 0.15
            bull_factors["arguments"].append("基本面分析支持买入")
        
        # 分析推理内容
        reasoning = fundamental_analysis.get("reasoning", [])
        for reason in reasoning:
            if any(keyword in reason for keyword in ["PE比率", "较低", "便宜", "低估"]):
                bull_factors["arguments"].append("估值具有吸引力")
                bull_factors["evidence"].append(f"基本面: {reason}")
                bull_factors["confidence_boost"] += 0.08
                
            elif any(keyword in reason for keyword in ["大盘股", "流动性", "稳定"]):
                bull_factors["arguments"].append("流动性和稳定性优势")
                bull_factors["evidence"].append(f"基本面: {reason}")
                bull_factors["confidence_boost"] += 0.05
                
            elif any(keyword in reason for keyword in ["财务", "业绩", "盈利", "营收"]):
                bull_factors["arguments"].append("财务指标健康")
                bull_factors["evidence"].append(f"基本面: {reason}")
                bull_factors["confidence_boost"] += 0.1
        
        return bull_factors if bull_factors["arguments"] else None
    
    def _find_technical_bulls(self, analyses: List[Dict], market_data: Dict) -> Dict:
        """从技术面分析中寻找看涨信号"""
        technical_analysis = None
        for analysis in analyses:
            if analysis.get("analyst_type") == "技术面分析":
                technical_analysis = analysis
                break
        
        if not technical_analysis:
            return None
        
        bull_factors = {
            "arguments": [],
            "evidence": [],
            "confidence_boost": 0.0
        }
        
        # 检查推荐结果
        if technical_analysis.get("recommendation") == "买入":
            bull_factors["confidence_boost"] += 0.12
            bull_factors["arguments"].append("技术指标显示买入信号")
        
        # 分析推理内容
        reasoning = technical_analysis.get("reasoning", [])
        for reason in reasoning:
            if any(keyword in reason for keyword in ["强势", "上升", "突破", "看涨"]):
                bull_factors["arguments"].append("技术形态积极")
                bull_factors["evidence"].append(f"技术面: {reason}")
                bull_factors["confidence_boost"] += 0.08
                
            elif any(keyword in reason for keyword in ["成交量", "放大", "活跃"]):
                bull_factors["arguments"].append("成交量配合良好")
                bull_factors["evidence"].append(f"技术面: {reason}")
                bull_factors["confidence_boost"] += 0.06
                
            elif "超卖" in reason:
                bull_factors["arguments"].append("技术指标显示超卖，存在反弹机会")
                bull_factors["evidence"].append(f"技术面: {reason}")
                bull_factors["confidence_boost"] += 0.1
        
        return bull_factors if bull_factors["arguments"] else None
    
    def _find_sentiment_bulls(self, analyses: List[Dict]) -> Dict:
        """从情感面分析中寻找积极情绪"""
        sentiment_analysis = None
        for analysis in analyses:
            if analysis.get("analyst_type") == "情感面分析":
                sentiment_analysis = analysis
                break
        
        if not sentiment_analysis:
            return None
        
        bull_factors = {
            "arguments": [],
            "evidence": [],
            "confidence_boost": 0.0
        }
        
        # 检查推荐结果
        if sentiment_analysis.get("recommendation") == "买入":
            bull_factors["confidence_boost"] += 0.1
            bull_factors["arguments"].append("市场情绪积极")
        
        # 检查新闻情感
        if sentiment_analysis.get("news_sentiment") == "积极":
            bull_factors["arguments"].append("新闻面释放积极信号")
            bull_factors["evidence"].append(f"新闻情感: 积极 ({sentiment_analysis.get('news_count', 0)}条新闻)")
            bull_factors["confidence_boost"] += 0.08
        
        # 分析推理内容
        reasoning = sentiment_analysis.get("reasoning", [])
        for reason in reasoning:
            if any(keyword in reason for keyword in ["涨势", "良好", "看好", "超预期"]):
                bull_factors["arguments"].append("情绪指标支持上涨")
                bull_factors["evidence"].append(f"情感面: {reason}")
                bull_factors["confidence_boost"] += 0.06
                
            elif "新闻" in reason and any(pos in reason for pos in ["积极", "利好", "超预期"]):
                bull_factors["arguments"].append("新闻面利好因素增加")
                bull_factors["evidence"].append(f"情感面: {reason}")
                bull_factors["confidence_boost"] += 0.05
        
        return bull_factors if bull_factors["arguments"] else None
    
    
    def _acknowledge_risks(self, analyses: List[Dict], confidence: float) -> List[str]:
        """承认潜在风险 (保持客观性)"""
        risks = []
        
        # 从各分析中提取风险因素
        for analysis in analyses:
            reasoning = analysis.get("reasoning", [])
            for reason in reasoning:
                if any(keyword in reason for keyword in ["风险", "下跌", "疲软", "压力"]):
                    risks.append(f"需关注: {reason}")
        
        # 根据信心度添加通用风险提示
        if confidence < 0.7:
            risks.append("当前证据支撑力度有限，需密切观察后续发展")
        
        if not risks:
            risks.append("虽然看涨，但仍需关注市场整体波动风险")
        
        return risks[:3]  # 最多显示3个主要风险
    
    def _generate_core_thesis(self, arguments: Dict) -> str:
        """生成核心投资论点"""
        key_args = arguments.get("key_arguments", [])
        confidence = arguments.get("confidence", 0.5)
        
        if not key_args:
            return "基于当前分析，暂未发现强有力的看涨理由。"
        
        # 构建核心论点
        if confidence >= 0.8:
            strength = "强烈"
        elif confidence >= 0.6:
            strength = "相对"
        else:
            strength = "谨慎"
            
        top_args = key_args[:3]  # 取前3个主要论点
        
        thesis = f"基于{len(key_args)}个积极因素，{strength}看涨该股。"
        thesis += f"主要支撑包括：{' | '.join(top_args)}。"
        
        # 目标价格分析已移除
        
        return thesis