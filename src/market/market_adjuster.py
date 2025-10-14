# -*- coding: utf-8 -*-
"""
市场调整器
根据市场状态和个股Beta调整投资建议
"""

import logging
from typing import Dict, Tuple
from .market_state import MarketTrend

logger = logging.getLogger(__name__)


class MarketAdjuster:
    """市场调整器 - 根据市场状态调整个股建议"""

    def __init__(self, config_manager=None):
        """
        初始化市场调整器

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.enabled = True

        if config_manager:
            market_config = config_manager.get('analysis_settings.market_analysis', {})
            self.enabled = market_config.get('enabled', True)

        logger.info(f"🎯 市场调整器初始化: {'已启用' if self.enabled else '已禁用'}")

    def adjust_recommendation(self,
                            original_rec: str,
                            original_confidence: float,
                            market_state: Dict,
                            stock_beta: float = 1.0) -> Tuple[str, float, str]:
        """
        根据市场状态调整个股建议

        调整逻辑：
        1. 市场暴跌/极高风险 → 强制降级（买入→持有，持有→卖出）
        2. 市场急跌/高风险 → 谨慎降级
        3. 高Beta股票在下跌市场中加大调整力度
        4. 市场上涨时增强买入信心

        Args:
            original_rec: 原始建议（买入/持有/卖出/强烈买入/强烈卖出）
            original_confidence: 原始置信度
            market_state: 市场状态字典
            stock_beta: 个股Beta系数

        Returns:
            Tuple[str, float, str]: (调整后建议, 调整后置信度, 调整理由)
        """
        if not self.enabled:
            return original_rec, original_confidence, "市场调整已禁用"

        trend = market_state.get('trend', MarketTrend.NEUTRAL)
        risk_level = market_state.get('risk_level', '中')
        daily_return = market_state.get('daily_return', 0.0)

        adjustment_reasons = []
        adjusted_rec = original_rec
        adjusted_confidence = original_confidence

        # ========== 暴跌/极高风险场景 ==========
        if trend == MarketTrend.CRASH or risk_level == "极高":
            adjusted_rec, adjusted_confidence, reason = self._handle_crash_scenario(
                original_rec, original_confidence, daily_return, stock_beta
            )
            adjustment_reasons.append(reason)

        # ========== 急跌/高风险场景 ==========
        elif trend == MarketTrend.STRONG_BEAR or risk_level == "高":
            adjusted_rec, adjusted_confidence, reason = self._handle_strong_bear_scenario(
                original_rec, original_confidence, daily_return, stock_beta
            )
            adjustment_reasons.append(reason)

        # ========== 温和下跌场景 ==========
        elif trend == MarketTrend.MODERATE_BEAR:
            adjusted_rec, adjusted_confidence, reason = self._handle_moderate_bear_scenario(
                original_rec, original_confidence, stock_beta
            )
            adjustment_reasons.append(reason)

        # ========== 震荡场景 ==========
        elif trend == MarketTrend.NEUTRAL:
            adjustment_reasons.append("市场震荡，维持原判断")

        # ========== 上涨场景 ==========
        elif trend in [MarketTrend.MODERATE_BULL, MarketTrend.STRONG_BULL]:
            adjusted_rec, adjusted_confidence, reason = self._handle_bull_scenario(
                original_rec, original_confidence, daily_return, stock_beta
            )
            adjustment_reasons.append(reason)

        # 如果没有调整，说明原判断合理
        if not adjustment_reasons:
            adjustment_reasons.append("市场状态与个股判断一致，无需调整")

        reason_str = "；".join(adjustment_reasons)

        logger.info(f"📊 市场调整: {original_rec}({original_confidence:.2%}) → "
                   f"{adjusted_rec}({adjusted_confidence:.2%})")
        logger.debug(f"   理由: {reason_str}")

        return adjusted_rec, adjusted_confidence, reason_str

    def _handle_crash_scenario(self,
                               original_rec: str,
                               original_confidence: float,
                               daily_return: float,
                               stock_beta: float) -> Tuple[str, float, str]:
        """处理暴跌/极高风险场景"""
        adjusted_rec = original_rec
        adjusted_confidence = original_confidence
        reason = ""

        if original_rec in ["买入", "强烈买入"]:
            adjusted_rec = "持有"
            adjusted_confidence = min(adjusted_confidence + 0.15, 0.95)
            reason = f"市场暴跌({daily_return:.2%})，买入降级为持有"

        elif original_rec == "持有":
            if stock_beta > 1.2:
                adjusted_rec = "卖出"
                adjusted_confidence = min(adjusted_confidence + 0.2, 0.95)
                reason = f"市场暴跌+高Beta({stock_beta:.2f})，持有降级为卖出"
            else:
                adjusted_confidence = min(adjusted_confidence + 0.1, 0.9)
                reason = f"市场暴跌但低Beta({stock_beta:.2f})，维持持有"

        else:  # 原本就是卖出
            adjusted_confidence = min(adjusted_confidence + 0.1, 0.95)
            reason = f"市场暴跌，强化卖出信号"

        return adjusted_rec, adjusted_confidence, reason

    def _handle_strong_bear_scenario(self,
                                     original_rec: str,
                                     original_confidence: float,
                                     daily_return: float,
                                     stock_beta: float) -> Tuple[str, float, str]:
        """处理急跌/高风险场景"""
        adjusted_rec = original_rec
        adjusted_confidence = original_confidence
        reason = ""

        if original_rec in ["买入", "强烈买入"]:
            adjusted_rec = "持有"
            adjusted_confidence = min(adjusted_confidence + 0.1, 0.9)
            reason = f"市场急跌({daily_return:.2%})，买入降级为持有"

        elif original_rec == "持有":
            if stock_beta > 1.3:
                adjusted_rec = "卖出"
                adjusted_confidence = min(adjusted_confidence + 0.15, 0.9)
                reason = f"市场下跌+超高Beta({stock_beta:.2f})，建议减仓"
            elif stock_beta > 1.1:
                adjusted_confidence = max(adjusted_confidence - 0.05, 0.5)
                reason = f"市场下跌+高Beta({stock_beta:.2f})，降低持有信心"
            else:
                reason = f"市场下跌但Beta适中({stock_beta:.2f})，维持持有"

        else:  # 卖出
            adjusted_confidence = min(adjusted_confidence + 0.05, 0.9)
            reason = f"市场下跌，强化卖出信号"

        return adjusted_rec, adjusted_confidence, reason

    def _handle_moderate_bear_scenario(self,
                                       original_rec: str,
                                       original_confidence: float,
                                       stock_beta: float) -> Tuple[str, float, str]:
        """处理温和下跌场景"""
        adjusted_rec = original_rec
        adjusted_confidence = original_confidence
        reason = ""

        if original_rec in ["买入", "强烈买入"] and stock_beta > 1.2:
            adjusted_confidence = max(adjusted_confidence - 0.05, 0.5)
            reason = f"市场下跌+高Beta({stock_beta:.2f})，降低买入信心"
        else:
            reason = "市场温和下跌，维持原判断"

        return adjusted_rec, adjusted_confidence, reason

    def _handle_bull_scenario(self,
                             original_rec: str,
                             original_confidence: float,
                             daily_return: float,
                             stock_beta: float) -> Tuple[str, float, str]:
        """处理上涨场景"""
        adjusted_rec = original_rec
        adjusted_confidence = original_confidence
        reason = ""

        if original_rec in ["买入", "强烈买入"]:
            if stock_beta > 1.1:
                adjusted_confidence = min(adjusted_confidence + 0.08, 0.95)
                reason = f"市场上涨({daily_return:.2%})+高Beta({stock_beta:.2f})，增强买入信心"
            else:
                adjusted_confidence = min(adjusted_confidence + 0.05, 0.95)
                reason = f"市场上涨({daily_return:.2%})，增强买入信心"

        elif original_rec == "持有" and stock_beta > 1.2:
            reason = f"市场上涨+高Beta({stock_beta:.2f})，考虑适度加仓"

        else:
            reason = "市场上涨，维持原判断"

        return adjusted_rec, adjusted_confidence, reason


# 便捷函数
def adjust_recommendation_by_market(original_rec: str,
                                   original_confidence: float,
                                   market_state: Dict,
                                   stock_beta: float = 1.0,
                                   config_manager=None) -> Tuple[str, float, str]:
    """
    根据市场状态调整建议的便捷函数

    Args:
        original_rec: 原始建议
        original_confidence: 原始置信度
        market_state: 市场状态
        stock_beta: 个股Beta
        config_manager: 配置管理器

    Returns:
        Tuple[str, float, str]: (调整后建议, 调整后置信度, 调整理由)
    """
    adjuster = MarketAdjuster(config_manager)
    return adjuster.adjust_recommendation(
        original_rec, original_confidence, market_state, stock_beta
    )