#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
趋势确认器 - 确认股票是否真正开始上升趋势
避免在下跌过程中过早买入，等待右侧交易信号确认
"""

from enum import Enum
from dataclasses import dataclass
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

from .buy_point_config import get_buy_point_config

logger = logging.getLogger(__name__)

class TrendStatus(Enum):
    """趋势状态枚举"""
    STRONG_DOWNTREND = "强势下跌"
    WEAK_DOWNTREND = "弱势下跌"
    CONSOLIDATION = "横盘整理"
    EARLY_UPTREND = "早期上涨"
    CONFIRMED_UPTREND = "确认上涨"

@dataclass
class TrendConfirmation:
    """趋势确认结果"""
    status: TrendStatus
    confidence: float
    confirmation_signals: List[str]
    expected_wait_days: float
    risk_level: str  # "高", "中", "低"
    raw_score: float  # 原始评分

class TrendConfirmer:
    """趋势确认器"""

    def __init__(self):
        self.confirmation_requirements = {
            TrendStatus.EARLY_UPTREND: {
                "min_price_gain": 0.015,  # 1.5%涨幅
                "volume_multiplier": 1.3,  # 1.3倍成交量
                "consecutive_up_days": 2   # 连续2天上涨
            },
            TrendStatus.CONFIRMED_UPTREND: {
                "min_price_gain": 0.03,   # 3%涨幅
                "volume_multiplier": 1.5,  # 1.5倍成交量
                "consecutive_up_days": 3,  # 连续3天上涨
                "ma_breakthrough": True    # 突破均线
            }
        }

        logger.info("趋势确认器初始化完成")

    def confirm_trend(self, data: pd.DataFrame, indicators: Dict) -> TrendConfirmation:
        """
        确认当前趋势状态

        Args:
            data: 股票价格数据
            indicators: 技术指标数据

        Returns:
            TrendConfirmation: 趋势确认结果
        """
        try:
            # 数据验证
            if len(data) < 10:
                logger.warning("数据不足10天，无法确认趋势")
                return self._create_default_confirmation()

            # 1. 计算基础指标
            recent_gain = self._calculate_recent_gain(data)
            volume_ratio = self._calculate_volume_ratio(data)
            consecutive_up = self._calculate_consecutive_up_days(data)

            # 2. 评估信号强度
            signals = []
            confidence = 0.0
            raw_score = 0.0

            # 从配置文件获取参数
            config = get_buy_point_config()
            trend_config = config.get('trend_confirmation', {})

            min_gain_threshold = trend_config.get('min_gain_threshold', 0.015)
            volume_multiplier = trend_config.get('volume_multiplier', 1.3)
            consecutive_up_days = trend_config.get('consecutive_up_days', 2)

            # 价格涨幅信号（使用配置参数）
            if recent_gain >= min_gain_threshold:
                signals.append(f"✅ 近期涨幅{recent_gain*100:.1f}%")
                confidence += 0.3
                raw_score += 0.25
            elif recent_gain >= min_gain_threshold * 0.5:  # 一半阈值
                signals.append(f"📈 微弱涨幅{recent_gain*100:.1f}%")
                confidence += 0.15
                raw_score += 0.10

            # 成交量信号（使用配置参数）
            if volume_ratio >= volume_multiplier:
                signals.append(f"📈 成交量放大{volume_ratio:.1f}倍")
                confidence += 0.3
                raw_score += 0.25
            elif volume_ratio >= volume_multiplier * 0.8:  # 80%的阈值
                signals.append(f"📊 成交量温和放大{volume_ratio:.1f}倍")
                confidence += 0.15
                raw_score += 0.10

            # 连续上涨信号（使用配置参数）
            if consecutive_up >= consecutive_up_days + 1:
                signals.append(f"📊 连续上涨{consecutive_up}天")
                confidence += 0.25
                raw_score += 0.20
            elif consecutive_up >= consecutive_up_days:
                signals.append(f"📈 连续上涨{consecutive_up}天")
                confidence += 0.15
                raw_score += 0.10

            # 3. 技术指标确认
            ma_signals = self._check_ma_signals(data, indicators)
            signals.extend(ma_signals["signals"])
            confidence += ma_signals["confidence"]
            raw_score += ma_signals["score"]

            # 4. 动量信号检查
            momentum_signals = self._check_momentum_signals(indicators)
            signals.extend(momentum_signals["signals"])
            confidence += momentum_signals["confidence"]
            raw_score += momentum_signals["score"]

            # 5. 综合评估趋势状态
            trend_result = self._evaluate_trend_status(confidence, raw_score, signals)

            logger.debug(f"趋势确认完成: {trend_result.status.value}, 信心度: {trend_result.confidence:.2f}")
            return trend_result

        except Exception as e:
            logger.error(f"趋势确认失败: {e}")
            return self._create_default_confirmation()

    def _calculate_recent_gain(self, data: pd.DataFrame) -> float:
        """计算近期涨幅"""
        try:
            if len(data) < 3:
                return 0.0

            # 使用最近3天的涨幅
            start_price = data['Close'].iloc[-3]
            end_price = data['Close'].iloc[-1]

            if start_price <= 0:
                return 0.0

            return (end_price - start_price) / start_price

        except Exception as e:
            logger.error(f"计算近期涨幅失败: {e}")
            return 0.0

    def _calculate_volume_ratio(self, data: pd.DataFrame) -> float:
        """计算成交量比率"""
        try:
            if 'Volume' not in data.columns or len(data) < 8:
                return 1.0

            # 最近3天平均成交量 vs 前5天平均成交量
            recent_volume = data['Volume'].tail(3).mean()
            prev_volume = data['Volume'].iloc[-8:-3].mean()

            if prev_volume <= 0:
                return 1.0

            return recent_volume / prev_volume

        except Exception as e:
            logger.error(f"计算成交量比率失败: {e}")
            return 1.0

    def _calculate_consecutive_up_days(self, data: pd.DataFrame) -> int:
        """计算连续上涨天数"""
        try:
            if len(data) < 2:
                return 0

            consecutive_days = 0
            for i in range(len(data) - 1, 0, -1):
                current_price = data['Close'].iloc[i]
                prev_price = data['Close'].iloc[i-1]

                if current_price > prev_price:
                    consecutive_days += 1
                else:
                    break

            return consecutive_days

        except Exception as e:
            logger.error(f"计算连续上涨天数失败: {e}")
            return 0

    def _check_ma_signals(self, data: pd.DataFrame, indicators: Dict) -> Dict:
        """检查均线信号"""
        result = {"signals": [], "confidence": 0.0, "score": 0.0}

        try:
            ma5 = indicators.get('daily_ma5', 0)
            ma20 = indicators.get('daily_ma20', 0)
            current_price = data['Close'].iloc[-1] if not data.empty else 0

            if ma5 > 0 and ma20 > 0:
                # 均线多头排列
                if ma5 > ma20 and current_price > ma5:
                    result["signals"].append(f"💥 均线多头排列，价格{current_price:.2f} > MA5{ma5:.2f} > MA20{ma20:.2f}")
                    result["confidence"] += 0.2
                    result["score"] += 0.15

                # 价格突破均线
                elif current_price > ma20 * 1.02:  # 突破MA20至少2%
                    result["signals"].append(f"🚀 突破MA20均线{(current_price-ma20)/ma20*100:.1f}%")
                    result["confidence"] += 0.15
                    result["score"] += 0.10

                # 均线转向
                elif ma5 > ma20:
                    result["signals"].append(f"📈 MA5{ma5:.2f}上穿MA20{ma20:.2f}")
                    result["confidence"] += 0.1
                    result["score"] += 0.05

        except Exception as e:
            logger.error(f"检查均线信号失败: {e}")

        return result

    def _check_momentum_signals(self, indicators: Dict) -> Dict:
        """检查动量信号"""
        result = {"signals": [], "confidence": 0.0, "score": 0.0}

        try:
            # RSI信号
            rsi = indicators.get('daily_rsi', 50)
            if 45 <= rsi <= 70:  # 健康的RSI区间
                result["signals"].append(f"💪 RSI{rsi:.0f}处于健康区间")
                result["confidence"] += 0.1
                result["score"] += 0.08

            # MACD信号
            macd = indicators.get('daily_macd', 0)
            macd_signal = indicators.get('daily_macd_signal', 0)
            macd_histogram = indicators.get('daily_macd_histogram', 0)

            if macd > macd_signal and macd_histogram > 0:
                result["signals"].append("⚡ MACD金叉向上")
                result["confidence"] += 0.15
                result["score"] += 0.12

            # KDJ信号
            kdj_k = indicators.get('daily_kdj_k', 50)
            kdj_d = indicators.get('daily_kdj_d', 50)

            if kdj_k > kdj_d and kdj_k < 80:  # 金叉且未超买
                result["signals"].append(f"🎯 KDJ金叉(K{kdj_k:.0f}>D{kdj_d:.0f})")
                result["confidence"] += 0.1
                result["score"] += 0.08

        except Exception as e:
            logger.error(f"检查动量信号失败: {e}")

        return result

    def _evaluate_trend_status(self, confidence: float, raw_score: float,
                             signals: List[str]) -> TrendConfirmation:
        """评估趋势状态"""

        # 根据评分确定趋势状态
        if confidence >= 0.8 and raw_score >= 0.7:
            status = TrendStatus.CONFIRMED_UPTREND
            expected_wait = 2.0
            risk_level = "低"
        elif confidence >= 0.6 and raw_score >= 0.5:
            status = TrendStatus.EARLY_UPTREND
            expected_wait = 5.0
            risk_level = "中"
        elif confidence >= 0.3 and raw_score >= 0.2:
            status = TrendStatus.CONSOLIDATION
            expected_wait = 10.0
            risk_level = "中"
        elif confidence >= 0.15:
            status = TrendStatus.WEAK_DOWNTREND
            expected_wait = 15.0
            risk_level = "高"
        else:
            status = TrendStatus.STRONG_DOWNTREND
            expected_wait = 20.0
            risk_level = "高"

        # 调整信心度范围
        adjusted_confidence = max(0.0, min(1.0, confidence))

        return TrendConfirmation(
            status=status,
            confidence=adjusted_confidence,
            confirmation_signals=signals,
            expected_wait_days=expected_wait,
            risk_level=risk_level,
            raw_score=raw_score
        )

    def _create_default_confirmation(self) -> TrendConfirmation:
        """创建默认的确认结果"""
        return TrendConfirmation(
            status=TrendStatus.CONSOLIDATION,
            confidence=0.0,
            confirmation_signals=["⚠️ 数据不足，无法确认趋势"],
            expected_wait_days=7.0,
            risk_level="高",
            raw_score=0.0
        )

    def get_trend_color(self, status: TrendStatus) -> str:
        """获取趋势状态对应的颜色"""
        color_map = {
            TrendStatus.CONFIRMED_UPTREND: "🟢",
            TrendStatus.EARLY_UPTREND: "🟡",
            TrendStatus.CONSOLIDATION: "⚪",
            TrendStatus.WEAK_DOWNTREND: "🟠",
            TrendStatus.STRONG_DOWNTREND: "🔴"
        }
        return color_map.get(status, "⚪")

    def should_buy_now(self, confirmation: TrendConfirmation,
                      min_confidence: float = 0.6) -> Tuple[bool, str]:
        """
        判断是否应该现在买入

        Args:
            confirmation: 趋势确认结果
            min_confidence: 最小信心度阈值

        Returns:
            Tuple[bool, str]: (是否应该买入, 原因)
        """
        should_buy = confirmation.confidence >= min_confidence

        if confirmation.status == TrendStatus.CONFIRMED_UPTREND:
            reason = "✅ 趋势确认上涨，量价配合良好"
            should_buy = True
        elif confirmation.status == TrendStatus.EARLY_UPTREND and confirmation.confidence >= 0.5:
            reason = "📈 早期上涨趋势，可小仓位试探"
            should_buy = True
        elif confirmation.status == TrendStatus.CONSOLIDATION:
            reason = "⏳ 横盘整理中，建议继续观察"
            should_buy = False
        elif confirmation.status in [TrendStatus.WEAK_DOWNTREND, TrendStatus.STRONG_DOWNTREND]:
            reason = "📉 仍在下跌趋势中，不建议买入"
            should_buy = False
        else:
            reason = f"⚠️ 信号不明确，信心度{confirmation.confidence:.1f}"
            should_buy = False

        return should_buy, reason