# -*- coding: utf-8 -*-
"""技术面分析师"""

import pandas as pd
import numpy as np
from typing import Dict
import logging
import sys
import os

from .base_analyst import BaseAnalyst

# 添加src路径到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# 导入AI因子模块
try:
    from factors import get_factor_manager, initialize_factors
    FACTORS_AVAILABLE = True
    # 初始化因子
    initialize_factors()
except ImportError as e:
    logger.warning(f"AI因子模块不可用: {e}")
    FACTORS_AVAILABLE = False

logger = logging.getLogger(__name__)

class TechnicalAnalyst(BaseAnalyst):
    def __init__(self):
        super().__init__("technical")
    
        
    def analyze(self, symbol: str, data: pd.DataFrame, info: Dict, indicators: Dict) -> Dict:
        # 首先进行传统分析
        analysis = self._traditional_analysis(symbol, data, info, indicators)
        
        # AI因子增强分析
        if FACTORS_AVAILABLE:
            try:
                factor_analysis = self._ai_factor_analysis(symbol, data, indicators)
                analysis.update(factor_analysis)
                analysis["reasoning"].append("已使用AI因子增强分析")
            except Exception as e:
                logger.error(f"AI因子分析失败: {e}")
        
        # 价格预测分析
        if FACTORS_AVAILABLE:
            try:
                prediction_analysis = self._price_prediction_analysis(symbol, data, indicators)
                analysis.update(prediction_analysis)
                analysis["reasoning"].append("已集成价格预测分析")
            except Exception as e:
                logger.error(f"价格预测分析失败: {e}")

        # 市场相关性分析
        try:
            # 市场相关性分析已移除
            market_analysis = {'error': '市场相关性分析已禁用'}
            # 市场相关性分析已禁用
            if False:  # 市场分析已移除
                pass
            else:
                analysis["reasoning"].append("市场相关性分析已禁用")
        except Exception as e:
            logger.error(f"市场相关性分析异常: {e}")
            analysis["reasoning"].append("市场相关性分析不可用")
        
        # 如果启用了AI分析且模型可用，进行AI增强分析
        ai_config = self.config_manager.get_ai_config()
        if (self.ai_model and self.ai_model.is_available() and 
            ai_config.get('enable_ai_analysis', False)):
            try:
                ai_analysis = self._ai_analysis(symbol, data, info, indicators, analysis)
                analysis.update(ai_analysis)
                analysis["reasoning"].append("已使用AI模型增强分析")
            except Exception as e:
                logger.error(f"AI分析失败: {e}")
                # 使用基类的错误处理
                analysis = self._create_ai_failure_response(str(e))
        
        return analysis

    def analyze_with_data(self, symbol: str, stock_data: pd.DataFrame, benchmark_data: Dict) -> Dict:
        """
        使用预获取的数据进行技术分析（避免重复数据获取）

        Args:
            symbol: 股票代码
            stock_data: 股票价格数据
            benchmark_data: 基准数据字典

        Returns:
            分析结果字典
        """
        # 构造兼容的info和indicators参数
        info = {}
        indicators = {}

        # 从股票数据计算基本信息
        if not stock_data.empty:
            info['currentPrice'] = stock_data['Close'].iloc[-1]
            info['volume'] = stock_data['Volume'].iloc[-1] if 'Volume' in stock_data.columns else 0

        # 调用传统分析逻辑，但使用预获取的基准数据进行市场分析
        return self._analyze_with_benchmark_data(symbol, stock_data, info, indicators, benchmark_data)

    def _analyze_with_benchmark_data(self, symbol: str, data: pd.DataFrame, info: Dict,
                                   indicators: Dict, benchmark_data: Dict) -> Dict:
        """使用预获取的基准数据进行技术分析，避免内部数据获取"""
        # 首先进行传统分析
        analysis = self._traditional_analysis(symbol, data, info, indicators)

        # AI因子增强分析 (传递市场数据)
        if FACTORS_AVAILABLE:
            try:
                factor_analysis = self._ai_factor_analysis(symbol, data, indicators, benchmark_data)
                analysis.update(factor_analysis)
                analysis["reasoning"].append("已使用AI因子增强分析（含市场数据）")
            except Exception as e:
                logger.error(f"AI因子分析失败: {e}")

        # 价格预测分析 (传递市场数据)
        if FACTORS_AVAILABLE:
            try:
                prediction_analysis = self._price_prediction_analysis(symbol, data, indicators, benchmark_data)
                analysis.update(prediction_analysis)
                analysis["reasoning"].append("已集成价格预测分析（含市场数据）")
            except Exception as e:
                logger.error(f"价格预测分析失败: {e}")

        # 使用预获取的基准数据进行市场相关性分析
        try:
            # 市场相关性分析已移除
            market_analysis = {'error': '市场相关性分析已禁用'}
            # 市场相关性分析已禁用
            if False:  # 市场分析已移除
                pass
            else:
                analysis["reasoning"].append("市场相关性分析已禁用（集中数据版本）")
        except Exception as e:
            logger.error(f"市场相关性分析异常: {e}")
            analysis["reasoning"].append("市场相关性分析不可用")

        # 如果启用了AI分析且模型可用，进行AI增强分析
        ai_config = self.config_manager.get_ai_config()
        if (self.ai_model and self.ai_model.is_available() and
            ai_config.get('enable_ai_analysis', False)):
            try:
                ai_analysis = self._ai_analysis(symbol, data, info, indicators, analysis)
                analysis.update(ai_analysis)
                analysis["reasoning"].append("已使用AI模型增强分析（集中数据版本）")
            except Exception as e:
                logger.error(f"AI分析失败: {e}")
                # 使用基类的错误处理
                analysis = self._create_ai_failure_response(str(e))

        return analysis

    def _traditional_analysis(self, symbol: str, data: pd.DataFrame, info: Dict, indicators: Dict) -> Dict:
        """传统技术面分析"""
        analysis = {
            "analyst_type": "技术面分析",
            "recommendation": "持有",
            "confidence": 0.5,
            "reasoning": [],
            "time_horizon": "medium"  # 技术面分析关注中期(15-30天)
        }
        
        if not indicators:
            analysis["reasoning"].append("缺乏技术数据")
            return analysis
        
        # 移动平均线分析（优先使用日线指标）
        ma5 = indicators.get('daily_ma5') or indicators.get('ma5', 0)
        ma20 = indicators.get('daily_ma20') or indicators.get('ma20', 0)
        current_price = data['Close'].iloc[-1] if not data.empty else 0

        if ma5 and ma20:
            if ma5 > ma20 and current_price > ma5:
                analysis["reasoning"].append("技术面强势")
                analysis["confidence"] += 0.2
                analysis["recommendation"] = "买入"
            elif ma5 < ma20 and current_price < ma5:
                analysis["reasoning"].append("技术面疲软")
                analysis["confidence"] -= 0.2
                analysis["recommendation"] = "卖出"
        
        # RSI分析（优先使用日线指标）
        rsi = indicators.get('daily_rsi') or indicators.get('rsi', 50)
        if rsi and not pd.isna(rsi):
            if rsi > 70:
                analysis["reasoning"].append(f"RSI{rsi:.0f}超买")
                analysis["confidence"] -= 0.1
            elif rsi < 30:
                analysis["reasoning"].append(f"RSI{rsi:.0f}超卖")
                analysis["confidence"] += 0.1
        
        # MACD分析（优先使用日线指标）
        macd = indicators.get('daily_macd') or indicators.get('macd', 0)
        macd_signal = indicators.get('daily_macd_signal') or indicators.get('macd_signal', 0)
        macd_histogram = indicators.get('daily_macd_histogram') or indicators.get('macd_histogram', 0)
        
        if macd and macd_signal:
            if macd > macd_signal and macd_histogram > 0:
                analysis["reasoning"].append("MACD金叉看涨")
                analysis["confidence"] += 0.15
                if analysis["recommendation"] == "持有":
                    analysis["recommendation"] = "买入"
            elif macd < macd_signal and macd_histogram < 0:
                analysis["reasoning"].append("MACD死叉看跌")
                analysis["confidence"] -= 0.15
                if analysis["recommendation"] == "持有":
                    analysis["recommendation"] = "卖出"
        
        # KDJ分析（优先使用日线指标）
        kdj_k = indicators.get('daily_kdj_k') or indicators.get('kdj_k', 50)
        kdj_d = indicators.get('daily_kdj_d') or indicators.get('kdj_d', 50)
        kdj_j = indicators.get('daily_kdj_j') or indicators.get('kdj_j', 50)
        
        if kdj_k and kdj_d and kdj_j:
            if kdj_k > kdj_d and kdj_j > kdj_k and kdj_k < 80:
                analysis["reasoning"].append("KDJ金叉向上")
                analysis["confidence"] += 0.1
            elif kdj_k < kdj_d and kdj_j < kdj_k and kdj_k > 20:
                analysis["reasoning"].append("KDJ死叉向下")
                analysis["confidence"] -= 0.1
            
            # KDJ超买超卖判断
            if kdj_k > 80 and kdj_d > 80:
                analysis["reasoning"].append("KDJ超买区域")
                analysis["confidence"] -= 0.05
            elif kdj_k < 20 and kdj_d < 20:
                analysis["reasoning"].append("KDJ超卖区域")
                analysis["confidence"] += 0.05
        
        # 威廉指标分析（优先使用日线指标）
        williams_r = indicators.get('daily_williams_r') or indicators.get('williams_r', -50)
        if williams_r:
            if williams_r > -20:
                analysis["reasoning"].append("威廉指标超买")
                analysis["confidence"] -= 0.08
            elif williams_r < -80:
                analysis["reasoning"].append("威廉指标超卖")
                analysis["confidence"] += 0.08
        
        # CCI指标分析（优先使用日线指标）
        cci = indicators.get('daily_cci') or indicators.get('cci', 0)
        if cci:
            if cci > 100:
                analysis["reasoning"].append("CCI超买")
                analysis["confidence"] -= 0.08
            elif cci < -100:
                analysis["reasoning"].append("CCI超卖")
                analysis["confidence"] += 0.08
        
        # 量价关系分析（优先使用日线指标）
        volume_price_trend = indicators.get('daily_volume_price_trend') or indicators.get('volume_price_trend', 'neutral')
        turnover_rate = indicators.get('daily_turnover_rate') or indicators.get('turnover_rate', 0)
        
        if volume_price_trend == "量价齐升":
            analysis["reasoning"].append("量价配合良好")
            analysis["confidence"] += 0.1
        elif volume_price_trend == "量价背离":
            analysis["reasoning"].append("量价出现背离")
            analysis["confidence"] -= 0.1
        
        # 换手率分析
        if turnover_rate:
            if turnover_rate > 10:
                analysis["reasoning"].append("换手率偏高")
                analysis["confidence"] -= 0.05
            elif turnover_rate < 1:
                analysis["reasoning"].append("换手率偏低")
                analysis["confidence"] -= 0.03
        
        # 布林带分析（如果有数据）
        if self._has_sufficient_data(data, 20):
            bollinger_analysis = self._analyze_bollinger_bands(data, current_price)
            analysis["confidence"] += bollinger_analysis["adjustment"]
            analysis["reasoning"].extend(bollinger_analysis["reasons"])
        
        # 支撑阻力位分析
        support_resistance = self._analyze_support_resistance(data, current_price)
        analysis.update(support_resistance)
        
        # 趋势强度分析
        trend_analysis = self._analyze_trend_strength(data, indicators)
        analysis["confidence"] += trend_analysis["adjustment"]
        analysis["reasoning"].extend(trend_analysis["reasons"])
        analysis["trend_strength"] = trend_analysis["strength"]
        
        # 确保信心度在合理范围内
        analysis["confidence"] = self._ensure_confidence_range(analysis["confidence"])
        
        return analysis
    
    def _ai_analysis(self, symbol: str, data: pd.DataFrame, info: Dict, 
                    indicators: Dict, traditional_analysis: Dict) -> Dict:
        """AI增强技术面分析"""
        current_price = data['Close'].iloc[-1] if not data.empty else 0
        ma5 = indicators.get('ma5', 'N/A')
        ma20 = indicators.get('ma20', 'N/A')
        rsi = indicators.get('rsi', 'N/A')
        
        # 获取MACD指标
        macd = indicators.get('macd', 'N/A')
        macd_signal = indicators.get('macd_signal', 'N/A')
        macd_histogram = indicators.get('macd_histogram', 'N/A')
        
        # 获取KDJ指标
        kdj_k = indicators.get('kdj_k', 'N/A')
        kdj_d = indicators.get('kdj_d', 'N/A')
        kdj_j = indicators.get('kdj_j', 'N/A')
        
        # 获取动量指标
        williams_r = indicators.get('williams_r', 'N/A')
        cci = indicators.get('cci', 'N/A')
        
        # 获取成交量指标
        turnover_rate = indicators.get('turnover_rate', 'N/A')
        volume_price_trend = indicators.get('volume_price_trend', 'N/A')
        volume_price_correlation = indicators.get('volume_price_correlation', 'N/A')
        
        # 计算成交量变化
        volume_change = "N/A"
        if not data.empty and len(data) > 1:
            recent_volume = data['Volume'].tail(5).mean()
            prev_volume = data['Volume'].iloc[:-5].tail(5).mean() if len(data) > 10 else recent_volume
            if prev_volume > 0:
                volume_change = f"{(recent_volume - prev_volume) / prev_volume * 100:.1f}%"
        
        # 获取分析提示词
        prompt_config = self._get_ai_prompt_config()
        
        # 构建上下文数据
        context = {
            "symbol": symbol,
            "current_price": current_price,
            "ma5": ma5,
            "ma20": ma20,
            "rsi": rsi,
            "volume_change": volume_change,
            "traditional_analysis": traditional_analysis
        }
        
        # 获取价格信息 - 从数据中计算
        if not data.empty:
            daily_high = data['High'].iloc[-1] if 'High' in data.columns else current_price
            daily_low = data['Low'].iloc[-1] if 'Low' in data.columns else current_price
            if len(data) > 1:
                prev_close = data['Close'].iloc[-2]
                daily_change = (current_price - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
            else:
                daily_change = 0.0
        else:
            daily_high = current_price
            daily_low = current_price
            daily_change = 0.0
        
        # 计算其他需要的变量
        if volume_change != "N/A" and isinstance(volume_change, str):
            try:
                volume_change_pct = float(volume_change.replace('%', ''))
                volume_ratio = 1.0 + volume_change_pct / 100  # 转换为倍数
            except:
                volume_ratio = 1.0
        else:
            volume_ratio = 1.0
        volatility = indicators.get("volatility", 0.0) * 100 if indicators.get("volatility") else 0.0
        price_position = indicators.get("price_position", 0.5)
        
        # 获取新的双重时间框架指标
        # 日线指标
        daily_ma5 = indicators.get('daily_ma5', 'N/A')
        daily_ma20 = indicators.get('daily_ma20', 'N/A')
        daily_rsi = indicators.get('daily_rsi', 'N/A')
        daily_macd = indicators.get('daily_macd', 'N/A')
        daily_macd_signal = indicators.get('daily_macd_signal', 'N/A')
        daily_macd_histogram = indicators.get('daily_macd_histogram', 'N/A')
        daily_kdj_k = indicators.get('daily_kdj_k', 'N/A')
        daily_kdj_d = indicators.get('daily_kdj_d', 'N/A')
        daily_kdj_j = indicators.get('daily_kdj_j', 'N/A')
        daily_turnover_rate = indicators.get('daily_turnover_rate', 'N/A')
        daily_volume_price_trend = indicators.get('daily_volume_price_trend', 'N/A')
        daily_volatility = indicators.get('daily_volatility', 0.0) * 100 if indicators.get('daily_volatility') else 'N/A'

        # 5分钟指标
        intraday_ma5 = indicators.get('intraday_ma5', 'N/A')
        intraday_ma20 = indicators.get('intraday_ma20', 'N/A')
        intraday_rsi = indicators.get('intraday_rsi', 'N/A')
        intraday_macd = indicators.get('intraday_macd', 'N/A')
        intraday_volume_ratio = indicators.get('intraday_volume_ratio', 'N/A')
        intraday_momentum = indicators.get('intraday_momentum', 'N/A')
        intraday_volatility = indicators.get('intraday_volatility', 0.0) * 100 if indicators.get('intraday_volatility') else 'N/A'

        # 融合指标
        trend_consistency = indicators.get('trend_consistency', 'N/A')
        volatility_alert = indicators.get('volatility_alert', 'N/A')
        momentum_divergence = indicators.get('momentum_divergence', 'N/A')
        volume_amplification = indicators.get('volume_amplification', 'N/A')
        risk_level = indicators.get('risk_level', 'N/A')
        short_term_momentum = indicators.get('short_term_momentum', 'N/A')

        # 获取市场相关性和AI因子数据
        enhanced_data = self._get_enhanced_technical_data(symbol, data, indicators)

        # 构建用户提示词
        user_prompt = prompt_config["user_prompt"].format(
            symbol=symbol,
            current_price=current_price,
            daily_high=daily_high,
            daily_low=daily_low,
            daily_change=daily_change,
            # 日线指标
            daily_ma5=daily_ma5,
            daily_ma20=daily_ma20,
            daily_rsi=daily_rsi,
            daily_macd=daily_macd,
            daily_macd_signal=daily_macd_signal,
            daily_macd_histogram=daily_macd_histogram,
            daily_kdj_k=daily_kdj_k,
            daily_kdj_d=daily_kdj_d,
            daily_kdj_j=daily_kdj_j,
            daily_turnover_rate=daily_turnover_rate,
            daily_volume_price_trend=daily_volume_price_trend,
            daily_volatility=daily_volatility,
            # 5分钟指标
            intraday_ma5=intraday_ma5,
            intraday_ma20=intraday_ma20,
            intraday_rsi=intraday_rsi,
            intraday_macd=intraday_macd,
            intraday_volume_ratio=intraday_volume_ratio,
            intraday_momentum=intraday_momentum,
            intraday_volatility=intraday_volatility,
            # 融合指标
            trend_consistency=trend_consistency,
            volatility_alert=volatility_alert,
            momentum_divergence=momentum_divergence,
            volume_amplification=volume_amplification,
            risk_level=risk_level,
            short_term_momentum=short_term_momentum,
            # 市场相关性分析
            market_beta=enhanced_data.get('market_beta', 'N/A'),
            hs300_correlation=enhanced_data.get('hs300_correlation', 'N/A'),
            sector_tech_sync=enhanced_data.get('sector_tech_sync', 'N/A'),
            systematic_tech_risk=enhanced_data.get('systematic_tech_risk', 'N/A'),
            # AI技术因子
            ai_factor_score=enhanced_data.get('ai_factor_score', 'N/A'),
            top_ai_factors=enhanced_data.get('top_ai_factors', 'N/A'),
            ai_confidence=enhanced_data.get('ai_confidence', 'N/A'),
            factor_weights=enhanced_data.get('factor_weights', 'N/A'),
            # 增强分析指标
            multi_timeframe_consistency=enhanced_data.get('multi_timeframe_consistency', 'N/A'),
            volume_price_divergence=enhanced_data.get('volume_price_divergence', 'N/A'),
            pattern_recognition=enhanced_data.get('pattern_recognition', 'N/A')
        )
        
        # 调用AI模型
        ai_response = self.ai_model.generate_analysis(user_prompt, context)
        
        # 解析AI响应并增强分析
        enhanced_analysis = {}
        
        # 使用基类的通用合并逻辑
        ai_recommendation = self._extract_ai_recommendation(ai_response)
        return self._combine_traditional_and_ai_analysis(traditional_analysis, ai_recommendation, ai_response)
    
    def _ai_factor_analysis(self, symbol: str, data: pd.DataFrame, indicators: Dict,
                           benchmark_data: Dict = None) -> Dict:
        """AI因子增强分析（支持市场数据）"""
        if not FACTORS_AVAILABLE:
            return {}

        try:
            factor_manager = get_factor_manager()

            # 准备因子计算所需的数据（包含市场数据）
            factor_data = {
                "price": data,
                "volume": data[['Volume']] if 'Volume' in data.columns else pd.DataFrame()
            }

            # 添加市场数据
            if benchmark_data:
                factor_data["market_data"] = benchmark_data.get('hs300_data')
                factor_data["market_state"] = benchmark_data.get('market_state')
                factor_data["stock_beta"] = benchmark_data.get('stock_beta')

            # 计算技术面AI因子
            factor_results = factor_manager.calculate_all_factors(
                symbol, factor_data, categories=['technical']
            )
            
            if not factor_results:
                logger.warning(f"未计算到任何技术因子: {symbol}")
                return {}
            
            # 分析因子结果
            factor_analysis = {
                "ai_factors": {},
                "factor_score": 0.0,
                "factor_confidence": 0.0,
                "time_horizon": "short"  # AI因子分析关注短期(0-14天)
            }
            
            total_score = 0.0
            total_confidence = 0.0
            factor_count = 0
            
            for factor_name, factor_value in factor_results.items():
                factor_analysis["ai_factors"][factor_name] = {
                    "value": round(factor_value.value, 4),
                    "confidence": factor_value.confidence,
                    "interpretation": self._interpret_factor(factor_name, factor_value.value)
                }
                
                total_score += factor_value.value * factor_value.confidence
                total_confidence += factor_value.confidence
                factor_count += 1
            
            if factor_count > 0:
                # 加权平均分数
                factor_analysis["factor_score"] = total_score / factor_count
                factor_analysis["factor_confidence"] = total_confidence / factor_count
                
                # 根据AI因子调整传统分析结果
                factor_adjustment = self._calculate_factor_adjustment(factor_analysis["factor_score"])
                
                return {
                    "ai_factor_analysis": factor_analysis,
                    "confidence_adjustment": factor_adjustment["confidence_adj"],
                    "recommendation_influence": factor_adjustment["recommendation_influence"]
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"AI因子分析失败 {symbol}: {e}")
            return {}
    
    def _interpret_factor(self, factor_name: str, value: float) -> str:
        """解释因子值的含义"""
        if factor_name == "pattern_recognition":
            if value > 0.3:
                return "技术形态偏向看涨"
            elif value < -0.3:
                return "技术形态偏向看跌"
            else:
                return "技术形态中性"
        
        elif factor_name == "volume_pattern":
            if value > 0.3:
                return "量价关系积极，资金流入"
            elif value < -0.3:
                return "量价关系消极，资金流出"
            else:
                return "量价关系平衡"
        
        else:
            # 通用解释
            if value > 0.2:
                return "因子显示积极信号"
            elif value < -0.2:
                return "因子显示消极信号"
            else:
                return "因子显示中性信号"
    
    def _calculate_factor_adjustment(self, factor_score: float) -> Dict:
        """根据AI因子计算调整参数"""
        # 信心度调整
        confidence_adj = 0.0
        if abs(factor_score) > 0.3:  # 因子信号较强
            confidence_adj = min(0.2, abs(factor_score) * 0.5)  # 最多提高20%信心度
        
        # 推荐影响
        recommendation_influence = "neutral"
        if factor_score > 0.4:
            recommendation_influence = "bullish"
        elif factor_score < -0.4:
            recommendation_influence = "bearish"
        
        return {
            "confidence_adj": confidence_adj,
            "recommendation_influence": recommendation_influence,
            "factor_strength": abs(factor_score)
        }
    
    def _price_prediction_analysis(self, symbol: str, data: pd.DataFrame, indicators: Dict,
                                  benchmark_data: Dict = None) -> Dict:
        """价格预测分析（支持市场数据）"""
        if not FACTORS_AVAILABLE:
            return {}

        try:
            factor_manager = get_factor_manager()

            # 准备预测因子所需的数据（包含市场数据）
            factor_data = {
                "price": data,
                "volume": data[['Volume']] if 'Volume' in data.columns else pd.DataFrame()
            }

            # 添加市场数据
            if benchmark_data:
                factor_data["market_data"] = benchmark_data.get('hs300_data')
                factor_data["market_state"] = benchmark_data.get('market_state')
                factor_data["stock_beta"] = benchmark_data.get('stock_beta')

            # 计算预测因子
            prediction_results = factor_manager.calculate_all_factors(
                symbol, factor_data, categories=['prediction']
            )
            
            if not prediction_results:
                logger.warning(f"未计算到任何预测因子: {symbol}")
                return {}
            
            # 解析预测结果
            prediction_analysis = {
                "price_predictions": {},
                "prediction_summary": {},
                "investment_outlook": "中性"
            }
            
            # 处理价格预测因子
            price_pred_factor = prediction_results.get('price_prediction_14d')
            if price_pred_factor:
                raw_data = price_pred_factor.raw_data or {}
                
                prediction_analysis["price_predictions"]["14d_forecast"] = {
                    "current_price": raw_data.get("current_price", 0),
                    "predicted_high": raw_data.get("predicted_14d_high", 0),
                    "expected_return": raw_data.get("expected_14d_return", 0),
                    "confidence": price_pred_factor.confidence,
                    "prediction_interval": raw_data.get("prediction_interval", (0, 0))
                }
            
            # 处理收益率预测因子
            return_pred_factor = prediction_results.get('return_prediction_14d')
            if return_pred_factor:
                raw_data = return_pred_factor.raw_data or {}
                
                prediction_analysis["price_predictions"]["return_forecast"] = {
                    "expected_return": return_pred_factor.value,
                    "return_std": raw_data.get("return_std", 0),
                    "percentiles": raw_data.get("percentiles", {}),
                    "confidence": return_pred_factor.confidence
                }
            
            # 生成预测摘要
            if price_pred_factor or return_pred_factor:
                prediction_analysis["prediction_summary"] = self._generate_prediction_summary(
                    price_pred_factor, return_pred_factor
                )
                
                # 根据预测结果调整投资展望
                prediction_analysis["investment_outlook"] = self._determine_investment_outlook(
                    price_pred_factor, return_pred_factor
                )
            
            return {
                "prediction_analysis": prediction_analysis,
                "has_predictions": bool(price_pred_factor or return_pred_factor)
            }
            
        except Exception as e:
            logger.error(f"价格预测分析失败 {symbol}: {e}")
            return {}
    
    def _generate_prediction_summary(self, price_factor, return_factor) -> Dict[str, str]:
        """生成预测摘要"""
        summary = {}
        
        if price_factor:
            raw_data = price_factor.raw_data or {}
            current_price = raw_data.get("current_price", 0)
            predicted_high = raw_data.get("predicted_14d_high", 0)
            expected_return = raw_data.get("expected_14d_return", 0)
            confidence = price_factor.confidence
            
            if current_price > 0 and predicted_high > 0:
                return_pct = expected_return * 100
                
                if expected_return > 0.1:
                    outlook = "强烈看涨"
                elif expected_return > 0.05:
                    outlook = "看涨"
                elif expected_return > 0.02:
                    outlook = "温和看涨"
                elif expected_return > -0.02:
                    outlook = "中性"
                elif expected_return > -0.05:
                    outlook = "温和看跌"
                else:
                    outlook = "看跌"
                
                summary["price_outlook"] = f"{outlook}：预测14天内最高可达{predicted_high:.2f}元（+{return_pct:.1f}%），置信度{confidence*100:.0f}%"
        
        if return_factor:
            raw_data = return_factor.raw_data or {}
            expected_return = return_factor.value
            percentiles = raw_data.get("percentiles", {})
            confidence = return_factor.confidence
            
            if percentiles:
                p25 = percentiles.get('25%', 0) * 100
                p75 = percentiles.get('75%', 0) * 100
                summary["return_range"] = f"预期收益区间：{p25:.1f}% 至 {p75:.1f}%，置信度{confidence*100:.0f}%"
        
        return summary
    
    def _determine_investment_outlook(self, price_factor, return_factor) -> str:
        """确定投资展望"""
        if not price_factor and not return_factor:
            return "中性"
        
        total_score = 0
        count = 0
        
        if price_factor:
            raw_data = price_factor.raw_data or {}
            expected_return = raw_data.get("expected_14d_return", 0)
            confidence = price_factor.confidence
            
            # 加权评分
            score = expected_return * confidence
            total_score += score
            count += 1
        
        if return_factor:
            expected_return = return_factor.value
            confidence = return_factor.confidence
            
            score = expected_return * confidence
            total_score += score
            count += 1
        
        if count == 0:
            return "中性"
        
        avg_score = total_score / count
        
        if avg_score > 0.05:
            return "积极"
        elif avg_score > 0.02:
            return "温和积极"
        elif avg_score > -0.02:
            return "中性"
        elif avg_score > -0.05:
            return "温和消极"
        else:
            return "消极"
    
    def _has_sufficient_data(self, data: pd.DataFrame, required_periods: int) -> bool:
        """检查是否有足够的数据进行分析"""
        return not data.empty and len(data) >= required_periods
    
    def _analyze_bollinger_bands(self, data: pd.DataFrame, current_price: float, period: int = 20) -> Dict:
        """布林带分析 - 参考TradingAgents-CN方法"""
        result = {"adjustment": 0.0, "reasons": []}
        
        try:
            # 计算布林带
            ma = data['Close'].rolling(window=period).mean()
            std = data['Close'].rolling(window=period).std()
            upper_band = ma + (std * 2)
            lower_band = ma - (std * 2)
            
            # 获取最新值
            latest_upper = upper_band.iloc[-1]
            latest_lower = lower_band.iloc[-1]
            latest_ma = ma.iloc[-1]
            
            # 计算价格位置
            band_width = latest_upper - latest_lower
            if band_width > 0:
                price_position = (current_price - latest_lower) / band_width
                
                if price_position > 0.8:
                    result["adjustment"] -= 0.1
                    result["reasons"].append(f"💥 价格接近布林带上轨{latest_upper:.2f}，超买信号")
                elif price_position < 0.2:
                    result["adjustment"] += 0.1
                    result["reasons"].append(f"📈 价格接近布林带下轨{latest_lower:.2f}，超卖信号")
                elif 0.4 < price_position < 0.6:
                    result["reasons"].append(f"⚖️ 价格在布林带中轨附近{latest_ma:.2f}，震荡整理")
        except Exception as e:
            logger.error(f"布林带计算失败: {e}")
        
        return result
    
    def _analyze_support_resistance(self, data: pd.DataFrame, current_price: float) -> Dict:
        """支撑阻力位分析"""
        result = {
            "support_levels": [],
            "resistance_levels": [],
            "support_strength": "弱",
            "resistance_strength": "弱"
        }
        
        if data.empty or len(data) < 20:
            return result
            
        try:
            # 计算近期高低点
            recent_data = data.tail(60)  # 最近60个交易日
            
            # 寻找支撑位（近期低点）
            lows = recent_data['Low']
            support_candidates = []
            for i in range(5, len(lows) - 5):
                if all(lows.iloc[i] <= lows.iloc[i-j] for j in range(1, 6)) and \
                   all(lows.iloc[i] <= lows.iloc[i+j] for j in range(1, 6)):
                    support_candidates.append(lows.iloc[i])
            
            # 寻找阻力位（近期高点）
            highs = recent_data['High']
            resistance_candidates = []
            for i in range(5, len(highs) - 5):
                if all(highs.iloc[i] >= highs.iloc[i-j] for j in range(1, 6)) and \
                   all(highs.iloc[i] >= highs.iloc[i+j] for j in range(1, 6)):
                    resistance_candidates.append(highs.iloc[i])
            
            # 筛选有效支撑阻力位
            if support_candidates:
                result["support_levels"] = sorted(list(set(support_candidates)), reverse=True)[:3]
                # 判断支撑强度
                nearest_support = max([s for s in result["support_levels"] if s < current_price], default=0)
                if nearest_support and (current_price - nearest_support) / current_price < 0.05:
                    result["support_strength"] = "强"
                    
            if resistance_candidates:
                result["resistance_levels"] = sorted(list(set(resistance_candidates)))[:3]
                # 判断阻力强度
                nearest_resistance = min([r for r in result["resistance_levels"] if r > current_price], default=float('inf'))
                if nearest_resistance != float('inf') and (nearest_resistance - current_price) / current_price < 0.05:
                    result["resistance_strength"] = "强"
                    
        except Exception as e:
            logger.error(f"支撑阻力位分析失败: {e}")
            
        return result
    
    def _analyze_trend_strength(self, data: pd.DataFrame, indicators: Dict) -> Dict:
        """趋势强度分析"""
        result = {"adjustment": 0.0, "reasons": [], "strength": "中性"}
        
        try:
            if data.empty or len(data) < 20:
                return result
                
            # 基于均线排列判断趋势
            ma5 = indicators.get('ma5', 0)
            ma20 = indicators.get('ma20', 0)
            current_price = data['Close'].iloc[-1]
            
            # 价格与均线关系
            price_trend_score = 0
            if current_price > ma5 > ma20:
                price_trend_score = 2
                result["reasons"].append("📈 价格 > MA5 > MA20，多头排列")
            elif current_price > ma5 and ma5 < ma20:
                price_trend_score = 1
                result["reasons"].append("⚖️ 价格上穿MA5，但MA5仍低于MA20")
            elif current_price < ma5 < ma20:
                price_trend_score = -2
                result["reasons"].append("📉 价格 < MA5 < MA20，空头排列")
            elif current_price < ma5 and ma5 > ma20:
                price_trend_score = -1
                result["reasons"].append("⚖️ 价格低于MA5，但MA5高于MA20")
                
            # MACD趋势确认
            macd_histogram = indicators.get('macd_histogram', 0)
            macd_trend_score = 0
            if macd_histogram > 0:
                macd_trend_score = 1
            elif macd_histogram < 0:
                macd_trend_score = -1
                
            # 量价配合
            volume_price_trend = indicators.get('volume_price_trend', 'neutral')
            volume_score = 0
            if volume_price_trend == "量价齐升":
                volume_score = 1
            elif volume_price_trend == "量价背离":
                volume_score = -1
                
            # 综合评分
            total_score = price_trend_score + macd_trend_score + volume_score
            
            if total_score >= 3:
                result["strength"] = "强势上涨"
                result["adjustment"] = 0.15
            elif total_score >= 1:
                result["strength"] = "温和上涨"
                result["adjustment"] = 0.08
            elif total_score <= -3:
                result["strength"] = "强势下跌"
                result["adjustment"] = -0.15
            elif total_score <= -1:
                result["strength"] = "温和下跌" 
                result["adjustment"] = -0.08
            else:
                result["strength"] = "震荡整理"
                
        except Exception as e:
            logger.error(f"趋势强度分析失败: {e}")

        return result


    def _get_enhanced_technical_data(self, symbol: str, data: pd.DataFrame, indicators: Dict) -> Dict:
        """获取增强技术分析数据（市场相关性+AI因子）"""
        try:
            enhanced_data = {}

            # 获取市场相关性数据
            # 市场相关性数据已移除
            market_data = {
                'market_beta': 'N/A',
                'hs300_correlation': 'N/A',
                'beta_category': 'unknown',
                'sector_dominance': 'N/A',
                'risk_level': 'medium',
                'data_quality': '市场相关性已禁用',
                'note': '市场相关性分析已移除'
            }
            enhanced_data.update(market_data)

            # 获取AI因子数据
            ai_factor_data = self._extract_ai_factor_data()
            enhanced_data.update(ai_factor_data)

            # 计算增强分析指标
            analysis_data = self._calculate_enhanced_analysis_indicators(data, indicators)
            enhanced_data.update(analysis_data)

            return enhanced_data

        except Exception as e:
            logger.error(f"获取增强技术数据失败: {e}")
            return self._get_default_enhanced_data()

    def _extract_ai_factor_data(self) -> Dict:
        """提取AI因子数据"""
        try:
            # 从已有的AI因子分析中提取数据
            ai_factor_analysis = getattr(self, '_cached_ai_factor_analysis', {})

            if not ai_factor_analysis:
                return {
                    'ai_factor_score': 'N/A',
                    'top_ai_factors': 'N/A',
                    'ai_confidence': 'N/A',
                    'factor_weights': 'N/A'
                }

            # AI因子综合评分
            factor_score = ai_factor_analysis.get('factor_score', 0)
            ai_factor_score = round(factor_score * 100, 1)  # 转换为百分制

            # 主要AI信号
            ai_factors = ai_factor_analysis.get('ai_factors', {})
            top_factors = []
            for factor_name, factor_info in ai_factors.items():
                if factor_info.get('confidence', 0) > 0.6:  # 高置信度因子
                    interpretation = factor_info.get('interpretation', '')
                    top_factors.append(f"{factor_name}: {interpretation}")

            top_ai_factors = "; ".join(top_factors[:3]) if top_factors else 'N/A'

            # AI置信度
            factor_confidence = ai_factor_analysis.get('factor_confidence', 0)
            ai_confidence = round(factor_confidence * 100, 1)

            # 因子权重分布
            if ai_factors:
                weights = []
                for factor_name, factor_info in ai_factors.items():
                    confidence = factor_info.get('confidence', 0)
                    weights.append(f"{factor_name}({confidence:.1f})")
                factor_weights = "; ".join(weights[:3]) if weights else 'N/A'
            else:
                factor_weights = 'N/A'

            return {
                'ai_factor_score': ai_factor_score,
                'top_ai_factors': top_ai_factors,
                'ai_confidence': ai_confidence,
                'factor_weights': factor_weights
            }

        except Exception as e:
            logger.error(f"提取AI因子数据失败: {e}")
            return {
                'ai_factor_score': 'N/A',
                'top_ai_factors': 'N/A',
                'ai_confidence': 'N/A',
                'factor_weights': 'N/A'
            }

    def _calculate_enhanced_analysis_indicators(self, data: pd.DataFrame, indicators: Dict) -> Dict:
        """计算增强分析指标"""
        try:
            # 多时间框架一致性
            daily_trend = indicators.get('trend_consistency', 'N/A')
            intraday_momentum = indicators.get('intraday_momentum', 'N/A')

            if daily_trend != 'N/A' and intraday_momentum != 'N/A':
                if 'positive' in str(daily_trend).lower() and 'positive' in str(intraday_momentum).lower():
                    multi_timeframe_consistency = '高度一致-上涨'
                elif 'negative' in str(daily_trend).lower() and 'negative' in str(intraday_momentum).lower():
                    multi_timeframe_consistency = '高度一致-下跌'
                else:
                    multi_timeframe_consistency = '分化'
            else:
                multi_timeframe_consistency = 'N/A'

            # 量价背离预警
            volume_price_trend = indicators.get('volume_price_trend', 'N/A')
            volume_amplification = indicators.get('volume_amplification', 'N/A')

            if volume_price_trend != 'N/A' and volume_amplification != 'N/A':
                if '背离' in str(volume_price_trend) or float(str(volume_amplification).replace('N/A', '0')) > 3:
                    volume_price_divergence = '预警'
                else:
                    volume_price_divergence = '正常'
            else:
                volume_price_divergence = 'N/A'

            # 技术形态识别（基于价格位置和波动率）
            price_position = indicators.get('price_position', 0.5)
            volatility = indicators.get('volatility', 0.02)

            if price_position > 0.8 and volatility < 0.03:
                pattern_recognition = '高位整理'
            elif price_position < 0.2 and volatility < 0.03:
                pattern_recognition = '底部构筑'
            elif volatility > 0.05:
                pattern_recognition = '高波动突破'
            else:
                pattern_recognition = '区间震荡'

            return {
                'multi_timeframe_consistency': multi_timeframe_consistency,
                'volume_price_divergence': volume_price_divergence,
                'pattern_recognition': pattern_recognition
            }

        except Exception as e:
            logger.error(f"计算增强分析指标失败: {e}")
            return {
                'multi_timeframe_consistency': 'N/A',
                'volume_price_divergence': 'N/A',
                'pattern_recognition': 'N/A'
            }

    def _get_default_enhanced_data(self) -> Dict:
        """返回默认的增强数据"""
        return {
            'market_beta': 'N/A',
            'hs300_correlation': 'N/A',
            'sector_tech_sync': 'N/A',
            'systematic_tech_risk': 'N/A',
            'ai_factor_score': 'N/A',
            'top_ai_factors': 'N/A',
            'ai_confidence': 'N/A',
            'factor_weights': 'N/A',
            'multi_timeframe_consistency': 'N/A',
            'volume_price_divergence': 'N/A',
            'pattern_recognition': 'N/A'
        }
