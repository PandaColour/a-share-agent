# -*- coding: utf-8 -*-
"""基本面分析师"""

import pandas as pd
import numpy as np
from typing import Dict
import logging

from .base_analyst import BaseAnalyst

logger = logging.getLogger(__name__)

class FundamentalAnalyst(BaseAnalyst):
    def __init__(self):
        super().__init__("fundamental")
    
        


    def _traditional_analysis(self, symbol: str, data: pd.DataFrame, info: Dict, indicators: Dict) -> Dict:
        """传统基本面分析 - 参考TradingAgents-CN架构优化"""
        analysis = {
            "analyst_type": "基本面分析",
            "recommendation": "持有",
            "confidence": 0.5,
            "reasoning": [],
            "valuation_status": "合理",
            "financial_health": "良好"
        }
        
        if not info:
            analysis["reasoning"].append("⚠️ 缺乏基本面数据，无法进行深度分析")
            analysis["confidence"] = 0.2
            return analysis
        
        current_price = data['Close'].iloc[-1] if not data.empty else info.get('currentPrice', 0)
        
        # 1. 估值指标分析
        valuation_score = self._analyze_valuation_metrics(info, current_price)
        analysis["confidence"] += valuation_score["adjustment"]
        analysis["reasoning"].extend(valuation_score["reasons"])
        
        # 2. 财务健康状况分析
        financial_score = self._analyze_financial_health(info)
        analysis["confidence"] += financial_score["adjustment"] 
        analysis["reasoning"].extend(financial_score["reasons"])
        analysis["financial_health"] = financial_score["status"]
        
        # 3. 盈利能力分析
        profitability_score = self._analyze_profitability(info)
        analysis["confidence"] += profitability_score["adjustment"]
        analysis["reasoning"].extend(profitability_score["reasons"])
        
        # 4. 成长性分析
        growth_score = self._analyze_growth_potential(info)
        analysis["confidence"] += growth_score["adjustment"]
        analysis["reasoning"].extend(growth_score["reasons"])
        
        # 5. 计算目标价格区间
        # 6. 估值状况判断
        analysis["valuation_status"] = self._determine_valuation_status(info, current_price)
        
        # 7. 综合投资建议
        analysis["confidence"] = self._ensure_confidence_range(analysis["confidence"])
        
        if analysis["confidence"] > 0.75:
            analysis["recommendation"] = "强烈买入" if analysis["valuation_status"] == "低估" else "买入"
        elif analysis["confidence"] > 0.6:
            analysis["recommendation"] = "买入"
        elif analysis["confidence"] < 0.35:
            analysis["recommendation"] = "强烈卖出" if analysis["valuation_status"] == "高估" else "卖出"
        elif analysis["confidence"] < 0.5:
            analysis["recommendation"] = "卖出"
        
        return analysis
    
    def _ai_analysis(self, symbol: str, data: pd.DataFrame, info: Dict, 
                    indicators: Dict, traditional_analysis: Dict) -> Dict:
        """AI增强基本面分析"""
        current_price = data['Close'].iloc[-1] if not data.empty else 0
        pe_ratio = info.get('trailingPE', 'N/A')
        market_cap = info.get('marketCap', 0)
        
        # 格式化市值显示
        if market_cap:
            if market_cap >= 1e12:
                market_cap_str = f"{market_cap/1e12:.2f}万亿"
            elif market_cap >= 1e8:
                market_cap_str = f"{market_cap/1e8:.0f}亿"
            else:
                market_cap_str = f"{market_cap:.0f}"
        else:
            market_cap_str = "N/A"
        
        # 获取分析提示词
        prompt_config = self._get_ai_prompt_config()
        
        # 构建上下文数据
        context = {
            "symbol": symbol,
            "current_price": current_price,
            "pe_ratio": pe_ratio,
            "market_cap": market_cap_str,
            "traditional_analysis": traditional_analysis
        }
        
        # 获取额外需要的变量
        company_name = info.get('longName', '') or info.get('shortName', '') or symbol
        pb_ratio = info.get('priceToBook', 2.0)
        roe = info.get('returnOnEquity', 0.15) * 100  # 转换为百分比
        industry = info.get('industry', '未知行业')
        growth_rate = 8.0  # 默认增长率

        # 市场相关性分析已移除，使用默认数据
        market_correlation_data = self._get_default_market_data()

        # 构建用户提示词
        user_prompt = prompt_config["user_prompt"].format(
            symbol=symbol,
            company_name=company_name,
            current_price=current_price,
            pe_ratio=pe_ratio,
            pb_ratio=pb_ratio,
            roe=roe,
            industry=industry,
            growth_rate=growth_rate,
            # 市场相关性数据
            market_beta=market_correlation_data.get('market_beta', 'N/A'),
            systematic_risk=market_correlation_data.get('systematic_risk', 'N/A'),
            sector_correlation=market_correlation_data.get('sector_correlation', 'N/A'),
            rotation_signal=market_correlation_data.get('rotation_signal', 'N/A'),
            risk_classification=market_correlation_data.get('risk_classification', 'N/A'),
            data_quality=market_correlation_data.get('data_quality', 'N/A'),
            data_verification=market_correlation_data.get('data_verification', 'N/A')
        )
        
        # 调用AI模型
        ai_response = self.ai_model.generate_analysis(user_prompt, context)
        
        # 解析AI响应并增强分析
        enhanced_analysis = {}
        
        # 使用基类的通用合并逻辑
        ai_recommendation = self._extract_ai_recommendation(ai_response)
        return self._combine_traditional_and_ai_analysis(traditional_analysis, ai_recommendation, ai_response)


    def _get_default_market_data(self) -> Dict:
        """返回默认的市场相关性数据"""
        return {
            'market_beta': 'N/A',
            'systematic_risk': 'N/A',
            'sector_correlation': 'N/A',
            'rotation_signal': 'N/A',
            'risk_classification': 'N/A',
            'data_quality': '数据不足',
            'data_verification': '无法验证'
        }
    
    def _analyze_valuation_metrics(self, info: Dict, current_price: float) -> Dict:
        """估值指标分析 - 参考TradingAgents-CN方法"""
        result = {"adjustment": 0.0, "reasons": []}
        
        # PE比率分析
        pe_ratio = info.get('trailingPE', 0)
        if pe_ratio and pe_ratio > 0:
            if pe_ratio < 10:
                result["adjustment"] += 0.15
                result["reasons"].append(f"📊 PE比率{pe_ratio:.1f}极低，可能被严重低估")
            elif pe_ratio < 15:
                result["adjustment"] += 0.1
                result["reasons"].append(f"📊 PE比率{pe_ratio:.1f}较低，估值合理")
            elif pe_ratio > 50:
                result["adjustment"] -= 0.15
                result["reasons"].append(f"📊 PE比率{pe_ratio:.1f}过高，存在泡沫风险")
            elif pe_ratio > 30:
                result["adjustment"] -= 0.1
                result["reasons"].append(f"📊 PE比率{pe_ratio:.1f}偏高，估值压力")
        
        # PB比率分析
        pb_ratio = info.get('priceToBook', 0)
        if pb_ratio and pb_ratio > 0:
            if pb_ratio < 1:
                result["adjustment"] += 0.1
                result["reasons"].append(f"📊 PB比率{pb_ratio:.1f}破净，可能存在价值")
            elif pb_ratio > 5:
                result["adjustment"] -= 0.08
                result["reasons"].append(f"📊 PB比率{pb_ratio:.1f}过高，账面价值偏离")
        
        # PEG比率分析
        peg_ratio = info.get('pegRatio', 0)
        if peg_ratio and peg_ratio > 0:
            if peg_ratio < 1:
                result["adjustment"] += 0.08
                result["reasons"].append(f"📊 PEG比率{peg_ratio:.2f}小于1，增长合理定价")
            elif peg_ratio > 2:
                result["adjustment"] -= 0.08
                result["reasons"].append(f"📊 PEG比率{peg_ratio:.2f}过高，增长预期过度")
        
        return result
    
    def _analyze_financial_health(self, info: Dict) -> Dict:
        """财务健康状况分析"""
        result = {"adjustment": 0.0, "reasons": [], "status": "良好"}
        
        # 负债率分析
        debt_to_equity = info.get('debtToEquity', 0)
        if debt_to_equity:
            if debt_to_equity < 30:
                result["adjustment"] += 0.05
                result["reasons"].append(f"💪 负债权益比{debt_to_equity:.1f}%较低，财务稳健")
            elif debt_to_equity > 80:
                result["adjustment"] -= 0.1
                result["reasons"].append(f"⚠️ 负债权益比{debt_to_equity:.1f}%过高，财务风险")
                result["status"] = "风险"
        
        # 流动比率分析
        current_ratio = info.get('currentRatio', 0)
        if current_ratio:
            if current_ratio > 2:
                result["adjustment"] += 0.05
                result["reasons"].append(f"💰 流动比率{current_ratio:.2f}良好，短期偿债能力强")
            elif current_ratio < 1:
                result["adjustment"] -= 0.08
                result["reasons"].append(f"⚠️ 流动比率{current_ratio:.2f}偏低，流动性风险")
                result["status"] = "风险"
        
        # 现金流分析
        free_cash_flow = info.get('freeCashflow', 0)
        if free_cash_flow:
            if free_cash_flow > 0:
                result["adjustment"] += 0.05
                result["reasons"].append("💵 自由现金流为正，现金生成能力良好")
            else:
                result["adjustment"] -= 0.05
                result["reasons"].append("⚠️ 自由现金流为负，现金流压力")
        
        return result
    
    def _analyze_profitability(self, info: Dict) -> Dict:
        """盈利能力分析"""
        result = {"adjustment": 0.0, "reasons": []}
        
        # ROE分析
        roe = info.get('returnOnEquity', 0)
        if roe:
            if roe > 0.2:  # 20%以上
                result["adjustment"] += 0.1
                result["reasons"].append(f"🚀 ROE {roe:.1%}优秀，股东回报率高")
            elif roe > 0.15:  # 15%以上
                result["adjustment"] += 0.05
                result["reasons"].append(f"✅ ROE {roe:.1%}良好，盈利能力较强")
            elif roe < 0.05:  # 5%以下
                result["adjustment"] -= 0.08
                result["reasons"].append(f"📉 ROE {roe:.1%}偏低，盈利能力不足")
        
        # ROA分析
        roa = info.get('returnOnAssets', 0)
        if roa:
            if roa > 0.1:
                result["adjustment"] += 0.05
                result["reasons"].append(f"💪 ROA {roa:.1%}优秀，资产使用效率高")
            elif roa < 0.02:
                result["adjustment"] -= 0.05
                result["reasons"].append(f"📉 ROA {roa:.1%}偏低，资产收益率不足")
        
        # 毛利率分析
        gross_margins = info.get('grossMargins', 0)
        if gross_margins:
            if gross_margins > 0.5:
                result["adjustment"] += 0.05
                result["reasons"].append(f"💎 毛利率{gross_margins:.1%}很高，产品定价能力强")
            elif gross_margins < 0.2:
                result["adjustment"] -= 0.05
                result["reasons"].append(f"📉 毛利率{gross_margins:.1%}偏低，成本压力大")
        
        return result
    
    def _analyze_growth_potential(self, info: Dict) -> Dict:
        """成长性分析"""
        result = {"adjustment": 0.0, "reasons": []}
        
        # 营收增长率
        revenue_growth = info.get('revenueGrowth', 0)
        if revenue_growth:
            if revenue_growth > 0.3:
                result["adjustment"] += 0.1
                result["reasons"].append(f"🚀 营收增长率{revenue_growth:.1%}强劲，业务快速扩张")
            elif revenue_growth > 0.1:
                result["adjustment"] += 0.05
                result["reasons"].append(f"📈 营收增长率{revenue_growth:.1%}稳健，业务持续增长")
            elif revenue_growth < -0.1:
                result["adjustment"] -= 0.1
                result["reasons"].append(f"📉 营收增长率{revenue_growth:.1%}负增长，业务萎缩")
        
        # 盈利增长率
        earnings_growth = info.get('earningsGrowth', 0) 
        if earnings_growth:
            if earnings_growth > 0.3:
                result["adjustment"] += 0.08
                result["reasons"].append(f"💰 盈利增长率{earnings_growth:.1%}优异，盈利能力提升")
            elif earnings_growth < -0.2:
                result["adjustment"] -= 0.08
                result["reasons"].append(f"📉 盈利增长率{earnings_growth:.1%}大幅下滑，盈利恶化")
        
        return result
    
    def _determine_valuation_status(self, info: Dict, current_price: float) -> str:
        """基于基本面指标判断估值状况"""
        if current_price <= 0:
            return "无法评估"

        # 基于PE判断
        pe_ratio = info.get('trailingPE', 15)
        if pe_ratio > 0:
            if pe_ratio < 10:
                pe_status = "低估"
            elif pe_ratio > 25:
                pe_status = "高估"
            else:
                pe_status = "合理"
        else:
            pe_status = "无法评估"

        # 基于PB判断
        pb_ratio = info.get('priceToBook', 2)
        if pb_ratio > 0:
            if pb_ratio < 1:
                pb_status = "低估"
            elif pb_ratio > 3:
                pb_status = "高估"
            else:
                pb_status = "合理"
        else:
            pb_status = "无法评估"

        # 综合判断
        if pe_status == "低估" and pb_status == "低估":
            return "低估"
        elif pe_status == "高估" or pb_status == "高估":
            return "高估"
        elif pe_status == "低估" or pb_status == "低估":
            return "相对低估"
        else:
            return "合理"
