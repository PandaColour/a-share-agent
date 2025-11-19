# -*- coding: utf-8 -*-
"""
技术面分析师 - 优化版
集成买点优化功能，右侧交易优先，减少回调后等待时间
"""

import pandas as pd
import numpy as np
from typing import Dict
import logging
import sys
import os

from .base_analyst import BaseAnalyst
from utils.consecutive_change_calculator import calculate_consecutive_changes

# 添加src路径到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# 导入优化模块
try:
    from utils.trend_confirmer import TrendConfirmer
    from utils.buy_point_optimizer import BuyPointOptimizer
    OPTIMIZATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"买点优化模块不可用: {e}")
    OPTIMIZATION_AVAILABLE = False

# 导入AI因子模块
try:
    from factors import get_factor_manager, initialize_factors
    FACTORS_AVAILABLE = True
    initialize_factors()
except ImportError as e:
    logging.warning(f"AI因子模块不可用: {e}")
    FACTORS_AVAILABLE = False

logger = logging.getLogger(__name__)

class TechnicalAnalystOptimized(BaseAnalyst):
    """优化版技术面分析师"""

    def __init__(self):
        super().__init__("technical")

        # 初始化优化模块
        if OPTIMIZATION_AVAILABLE:
            self.buy_point_optimizer = BuyPointOptimizer()
            self.trend_confirmer = TrendConfirmer()
            logger.info("技术分析师优化模块初始化完成")
        else:
            self.buy_point_optimizer = None
            self.trend_confirmer = None
            logger.warning("技术分析师优化模块不可用，使用传统模式")

    def analyze(self, symbol: str, data: pd.DataFrame, info: Dict, indicators: Dict) -> Dict:
        """优化版技术面分析"""

        # 1. 执行传统技术分析
        traditional_analysis = self._traditional_analysis(symbol, data, info, indicators)

        # 2. 如果优化模块可用，执行买点优化
        if OPTIMIZATION_AVAILABLE and self.buy_point_optimizer:
            try:
                optimization_result = self._execute_buy_point_optimization(
                    symbol, data, indicators, traditional_analysis
                )

                # 更新分析结果
                traditional_analysis["buy_optimization"] = optimization_result

                # 根据优化结果调整最终建议
                self._adjust_recommendation_based_on_optimization(traditional_analysis, optimization_result)

                # 添加优化理由
                optimization_reasoning = optimization_result.get("optimization_reasoning", [])
                traditional_analysis["reasoning"].extend(optimization_reasoning)

                # 添加等待时间预警
                wait_days = optimization_result.get("trend_confirmation", {}).get("expected_wait_days", 0)
                if wait_days > 7:
                    traditional_analysis["reasoning"].append(f"⏰ 预期等待时间较长：{wait_days:.1f}天")
                elif wait_days <= 3:
                    traditional_analysis["reasoning"].append(f"🚀 短期确认信号，等待时间约{wait_days:.1f}天")

            except Exception as e:
                logger.error(f"买点优化失败 {symbol}: {e}")
                traditional_analysis["reasoning"].append("⚠️ 买点优化功能异常，使用传统分析")

        # 3. 执行其他增强分析（AI因子等）
        if FACTORS_AVAILABLE:
            try:
                factor_analysis = self._ai_factor_analysis(symbol, data, indicators)
                traditional_analysis.update(factor_analysis)
                traditional_analysis["reasoning"].append("已使用AI因子增强分析")
            except Exception as e:
                logger.error(f"AI因子分析失败: {e}")

        # 4. AI模型增强分析
        ai_config = self.config_manager.get_ai_config()
        if (self.ai_model and self.ai_model.is_available() and
            ai_config.get('enable_ai_analysis', False)):
            try:
                ai_analysis = self._ai_analysis(symbol, data, info, indicators, traditional_analysis)
                traditional_analysis.update(ai_analysis)
                traditional_analysis["reasoning"].append("已使用AI模型增强分析")
            except Exception as e:
                logger.error(f"AI分析失败: {e}")
                traditional_analysis = self._create_ai_failure_response(str(e))

        return traditional_analysis

    def _traditional_analysis(self, symbol: str, data: pd.DataFrame, info: Dict, indicators: Dict) -> Dict:
        """传统技术面分析 - 保持原有逻辑"""
        analysis = {
            "analyst_type": "技术面分析（优化版）",
            "recommendation": "持有",
            "confidence": 0.5,
            "reasoning": [],
            "time_horizon": "medium",  # 技术面分析关注中期(15-30天)
        }

        if not indicators:
            analysis["reasoning"].append("缺乏技术数据")
            return analysis

        # 移动平均线分析
        ma5 = indicators.get('daily_ma5') or indicators.get('ma5', 0)
        ma20 = indicators.get('daily_ma20') or indicators.get('ma20', 0)
        current_price = data['Close'].iloc[-1] if not data.empty else 0

        if ma5 and ma20:
            if ma5 > ma20 and current_price > ma5:
                analysis["reasoning"].append("技术面强势")
                analysis["confidence"] += 0.2
                if analysis["recommendation"] == "持有":
                    analysis["recommendation"] = "买入"
            elif ma5 < ma20 and current_price < ma5:
                analysis["reasoning"].append("技术面疲软")
                analysis["confidence"] -= 0.2
                if analysis["recommendation"] == "持有":
                    analysis["recommendation"] = "卖出"

        # RSI分析
        rsi = indicators.get('daily_rsi') or indicators.get('rsi', 50)
        if rsi and not pd.isna(rsi):
            if rsi > 70:
                analysis["reasoning"].append(f"RSI{rsi:.0f}超买")
                analysis["confidence"] -= 0.1
            elif rsi < 30:
                analysis["reasoning"].append(f"RSI{rsi:.0f}超卖")
                analysis["confidence"] += 0.1

        # MACD分析
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

        # 量价关系分析
        volume_price_trend = indicators.get('daily_volume_price_trend') or indicators.get('volume_price_trend', 'neutral')
        turnover_rate = indicators.get('daily_turnover_rate') or indicators.get('turnover_rate', 0)

        if volume_price_trend == "量价齐升":
            analysis["reasoning"].append("量价配合良好")
            analysis["confidence"] += 0.1
        elif volume_price_trend == "量价背离":
            analysis["reasoning"].append("量价出现背离")
            analysis["confidence"] -= 0.1

        # 连续涨跌分析
        consecutive_stats = calculate_consecutive_changes(data)
        analysis["consecutive_days"] = consecutive_stats["consecutive_days"]
        analysis["consecutive_change"] = consecutive_stats["consecutive_change"]

        # 连续上涨分析
        if consecutive_stats["consecutive_days"] >= 2 and consecutive_stats["consecutive_change"] >= 3.0:
            analysis["reasoning"].append(
                f"🚀 连续上涨{consecutive_stats['consecutive_days']}天累计{consecutive_stats['consecutive_change']:.2f}%，短期动量强劲"
            )
            analysis["confidence"] += 0.15
            if analysis["recommendation"] == "持有":
                analysis["recommendation"] = "买入"

        # 计算上涨天数
        rising_days_10 = self._calculate_rising_days(data, 10)
        if rising_days_10 >= 7:
            analysis["reasoning"].append(f"📈 最近10天中有{rising_days_10}天上涨，短期趋势强劲")
            analysis["confidence"] += 0.1

        # 确保信心度在合理范围内
        analysis["confidence"] = max(0.0, min(1.0, analysis["confidence"]))

        return analysis

    def _execute_buy_point_optimization(self, symbol: str, data: pd.DataFrame,
                                     indicators: Dict, traditional_analysis: Dict) -> Dict:
        """执行买点优化"""

        # 准备优化所需的数据
        current_price = data['Close'].iloc[-1] if not data.empty else 0
        indicators["current_price"] = current_price

        # 执行优化
        optimization_result = self.buy_point_optimizer.optimize_buy_signals(
            symbol, data, indicators, traditional_analysis
        )

        return optimization_result

    def _adjust_recommendation_based_on_optimization(self, analysis: Dict, optimization_result: Dict):
        """根据优化结果调整建议"""

        optimized_score = optimization_result.get("optimized_score", 0)
        buy_recommendation = optimization_result.get("buy_recommendation", "")
        trend_confirmation = optimization_result.get("trend_confirmation", {})

        # 根据优化评分调整信心度
        if optimized_score > 0.7:
            analysis["confidence"] = max(analysis["confidence"], optimized_score)
            if "强烈买入" in buy_recommendation:
                analysis["recommendation"] = "强烈买入"
            elif "买入" in buy_recommendation:
                analysis["recommendation"] = "买入"
        elif optimized_score > 0.5:
            analysis["confidence"] = max(analysis["confidence"], optimized_score * 0.8)
            if "买入" in buy_recommendation:
                analysis["recommendation"] = "买入"
        elif optimized_score < 0.3:
            # 信号很弱时降低建议强度
            if analysis["recommendation"] in ["强烈买入", "买入"]:
                analysis["recommendation"] = "持有"
            analysis["confidence"] = min(analysis["confidence"], 0.4)

        # 根据趋势状态调整
        trend_status = trend_confirmation.get("status", "")
        if "强势下跌" in str(trend_status):
            # 强势下跌时，避免买入建议
            if analysis["recommendation"] in ["强烈买入", "买入"]:
                analysis["recommendation"] = "持有"
            analysis["confidence"] *= 0.7

    def _calculate_rising_days(self, data: pd.DataFrame, days: int) -> int:
        """计算最近N天的上涨天数"""
        try:
            if data is None or data.empty or 'Close' not in data.columns:
                return 0

            if len(data) < 2:
                return 0

            recent_data = data.tail(min(days, len(data)))
            daily_changes = recent_data['Close'].diff()
            rising_days = (daily_changes > 0).sum()

            return int(rising_days)

        except Exception as e:
            logger.error(f"计算上涨天数失败: {e}")
            return 0

    def _ai_factor_analysis(self, symbol: str, data: pd.DataFrame, indicators: Dict,
                           benchmark_data: Dict = None) -> Dict:
        """AI因子增强分析"""
        if not FACTORS_AVAILABLE:
            return {}

        try:
            factor_manager = get_factor_manager()
            factor_data = {
                "price": data,
                "volume": data[['Volume']] if 'Volume' in data.columns else pd.DataFrame()
            }

            if benchmark_data:
                factor_data["market_data"] = benchmark_data.get('hs300_data')
                factor_data["market_state"] = benchmark_data.get('market_state')
                factor_data["stock_beta"] = benchmark_data.get('stock_beta')

            factor_results = factor_manager.calculate_all_factors(
                symbol, factor_data, categories=['technical']
            )

            if not factor_results:
                return {}

            factor_analysis = {
                "ai_factors": {},
                "factor_score": 0.0,
                "factor_confidence": 0.0,
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
                factor_analysis["factor_score"] = total_score / factor_count
                factor_analysis["factor_confidence"] = total_confidence / factor_count

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
            if value > 0.2:
                return "因子显示积极信号"
            elif value < -0.2:
                return "因子显示消极信号"
            else:
                return "因子显示中性信号"

    def _calculate_factor_adjustment(self, factor_score: float) -> Dict:
        """根据AI因子计算调整参数"""
        confidence_adj = 0.0
        if abs(factor_score) > 0.3:
            confidence_adj = min(0.2, abs(factor_score) * 0.5)

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

    def _ai_analysis(self, symbol: str, data: pd.DataFrame, info: Dict,
                    indicators: Dict, traditional_analysis: Dict) -> Dict:
        """AI增强技术面分析"""
        current_price = data['Close'].iloc[-1] if not data.empty else 0
        ma5 = indicators.get('ma5', 'N/A')
        ma20 = indicators.get('ma20', 'N/A')
        rsi = indicators.get('rsi', 'N/A')

        # 获取分析提示词
        prompt_config = self._get_ai_prompt_config()

        # 构建上下文数据
        context = {
            "symbol": symbol,
            "current_price": current_price,
            "ma5": ma5,
            "ma20": ma20,
            "rsi": rsi,
            "traditional_analysis": traditional_analysis
        }

        # 构建用户提示词
        user_prompt = prompt_config["user_prompt"].format(
            symbol=symbol,
            current_price=current_price,
            ma5=ma5,
            ma20=ma20,
            rsi=rsi,
            # 技术分析摘要
            technical_summary=str(traditional_analysis.get("reasoning", [])),
            confidence_score=traditional_analysis.get("confidence", 0.5),
            current_recommendation=traditional_analysis.get("recommendation", "持有")
        )

        # 调用AI模型
        ai_response = self.ai_model.generate_analysis(user_prompt, context)

        # 解析AI响应并增强分析
        ai_recommendation = self._extract_ai_recommendation(ai_response)
        return self._combine_traditional_and_ai_analysis(traditional_analysis, ai_recommendation, ai_response)