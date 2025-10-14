# -*- coding: utf-8 -*-
"""
市场增强AI因子
利用市场数据（沪深300）和市场状态来增强个股分析
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
from datetime import datetime

from .factor_manager import BaseFactor, FactorValue

logger = logging.getLogger(__name__)


class MarketBetaAdjustedFactor(BaseFactor):
    """市场Beta调整因子

    考虑个股Beta系数，在不同市场环境下调整因子权重
    """

    def __init__(self):
        super().__init__(
            name="market_beta_adjusted",
            category="technical",
            description="根据市场Beta和市场状态调整的技术因子"
        )
        self.dependencies = ["price", "market_data"]

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算市场Beta调整因子"""
        try:
            price_df = data.get("price")
            market_df = data.get("market_data")
            market_state = data.get("market_state")
            stock_beta = data.get("stock_beta")

            if price_df is None or len(price_df) < 20:
                return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3,
                                 raw_data={"error": "insufficient_price_data"})

            # 如果没有市场数据，降级到纯技术分析
            if market_df is None or len(market_df) < 20:
                logger.debug(f"{symbol}: 无市场数据，使用纯技术分析")
                return self._fallback_technical_analysis(price_df, symbol)

            # 计算个股动量
            stock_momentum = self._calculate_momentum(price_df, window=20)

            # 计算市场动量
            market_momentum = self._calculate_momentum(market_df, window=20)

            # 获取Beta系数（如果没有提供，简单估算）
            if stock_beta is None or stock_beta == 0:
                stock_beta = self._estimate_beta(price_df, market_df)

            # 根据市场状态调整
            market_adjustment = self._get_market_adjustment(market_state, stock_beta)

            # 综合评分
            # 1. 个股动量 (40%)
            # 2. 市场动量 * Beta (30%)
            # 3. 市场状态调整 (30%)
            base_score = (
                stock_momentum * 0.4 +
                market_momentum * stock_beta * 0.3 +
                market_adjustment * 0.3
            )

            # 标准化到[-1, 1]
            final_score = np.tanh(base_score)

            # 置信度基于数据质量
            confidence = self._calculate_confidence(price_df, market_df, market_state)

            return FactorValue(
                symbol=symbol,
                factor_name=self.name,
                value=final_score,
                timestamp=datetime.now(),
                confidence=confidence,
                raw_data={
                    "stock_momentum": stock_momentum,
                    "market_momentum": market_momentum,
                    "stock_beta": stock_beta,
                    "market_adjustment": market_adjustment,
                    "market_state": str(market_state) if market_state else None
                }
            )

        except Exception as e:
            logger.error(f"市场Beta调整因子计算失败 {symbol}: {e}")
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.2,
                             raw_data={"error": str(e)})

    def _calculate_momentum(self, df: pd.DataFrame, window: int = 20) -> float:
        """计算动量"""
        try:
            close_col = 'Close' if 'Close' in df.columns else 'close'
            if close_col not in df.columns:
                return 0.0

            prices = df[close_col].tail(window)
            if len(prices) < window:
                return 0.0

            # 简单动量：当前价格 / N日前价格 - 1
            momentum = (prices.iloc[-1] / prices.iloc[0]) - 1
            return float(momentum)

        except Exception as e:
            logger.error(f"动量计算失败: {e}")
            return 0.0

    def _estimate_beta(self, stock_df: pd.DataFrame, market_df: pd.DataFrame,
                      window: int = 60) -> float:
        """估算Beta系数"""
        try:
            close_col = 'Close' if 'Close' in stock_df.columns else 'close'

            # 计算收益率
            stock_returns = stock_df[close_col].pct_change().dropna()
            market_returns = market_df[close_col].pct_change().dropna()

            # 对齐日期
            common_dates = stock_returns.index.intersection(market_returns.index)
            if len(common_dates) < window:
                return 1.0  # 默认Beta

            stock_aligned = stock_returns.loc[common_dates].tail(window)
            market_aligned = market_returns.loc[common_dates].tail(window)

            # 计算Beta
            covariance = np.cov(stock_aligned, market_aligned)[0, 1]
            market_variance = np.var(market_aligned)

            if market_variance == 0:
                return 1.0

            beta = covariance / market_variance
            return float(np.clip(beta, -3, 3))  # 限制范围

        except Exception as e:
            logger.error(f"Beta估算失败: {e}")
            return 1.0

    def _get_market_adjustment(self, market_state: Optional[Dict],
                              stock_beta: float) -> float:
        """根据市场状态和Beta获取调整系数"""
        if not market_state:
            return 0.0

        try:
            # 获取市场趋势
            trend = market_state.get('trend')
            if not trend:
                return 0.0

            trend_str = str(trend) if hasattr(trend, 'value') else str(trend)

            # 市场暴跌场景
            if '暴跌' in trend_str or 'CRASH' in trend_str:
                # 高Beta股票受影响大，给负分
                if stock_beta > 1.2:
                    return -0.8
                elif stock_beta > 0.8:
                    return -0.4
                else:
                    return -0.2  # 低Beta相对防御

            # 市场急跌场景
            elif '急跌' in trend_str or 'STRONG_BEAR' in trend_str:
                if stock_beta > 1.3:
                    return -0.6
                elif stock_beta > 1.0:
                    return -0.3
                else:
                    return -0.1

            # 市场温和下跌
            elif '下跌' in trend_str or 'BEAR' in trend_str:
                if stock_beta > 1.2:
                    return -0.3
                else:
                    return -0.1

            # 市场上涨场景
            elif '上涨' in trend_str or 'BULL' in trend_str:
                # 高Beta在上涨市中表现更好
                if stock_beta > 1.2:
                    return 0.6
                elif stock_beta > 0.8:
                    return 0.3
                else:
                    return 0.1

            # 市场震荡
            else:
                return 0.0

        except Exception as e:
            logger.error(f"市场调整计算失败: {e}")
            return 0.0

    def _calculate_confidence(self, stock_df: pd.DataFrame,
                            market_df: pd.DataFrame,
                            market_state: Optional[Dict]) -> float:
        """计算置信度"""
        confidence = 0.5

        # 数据点越多，置信度越高
        if len(stock_df) >= 60:
            confidence += 0.2
        elif len(stock_df) >= 30:
            confidence += 0.1

        # 有市场数据
        if market_df is not None and len(market_df) >= 60:
            confidence += 0.15

        # 有市场状态信息
        if market_state and market_state.get('confidence', 0) > 0.7:
            confidence += 0.15

        return min(confidence, 0.95)

    def _fallback_technical_analysis(self, price_df: pd.DataFrame,
                                    symbol: str) -> FactorValue:
        """无市场数据时的降级技术分析"""
        try:
            close_col = 'Close' if 'Close' in price_df.columns else 'close'

            # 简单动量
            momentum = self._calculate_momentum(price_df, window=20)

            # 价格趋势（MA5 vs MA20）
            prices = price_df[close_col]
            ma5 = prices.rolling(5).mean().iloc[-1]
            ma20 = prices.rolling(20).mean().iloc[-1]

            trend_score = 0.0
            if ma5 > ma20:
                trend_score = 0.3
            elif ma5 < ma20:
                trend_score = -0.3

            # 综合评分
            score = momentum * 0.7 + trend_score * 0.3
            final_score = np.tanh(score)

            return FactorValue(
                symbol=symbol,
                factor_name=self.name,
                value=final_score,
                timestamp=datetime.now(),
                confidence=0.4,  # 降级模式置信度较低
                raw_data={
                    "mode": "fallback_technical",
                    "momentum": momentum,
                    "trend_score": trend_score
                }
            )

        except Exception as e:
            logger.error(f"降级技术分析失败 {symbol}: {e}")
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.2,
                             raw_data={"error": str(e)})


class MarketRelativeStrengthFactor(BaseFactor):
    """市场相对强度因子

    衡量个股相对市场的强度
    """

    def __init__(self):
        super().__init__(
            name="market_relative_strength",
            category="technical",
            description="个股相对市场的强度指标"
        )
        self.dependencies = ["price", "market_data"]

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算相对强度因子"""
        try:
            price_df = data.get("price")
            market_df = data.get("market_data")

            if price_df is None or len(price_df) < 20:
                return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3)

            # 没有市场数据则返回中性
            if market_df is None or len(market_df) < 20:
                return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3,
                                 raw_data={"error": "no_market_data"})

            close_col = 'Close' if 'Close' in price_df.columns else 'close'

            # 计算多个时间窗口的相对强度
            windows = [5, 10, 20]
            rs_scores = []

            for window in windows:
                if len(price_df) >= window and len(market_df) >= window:
                    # 个股收益率
                    stock_return = (price_df[close_col].iloc[-1] /
                                  price_df[close_col].iloc[-window] - 1)

                    # 市场收益率
                    market_return = (market_df[close_col].iloc[-1] /
                                   market_df[close_col].iloc[-window] - 1)

                    # 相对强度 = 个股收益 - 市场收益
                    rs = stock_return - market_return
                    rs_scores.append(rs)

            if not rs_scores:
                return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3)

            # 加权平均（短期权重更高）
            weights = [0.5, 0.3, 0.2]
            weighted_rs = sum(score * weight for score, weight
                            in zip(rs_scores, weights))

            # 标准化
            final_score = np.tanh(weighted_rs * 5)  # 放大5倍再tanh

            return FactorValue(
                symbol=symbol,
                factor_name=self.name,
                value=final_score,
                timestamp=datetime.now(),
                confidence=0.75,
                raw_data={
                    "rs_5d": rs_scores[0] if len(rs_scores) > 0 else None,
                    "rs_10d": rs_scores[1] if len(rs_scores) > 1 else None,
                    "rs_20d": rs_scores[2] if len(rs_scores) > 2 else None,
                    "weighted_rs": weighted_rs
                }
            )

        except Exception as e:
            logger.error(f"相对强度因子计算失败 {symbol}: {e}")
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.2,
                             raw_data={"error": str(e)})
