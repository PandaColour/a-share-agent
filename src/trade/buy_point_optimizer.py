#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
买点优化器 - 优化买入信号识别，减少回调后等待时间
右侧交易优先，左侧交易确认的混合模式
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging

from .trend_confirmer import TrendConfirmer, TrendConfirmation, TrendStatus

logger = logging.getLogger(__name__)

class BuyPointOptimizer:
    """买点优化器"""

    def __init__(self):
        # 从配置文件加载参数
        import sys
        import os
        # 添加config路径
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config')
        if config_dir not in sys.path:
            sys.path.insert(0, config_dir)

        from config_manager import get_buy_point_config
        config = get_buy_point_config()

        self.trend_confirmer = TrendConfirmer()

        # 从配置文件获取信号权重
        self.signal_weights = config.get('signal_weights', {
            "right_side": 0.75,
            "left_side": 0.25
        })

        # 从配置文件获取信号类型权重
        signal_types = config.get('signal_types', {})
        self.signal_type_weights = {
            # 右侧交易信号（确认性）
            "breakthrough": signal_types.get('right_side_signals', {}).get('breakthrough', 0.3),
            "volume_surge": signal_types.get('right_side_signals', {}).get('volume_surge', 0.25),
            "ma_alignment": signal_types.get('right_side_signals', {}).get('ma_alignment', 0.2),
            "momentum_confirm": signal_types.get('right_side_signals', {}).get('momentum_confirm', 0.25),

            # 左侧交易信号（预测性）
            "oversold": signal_types.get('left_side_signals', {}).get('oversold', 0.15),
            "support_level": signal_types.get('left_side_signals', {}).get('support_level', 0.15),
            "undervalued": signal_types.get('left_side_signals', {}).get('undervalued', 0.1),
            "contrarian": signal_types.get('left_side_signals', {}).get('contrarian', 0.1)
        }

        logger.info("买点优化器初始化完成（使用配置文件参数）")

    def optimize_buy_signals(self, symbol: str, data: pd.DataFrame,
                           indicators: Dict, traditional_signals: Dict) -> Dict:
        """
        优化买入信号

        Args:
            symbol: 股票代码
            data: 价格数据
            indicators: 技术指标
            traditional_signals: 传统分析信号

        Returns:
            Dict: 优化后的买点分析结果
        """
        try:
            # 1. 趋势确认
            trend_confirmation = self.trend_confirmer.confirm_trend(data, indicators)

            # 2. 信号分类和提取
            signal_analysis = self._analyze_and_classify_signals(traditional_signals, indicators)

            # 3. 计算优化后的信号强度
            optimization_result = self._calculate_optimization_score(
                signal_analysis, trend_confirmation
            )

            # 4. 生成买入建议
            buy_recommendation = self._generate_buy_recommendation(
                optimization_result, trend_confirmation
            )

            # 5. 计算动态仓位
            position_strategy = self._calculate_dynamic_position_strategy(
                optimization_result, trend_confirmation
            )

            # 6. 生成优化理由
            optimization_reasoning = self._generate_optimization_reasoning(
                trend_confirmation, signal_analysis, optimization_result
            )

            return {
                "symbol": symbol,
                "optimized_score": optimization_result["score"],
                "trend_confirmation": trend_confirmation,
                "buy_recommendation": buy_recommendation,
                "position_strategy": position_strategy,
                "signal_analysis": signal_analysis,
                "optimization_reasoning": optimization_reasoning,
                "expected_performance": self._estimate_performance(
                    optimization_result, trend_confirmation
                )
            }

        except Exception as e:
            logger.error(f"买点优化失败 {symbol}: {e}")
            return self._create_fallback_result(symbol)

    def _analyze_and_classify_signals(self, traditional_signals: Dict, indicators: Dict) -> Dict:
        """分析和分类信号"""

        signal_analysis = {
            "right_side_signals": [],
            "left_side_signals": [],
            "signal_summary": {
                "total_right_score": 0.0,
                "total_left_score": 0.0,
                "signal_balance": 0.0
            }
        }

        try:
            reasoning = traditional_signals.get("reasoning", [])
            confidence = traditional_signals.get("confidence", 0.5)

            # 提取右侧交易信号（确认性信号）
            right_signals = self._extract_right_side_signals(reasoning, indicators, confidence)
            signal_analysis["right_side_signals"] = right_signals
            signal_analysis["signal_summary"]["total_right_score"] = sum(s["weight"] for s in right_signals)

            # 提取左侧交易信号（预测性信号）
            left_signals = self._extract_left_side_signals(reasoning, indicators, confidence)
            signal_analysis["left_side_signals"] = left_signals
            signal_analysis["signal_summary"]["total_left_score"] = sum(s["weight"] for s in left_signals)

            # 计算信号平衡度
            total_score = signal_analysis["signal_summary"]["total_right_score"] + signal_analysis["signal_summary"]["total_left_score"]
            if total_score > 0:
                signal_analysis["signal_summary"]["signal_balance"] = (
                    signal_analysis["signal_summary"]["total_right_score"] / total_score
                )

        except Exception as e:
            logger.error(f"信号分类分析失败: {e}")

        return signal_analysis

    def _extract_right_side_signals(self, reasoning: List[str], indicators: Dict,
                                  base_confidence: float) -> List[Dict]:
        """提取右侧交易信号（确认性信号）"""

        right_signals = []

        try:
            # 突破信号关键词
            breakthrough_keywords = ["突破", "放量", "金叉", "量价齐升", "多头排列", "向上突破"]

            # 均线信号
            ma5 = indicators.get('daily_ma5', 0)
            ma20 = indicators.get('daily_ma20', 0)
            current_price = indicators.get('current_price', 0)

            if ma5 > ma20 and current_price > ma5:
                right_signals.append({
                    "type": "ma_alignment",
                    "content": f"均线多头排列 (价格{current_price:.2f} > MA5{ma5:.2f} > MA20{ma20:.2f})",
                    "weight": self.signal_type_weights["ma_alignment"],
                    "confidence": base_confidence * 0.9
                })

            # 检查推理内容中的信号
            for reason in reasoning:
                reason_lower = reason.lower()

                # 突破类信号
                for keyword in breakthrough_keywords:
                    if keyword in reason_lower:
                        signal_type = "breakthrough" if "突破" in reason_lower else "volume_surge"
                        right_signals.append({
                            "type": signal_type,
                            "content": reason,
                            "weight": self.signal_type_weights.get(signal_type, 0.2),
                            "confidence": base_confidence * 0.85
                        })
                        break

            # 成交量信号
            volume_ratio = self._calculate_volume_ratio(indicators)
            if volume_ratio >= 1.5:
                right_signals.append({
                    "type": "volume_surge",
                    "content": f"成交量显著放大{volume_ratio:.1f}倍",
                    "weight": self.signal_type_weights["volume_surge"] * min(volume_ratio/2, 1.5),
                    "confidence": base_confidence * 0.8
                })

            # MACD金叉信号
            macd = indicators.get('daily_macd', 0)
            macd_signal = indicators.get('daily_macd_signal', 0)
            if macd > macd_signal:
                right_signals.append({
                    "type": "momentum_confirm",
                    "content": "MACD金叉确认向上趋势",
                    "weight": self.signal_type_weights["momentum_confirm"],
                    "confidence": base_confidence * 0.75
                })

        except Exception as e:
            logger.error(f"提取右侧信号失败: {e}")

        return right_signals

    def _extract_left_side_signals(self, reasoning: List[str], indicators: Dict,
                                 base_confidence: float) -> List[Dict]:
        """提取左侧交易信号（预测性信号）"""

        left_signals = []

        try:
            # 超卖信号关键词
            oversold_keywords = ["超卖", "超跌", "下轨", "超买", "超买区域"]

            # 估值信号关键词
            value_keywords = ["pe低", "低估", "破净", "便宜", "价值"]

            # 检查推理内容
            for reason in reasoning:
                reason_lower = reason.lower()

                # 超卖类信号
                for keyword in oversold_keywords:
                    if keyword in reason_lower:
                        left_signals.append({
                            "type": "oversold",
                            "content": reason,
                            "weight": self.signal_type_weights["oversold"],
                            "confidence": base_confidence * 0.6  # 左侧信号信心度较低
                        })
                        break

                # 价值类信号
                for keyword in value_keywords:
                    if keyword in reason_lower:
                        left_signals.append({
                            "type": "undervalued",
                            "content": reason,
                            "weight": self.signal_type_weights["undervalued"],
                            "confidence": base_confidence * 0.65
                        })
                        break

            # RSI超卖信号（加强判断：不仅要超卖，还要开始回升）
            rsi = indicators.get('daily_rsi', 50)
            if rsi < 25:  # 从30提高到25，更极端的超卖
                # 检查RSI是否开始回升（相比前一天）
                rsi_prev = indicators.get('daily_rsi_prev', rsi)
                if rsi > rsi_prev:  # RSI开始回升
                    left_signals.append({
                        "type": "oversold",
                        "content": f"RSI{rsi:.0f}极度超卖且开始回升",
                        "weight": self.signal_type_weights["oversold"] * 1.3,
                        "confidence": base_confidence * 0.75
                    })
                else:
                    # RSI超卖但仍在下降，降低权重
                    left_signals.append({
                        "type": "oversold",
                        "content": f"RSI{rsi:.0f}超卖但仍在下探",
                        "weight": self.signal_type_weights["oversold"] * 0.5,
                        "confidence": base_confidence * 0.4
                    })

            # MACD底背离检查（新增）
            macd = indicators.get('daily_macd', 0)
            macd_signal = indicators.get('daily_macd_signal', 0)
            macd_histogram = indicators.get('daily_macd_histogram', 0)

            if macd < 0 and macd > macd_signal:  # MACD在0轴下方金叉
                left_signals.append({
                    "type": "contrarian",
                    "content": "MACD在低位出现金叉信号",
                    "weight": self.signal_type_weights["contrarian"] * 1.5,
                    "confidence": base_confidence * 0.7
                })

            # 布林带下轨信号
            price_position = indicators.get('price_position', 0.5)
            if price_position < 0.2:
                left_signals.append({
                    "type": "support_level",
                    "content": "价格接近布林带下轨支撑位",
                    "weight": self.signal_type_weights["support_level"],
                    "confidence": base_confidence * 0.6
                })

        except Exception as e:
            logger.error(f"提取左侧信号失败: {e}")

        return left_signals

    def _calculate_optimization_score(self, signal_analysis: Dict,
                                    trend_confirmation: TrendConfirmation) -> Dict:
        """计算优化后的信号强度"""

        try:
            right_score = signal_analysis["signal_summary"]["total_right_score"]
            left_score = signal_analysis["signal_summary"]["total_left_score"]

            # 基础加权分数
            base_score = (
                right_score * self.signal_weights["right_side"] +
                left_score * self.signal_weights["left_side"]
            )

            # 趋势确认调整
            trend_multiplier = self._get_trend_multiplier(trend_confirmation)

            # 信号平衡调整
            balance_bonus = self._calculate_balance_bonus(signal_analysis["signal_summary"]["signal_balance"])

            # 最终优化分数
            optimized_score = min(base_score * trend_multiplier + balance_bonus, 1.0)

            return {
                "score": optimized_score,
                "base_score": base_score,
                "trend_multiplier": trend_multiplier,
                "balance_bonus": balance_bonus,
                "signal_quality": self._assess_signal_quality(right_score, left_score, trend_confirmation)
            }

        except Exception as e:
            logger.error(f"计算优化分数失败: {e}")
            return {"score": 0.0, "base_score": 0.0, "trend_multiplier": 1.0, "balance_bonus": 0.0, "signal_quality": "低"}

    def _get_trend_multiplier(self, trend_confirmation: TrendConfirmation) -> float:
        """根据趋势状态获取乘数"""

        multiplier_map = {
            TrendStatus.CONFIRMED_UPTREND: 1.5,  # 确认上涨：大幅加成
            TrendStatus.EARLY_UPTREND: 1.2,      # 早期上涨：小幅加成
            TrendStatus.CONSOLIDATION: 1.0,      # 横盘整理：无调整
            TrendStatus.WEAK_DOWNTREND: 0.7,     # 弱势下跌：大幅扣分
            TrendStatus.STRONG_DOWNTREND: 0.5    # 强势下跌：严重扣分
        }

        return multiplier_map.get(trend_confirmation.status, 1.0)

    def _calculate_balance_bonus(self, signal_balance: float) -> float:
        """计算信号平衡奖励"""

        # 右侧信号比例越高，奖励越多
        if signal_balance >= 0.7:  # 右侧信号占70%以上
            return 0.1
        elif signal_balance >= 0.5:  # 右侧信号占50%以上
            return 0.05
        else:
            return 0.0

    def _assess_signal_quality(self, right_score: float, left_score: float,
                             trend_confirmation: TrendConfirmation) -> str:
        """评估信号质量"""

        total_score = right_score + left_score

        if total_score >= 0.8 and right_score >= 0.4:
            return "优秀"
        elif total_score >= 0.6 and right_score >= 0.3:
            return "良好"
        elif total_score >= 0.4:
            return "一般"
        else:
            return "较差"

    def _generate_buy_recommendation(self, optimization_result: Dict,
                                   trend_confirmation: TrendConfirmation) -> str:
        """生成买入建议"""

        optimized_score = optimization_result["score"]
        signal_quality = optimization_result["signal_quality"]

        # 综合评估
        if trend_confirmation.status == TrendStatus.CONFIRMED_UPTREND and optimized_score > 0.7:
            return "强烈买入 - 趋势确认上涨，量价配合良好"
        elif trend_confirmation.status == TrendStatus.EARLY_UPTREND and optimized_score > 0.5:
            return "买入 - 早期上涨趋势，可开始建仓"
        elif optimized_score > 0.6 and signal_quality in ["优秀", "良好"]:
            return "买入 - 信号质量良好，可考虑建仓"
        elif optimized_score > 0.4:
            return "观察 - 信号中性，可小仓位试探"
        elif trend_confirmation.status == TrendStatus.CONSOLIDATION:
            return "等待 - 趋势不明，继续观察"
        else:
            return "暂停 - 信号不足，不建议买入"

    def _calculate_dynamic_position_strategy(self, optimization_result: Dict,
                                           trend_confirmation: TrendConfirmation) -> Dict:
        """计算动态仓位策略"""

        try:
            optimized_score = optimization_result["score"]
            signal_quality = optimization_result["signal_quality"]

            # 基础仓位
            base_position = 0.1  # 10%

            # 信号强度调整
            strength_multiplier = self._get_strength_multiplier(optimized_score)

            # 趋势状态调整
            trend_multiplier = self._get_trend_position_multiplier(trend_confirmation)

            # 信号质量调整
            quality_multiplier = self._get_quality_multiplier(signal_quality)

            # 风险调整
            risk_adjustment = self._get_risk_adjustment(trend_confirmation)

            # 最终仓位
            final_position = base_position * strength_multiplier * trend_multiplier * quality_multiplier + risk_adjustment

            # 限制仓位范围
            final_position = max(0.05, min(final_position, 0.3))  # 5%-30%

            return {
                "recommended_position": final_position,
                "position_rationale": self._generate_position_rationale(
                    base_position, strength_multiplier, trend_multiplier, quality_multiplier, risk_adjustment
                ),
                "risk_level": trend_confirmation.risk_level,
                "scaling_plan": self._generate_scaling_plan(optimized_score, trend_confirmation)
            }

        except Exception as e:
            logger.error(f"计算仓位策略失败: {e}")
            return self._create_default_position_strategy()

    def _get_strength_multiplier(self, optimized_score: float) -> float:
        """获取强度乘数"""
        if optimized_score > 0.8:
            return 1.5
        elif optimized_score > 0.6:
            return 1.2
        elif optimized_score > 0.4:
            return 1.0
        else:
            return 0.6

    def _get_trend_position_multiplier(self, trend_confirmation: TrendConfirmation) -> float:
        """获取趋势仓位乘数"""
        multiplier_map = {
            TrendStatus.CONFIRMED_UPTREND: 1.4,
            TrendStatus.EARLY_UPTREND: 1.1,
            TrendStatus.CONSOLIDATION: 0.8,
            TrendStatus.WEAK_DOWNTREND: 0.5,
            TrendStatus.STRONG_DOWNTREND: 0.3
        }
        return multiplier_map.get(trend_confirmation.status, 1.0)

    def _get_quality_multiplier(self, signal_quality: str) -> float:
        """获取质量乘数"""
        quality_map = {
            "优秀": 1.2,
            "良好": 1.1,
            "一般": 1.0,
            "较差": 0.8
        }
        return quality_map.get(signal_quality, 1.0)

    def _get_risk_adjustment(self, trend_confirmation: TrendConfirmation) -> float:
        """获取风险调整"""
        if trend_confirmation.risk_level == "高":
            return -0.02  # 减少仓位
        elif trend_confirmation.risk_level == "低":
            return 0.02   # 增加仓位
        else:
            return 0.0

    def _generate_position_rationale(self, base_pos: float, strength_mul: float,
                                   trend_mul: float, quality_mul: float,
                                   risk_adj: float) -> str:
        """生成仓位理由"""
        return (f"基础{base_pos*100:.0f}% × 强度{strength_mul:.1f} × "
                f"趋势{trend_mul:.1f} × 质量{quality_mul:.1f} + 风险调整{risk_adj*100:+.0f}%")

    def _generate_scaling_plan(self, optimized_score: float,
                             trend_confirmation: TrendConfirmation) -> Dict:
        """生成分批建仓计划"""

        if optimized_score > 0.7 and trend_confirmation.status in [TrendStatus.CONFIRMED_UPTREND, TrendStatus.EARLY_UPTREND]:
            return {
                "strategy": "分批建仓",
                "first_batch": "40%",
                "second_batch": "30% (等待回调至5日线)",
                "third_batch": "30% (突破前高时)",
                "time_horizon": "2-3周内完成"
            }
        elif optimized_score > 0.5:
            return {
                "strategy": "试探性建仓",
                "first_batch": "30%",
                "second_batch": "70% (趋势确认后)",
                "time_horizon": "观察3-5天"
            }
        else:
            return {
                "strategy": "观望为主",
                "first_batch": "0%",
                "action": "等待更好时机",
                "time_horizon": "继续观察"
            }

    def _generate_optimization_reasoning(self, trend_confirmation: TrendConfirmation,
                                        signal_analysis: Dict,
                                        optimization_result: Dict) -> List[str]:
        """生成优化理由"""

        reasoning = []

        # 趋势状态说明
        trend_color = self.trend_confirmer.get_trend_color(trend_confirmation.status)
        reasoning.append(f"{trend_color} 趋势状态：{trend_confirmation.status.value}")

        # 确认信号说明
        if trend_confirmation.confirmation_signals:
            reasoning.append(f"确认信号：{'; '.join(trend_confirmation.confirmation_signals[:3])}")

        # 信号质量说明
        signal_quality = optimization_result["signal_quality"]
        reasoning.append(f"信号质量：{signal_quality} (评分{optimization_result['score']:.2f})")

        # 右侧交易优势说明
        right_count = len(signal_analysis["right_side_signals"])
        left_count = len(signal_analysis["left_side_signals"])
        reasoning.append(f"信号分布：右侧{right_count}个，左侧{left_count}个")

        # 等待时间说明
        wait_days = trend_confirmation.expected_wait_days
        if wait_days <= 3:
            reasoning.append(f"⚡ 短期确认信号，预计等待时间{wait_days:.1f}天")
        elif wait_days <= 7:
            reasoning.append(f"📊 中期观察信号，预计等待时间{wait_days:.1f}天")
        else:
            reasoning.append(f"⏰ 长期观察信号，预计等待时间{wait_days:.1f}天")

        return reasoning

    def _estimate_performance(self, optimization_result: Dict,
                            trend_confirmation: TrendConfirmation) -> Dict:
        """估算预期表现"""

        base_return = 0.05  # 基础预期收益5%

        # 根据信号强度调整
        strength_adjustment = optimization_result["score"] * 0.1  # 最高额外10%

        # 根据趋势状态调整
        trend_adjustment_map = {
            TrendStatus.CONFIRMED_UPTREND: 0.05,
            TrendStatus.EARLY_UPTREND: 0.03,
            TrendStatus.CONSOLIDATION: 0.0,
            TrendStatus.WEAK_DOWNTREND: -0.02,
            TrendStatus.STRONG_DOWNTREND: -0.05
        }
        trend_adjustment = trend_adjustment_map.get(trend_confirmation.status, 0.0)

        expected_return = base_return + strength_adjustment + trend_adjustment
        success_probability = min(0.8, optimization_result["score"] * 1.2)

        return {
            "expected_return_30d": expected_return,
            "success_probability": success_probability,
            "confidence_level": trend_confirmation.confidence,
            "risk_assessment": trend_confirmation.risk_level
        }

    def _calculate_volume_ratio(self, indicators: Dict) -> float:
        """计算成交量比率"""
        try:
            volume_ratio = indicators.get('intraday_volume_ratio', 1.0)
            return max(1.0, volume_ratio)
        except:
            return 1.0

    def _create_fallback_result(self, symbol: str) -> Dict:
        """创建备用结果"""
        return {
            "symbol": symbol,
            "optimized_score": 0.0,
            "trend_confirmation": TrendConfirmation(
                status=TrendStatus.CONSOLIDATION,
                confidence=0.0,
                confirmation_signals=["优化功能异常"],
                expected_wait_days=7.0,
                risk_level="高",
                raw_score=0.0
            ),
            "buy_recommendation": "暂停 - 优化功能异常",
            "position_strategy": self._create_default_position_strategy(),
            "signal_analysis": {"right_side_signals": [], "left_side_signals": [], "signal_summary": {}},
            "optimization_reasoning": ["⚠️ 买点优化功能出现异常，使用传统分析方法"],
            "expected_performance": {"expected_return_30d": 0.0, "success_probability": 0.3}
        }

    def _create_default_position_strategy(self) -> Dict:
        """创建默认仓位策略"""
        return {
            "recommended_position": 0.05,  # 5%最小仓位
            "position_rationale": "保守策略 - 最小试探仓位",
            "risk_level": "高",
            "scaling_plan": {"strategy": "观望为主", "action": "等待更好时机"}
        }