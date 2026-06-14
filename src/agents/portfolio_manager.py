# -*- coding: utf-8 -*-
"""投资组合经理 - 简化版本，只支持AI因子分析"""

from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from src.trade.decision import TradingDecision
import logging

logger = logging.getLogger(__name__)


class PortfolioManager:
    def __init__(self):
        # 内部初始化配置管理器,简化依赖传递
        from config.config_manager import get_config
        self.config_manager = get_config()

        logger.info("投资组合管理器初始化完成，使用AI因子分析决策")

    def make_decision(self, symbol: str, analyses: List[Dict], risk_assessment: Dict,
                     price_info: Dict = None, data: pd.DataFrame = None,
                     position_info: Dict = None) -> TradingDecision:
        """
        基于AI因子分析的决策方法

        Args:
            symbol: 股票代码
            analyses: 分析结果列表(应该只包含AI因子分析)
            risk_assessment: 风险评估结果
            price_info: 价格信息
            data: 历史价格数据
            position_info: 持仓信息 {buy_price, holding_days}

        Returns:
            TradingDecision: 交易决策
        """
        if price_info is None:
            price_info = {}

        # 检查是否有分析结果
        if not analyses or len(analyses) == 0:
            logger.warning(f"没有可用的分析结果: {symbol}")
            return TradingDecision(
                action="无法决策",
                confidence=0.0,
                reason="没有可用的分析结果",
                risk_level="未知",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                current_price=price_info.get("current_price", 0.0),
                daily_high=price_info.get("daily_high", 0.0),
                daily_low=price_info.get("daily_low", 0.0),
                daily_change=price_info.get("daily_change", 0.0),
                daily_change_percent=price_info.get("daily_change_percent", 0.0)
            )

        # 使用AI因子分析结果进行决策
        logger.info(f"使用AI因子分析进行决策: {symbol}")
        return self._make_ai_factor_decision(symbol, analyses, risk_assessment, price_info)

    def _make_ai_factor_decision(self, symbol: str, analyses: List[Dict],
                                 risk_assessment: Dict, price_info: Dict) -> TradingDecision:
        """基于AI因子分析的决策"""
        # 获取AI因子分析结果(应该只有一个)
        ai_analysis = analyses[0] if analyses else None

        if not ai_analysis:
            return TradingDecision(
                action="无法决策",
                confidence=0.0,
                reason="AI因子分析结果为空",
                risk_level="未知",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

        # 获取AI因子的推荐和置信度
        recommendation = ai_analysis.get("recommendation", "持有")
        confidence = ai_analysis.get("confidence", 0.5)
        reasoning = ai_analysis.get("reasoning", [])

        # 风险调整
        risk_score = risk_assessment.get("risk_score", 0.5)
        risk_level = risk_assessment.get("risk_level", "中等")
        risk_factors = risk_assessment.get("risk_factors", [])

        # 根据风险等级调整置信度
        if risk_level == "高":
            adjusted_confidence = confidence * 0.7  # 高风险降低30%置信度
        elif risk_level == "极高":
            adjusted_confidence = confidence * 0.5  # 极高风险降低50%置信度
        else:
            adjusted_confidence = confidence * (1 - risk_score * 0.3)

        # 生成决策理由
        reason_parts = []

        # 添加AI因子分析的主要理由
        if reasoning:
            reason_parts.extend(reasoning[:2])  # 只取前2条理由

        # 添加风险因素
        if risk_factors:
            reason_parts.append(f"风险: {risk_factors[0]}")

        # 创建决策对象
        decision = TradingDecision(
            action=recommendation,
            confidence=max(0, min(1, adjusted_confidence)),
            reason=" | ".join(reason_parts) if reason_parts else "AI因子分析",
            risk_level=risk_level,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            current_price=price_info.get("current_price", 0.0),
            daily_high=price_info.get("daily_high", 0.0),
            daily_low=price_info.get("daily_low", 0.0),
            daily_change=price_info.get("daily_change", 0.0),
            daily_change_percent=price_info.get("daily_change_percent", 0.0)
        )

        # 基于AI因子分析结果计算价格区间
        current_price = price_info.get("current_price", 0.0)
        if current_price > 0:
            price_range = self._estimate_price_range_from_ai_factors(ai_analysis, current_price)
            if price_range:
                decision.price_range_low = price_range.get("low", 0.0)
                decision.price_range_high = price_range.get("high", 0.0)
                # 计算上涨空间
                if price_range.get("high", 0) > current_price:
                    decision.upside_potential = (price_range["high"] - current_price) / current_price * 100

        logger.info(f"AI因子决策完成 {symbol}: {decision.action} (信心度: {decision.confidence:.2f})")

        return decision

    def _estimate_price_range_from_ai_factors(self, ai_analysis: Dict, current_price: float) -> Dict:
        """基于AI因子分析结果估算价格区间"""
        if current_price <= 0:
            return None

        # 获取AI因子的置信度和推荐
        confidence = ai_analysis.get("confidence", 0.5)
        recommendation = ai_analysis.get("recommendation", "持有")

        # 根据推荐和置信度计算价格区间
        if recommendation == "买入":
            # 买入建议，设置较高的价格区间
            low = current_price * (1 - 0.05 * (1 - confidence))
            high = current_price * (1 + 0.15 * confidence)
        elif recommendation.startswith("卖出"):
            # 卖出建议，设置较低的价格区间
            low = current_price * (1 - 0.15 * confidence)
            high = current_price * (1 + 0.05 * (1 - confidence))
        else:
            # 持有建议，设置对称区间
            range_factor = 0.1 * confidence
            low = current_price * (1 - range_factor)
            high = current_price * (1 + range_factor)

        return {
            "low": round(low, 2),
            "high": round(high, 2),
            "confidence": confidence
        }
