# -*- coding: utf-8 -*-
"""
看跌研究员 - 专注于识别股票的风险和负面因素
"""

import pandas as pd
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class BearResearcher:
    """看跌研究员 - 专注于寻找卖出理由"""
    
    def __init__(self):
        self.agent_type = "bear_researcher"
        self.focus_areas = [
            "估值风险",
            "技术破位信号",
            "业绩恶化",
            "行业逆风",
            "政策风险",
            "资金流出"
        ]
    
    def analyze_and_argue(self, symbol: str, analyses: List[Dict], 
                         market_data: Dict, price_info: Dict) -> Dict:
        """
        分析并提出看跌论点
        
        Args:
            symbol: 股票代码
            analyses: 各分析师的分析结果
            market_data: 市场数据
            price_info: 价格信息
            
        Returns:
            看跌论点和支持理由
        """
        logger.info(f"🐻 看跌研究员开始分析 {symbol}")
        
        bear_arguments = {
            "researcher_type": "看跌研究员",
            "overall_stance": "看跌",
            "confidence": 0.5,
            "key_arguments": [],
            "supporting_evidence": [],
            "opportunity_acknowledgment": [],
            "recommendation": "卖出",
            "time_horizon": "1-3个月"
        }
        
        try:
            # 1. 从基本面寻找风险因素
            fundamental_bears = self._find_fundamental_bears(analyses)
            if fundamental_bears:
                bear_arguments["key_arguments"].extend(fundamental_bears["arguments"])
                bear_arguments["supporting_evidence"].extend(fundamental_bears["evidence"])
                bear_arguments["confidence"] += fundamental_bears["confidence_boost"]
            
            # 2. 从技术面寻找卖出信号
            technical_bears = self._find_technical_bears(analyses, market_data)
            if technical_bears:
                bear_arguments["key_arguments"].extend(technical_bears["arguments"])
                bear_arguments["supporting_evidence"].extend(technical_bears["evidence"])
                bear_arguments["confidence"] += technical_bears["confidence_boost"]
            
            # 3. 从情感面寻找负面情绪
            sentiment_bears = self._find_sentiment_bears(analyses)
            if sentiment_bears:
                bear_arguments["key_arguments"].extend(sentiment_bears["arguments"])
                bear_arguments["supporting_evidence"].extend(sentiment_bears["evidence"])
                bear_arguments["confidence"] += sentiment_bears["confidence_boost"]
            
            # 4. 估算目标价格
            # 目标价格分析已移除
            
            # 5. 承认潜在机会 (保持客观)
            opportunities = self._acknowledge_opportunities(analyses, bear_arguments["confidence"])
            bear_arguments["opportunity_acknowledgment"] = opportunities
            
            # 6. 调整最终信心度
            bear_arguments["confidence"] = max(0.1, min(0.95, bear_arguments["confidence"]))
            
            # 7. 生成核心论点摘要
            core_thesis = self._generate_core_thesis(bear_arguments)
            bear_arguments["core_thesis"] = core_thesis
            
            logger.info(f"🐻 看跌研究员分析完成: {symbol}, 信心度: {bear_arguments['confidence']:.2f}")
            
        except Exception as e:
            logger.error(f"看跌研究员分析失败 {symbol}: {e}")
            bear_arguments["key_arguments"] = ["分析过程出现错误，无法提供可靠的看跌观点"]
            bear_arguments["confidence"] = 0.1
        
        return bear_arguments
    
    def _find_fundamental_bears(self, analyses: List[Dict]) -> Dict:
        """从基本面分析中寻找看跌因素"""
        fundamental_analysis = None
        for analysis in analyses:
            if analysis.get("analyst_type") == "基本面分析":
                fundamental_analysis = analysis
                break
        
        if not fundamental_analysis:
            return None
        
        bear_factors = {
            "arguments": [],
            "evidence": [],
            "confidence_boost": 0.0
        }
        
        # 检查推荐结果
        if fundamental_analysis.get("recommendation") == "卖出":
            bear_factors["confidence_boost"] += 0.15
            bear_factors["arguments"].append("基本面分析建议卖出")
        
        # 分析推理内容寻找负面因素
        reasoning = fundamental_analysis.get("reasoning", [])
        for reason in reasoning:
            if any(keyword in reason for keyword in ["高估", "昂贵", "PE过高", "估值偏高"]):
                bear_factors["arguments"].append("估值存在泡沫风险")
                bear_factors["evidence"].append(f"基本面: {reason}")
                bear_factors["confidence_boost"] += 0.1
                
            elif any(keyword in reason for keyword in ["财务恶化", "业绩下滑", "亏损"]):
                bear_factors["arguments"].append("财务状况令人担忧")
                bear_factors["evidence"].append(f"基本面: {reason}")
                bear_factors["confidence_boost"] += 0.12
                
            elif any(keyword in reason for keyword in ["债务", "负债", "现金流"]):
                bear_factors["arguments"].append("资金链存在压力")
                bear_factors["evidence"].append(f"基本面: {reason}")
                bear_factors["confidence_boost"] += 0.08
        
        # 如果基本面信心度过低，也是负面信号
        confidence = fundamental_analysis.get("confidence", 0.5)
        if confidence < 0.3:
            bear_factors["arguments"].append("基本面分析信心度不足")
            bear_factors["evidence"].append(f"基本面信心度仅{confidence:.1%}")
            bear_factors["confidence_boost"] += 0.06
        
        return bear_factors if bear_factors["arguments"] else None
    
    def _find_technical_bears(self, analyses: List[Dict], market_data: Dict) -> Dict:
        """从技术面分析中寻找看跌信号"""
        technical_analysis = None
        for analysis in analyses:
            if analysis.get("analyst_type") == "技术面分析":
                technical_analysis = analysis
                break
        
        if not technical_analysis:
            return None
        
        bear_factors = {
            "arguments": [],
            "evidence": [],
            "confidence_boost": 0.0
        }
        
        # 检查推荐结果
        if technical_analysis.get("recommendation") == "卖出":
            bear_factors["confidence_boost"] += 0.12
            bear_factors["arguments"].append("技术指标发出卖出信号")
        
        # 分析推理内容寻找负面因素
        reasoning = technical_analysis.get("reasoning", [])
        for reason in reasoning:
            if any(keyword in reason for keyword in ["疲软", "下跌", "破位", "看跌"]):
                bear_factors["arguments"].append("技术形态恶化")
                bear_factors["evidence"].append(f"技术面: {reason}")
                bear_factors["confidence_boost"] += 0.08
                
            elif "超买" in reason:
                bear_factors["arguments"].append("技术指标显示超买，存在调整风险")
                bear_factors["evidence"].append(f"技术面: {reason}")
                bear_factors["confidence_boost"] += 0.1
                
            elif any(keyword in reason for keyword in ["成交量萎缩", "量能不足"]):
                bear_factors["arguments"].append("成交量无法支撑上涨")
                bear_factors["evidence"].append(f"技术面: {reason}")
                bear_factors["confidence_boost"] += 0.07
        
        return bear_factors if bear_factors["arguments"] else None
    
    def _find_sentiment_bears(self, analyses: List[Dict]) -> Dict:
        """从情感面分析中寻找负面情绪"""
        sentiment_analysis = None
        for analysis in analyses:
            if analysis.get("analyst_type") == "情感面分析":
                sentiment_analysis = analysis
                break
        
        if not sentiment_analysis:
            return None
        
        bear_factors = {
            "arguments": [],
            "evidence": [],
            "confidence_boost": 0.0
        }
        
        # 检查推荐结果
        if sentiment_analysis.get("recommendation") == "卖出":
            bear_factors["confidence_boost"] += 0.1
            bear_factors["arguments"].append("市场情绪转向悲观")
        
        # 检查新闻情感
        if sentiment_analysis.get("news_sentiment") == "消极":
            bear_factors["arguments"].append("新闻面释放负面信号")
            bear_factors["evidence"].append(f"新闻情感: 消极 ({sentiment_analysis.get('news_count', 0)}条新闻)")
            bear_factors["confidence_boost"] += 0.08
        
        # 分析推理内容
        reasoning = sentiment_analysis.get("reasoning", [])
        for reason in reasoning:
            if any(keyword in reason for keyword in ["跌幅", "较大", "下滑", "恶化"]):
                bear_factors["arguments"].append("市场情绪指标转弱")
                bear_factors["evidence"].append(f"情感面: {reason}")
                bear_factors["confidence_boost"] += 0.06
                
            elif "新闻" in reason and any(neg in reason for neg in ["消极", "负面", "风险", "警告"]):
                bear_factors["arguments"].append("新闻面风险因素增加")
                bear_factors["evidence"].append(f"情感面: {reason}")
                bear_factors["confidence_boost"] += 0.05
        
        return bear_factors if bear_factors["arguments"] else None
    
    
    def _acknowledge_opportunities(self, analyses: List[Dict], confidence: float) -> List[str]:
        """承认潜在机会 (保持客观性)"""
        opportunities = []
        
        # 从各分析中提取积极因素
        for analysis in analyses:
            reasoning = analysis.get("reasoning", [])
            for reason in reasoning:
                if any(keyword in reason for keyword in ["机会", "反弹", "支撑", "便宜"]):
                    opportunities.append(f"潜在机会: {reason}")
                    
            # 检查是否有买入推荐
            if analysis.get("recommendation") == "买入":
                opportunities.append(f"{analysis.get('analyst_type', '分析师')}建议买入")
        
        # 根据信心度添加通用机会提示
        if confidence < 0.7:
            opportunities.append("如果风险因素得到缓解，可能存在反弹机会")
        
        if not opportunities:
            opportunities.append("尽管看跌，但需关注是否出现超跌反弹机会")
        
        return opportunities[:3]  # 最多显示3个主要机会
    
    def _generate_core_thesis(self, arguments: Dict) -> str:
        """生成核心投资论点"""
        key_args = arguments.get("key_arguments", [])
        confidence = arguments.get("confidence", 0.5)
        
        if not key_args:
            return "基于当前分析，暂未发现明显的看跌理由。"
        
        # 构建核心论点
        if confidence >= 0.8:
            strength = "强烈"
        elif confidence >= 0.6:
            strength = "相对"
        else:
            strength = "谨慎"
            
        top_args = key_args[:3]  # 取前3个主要论点
        
        thesis = f"基于{len(key_args)}个风险因素，{strength}看跌该股。"
        thesis += f"主要担忧包括：{' | '.join(top_args)}。"
        
        # 目标价格分析已移除
        
        return thesis