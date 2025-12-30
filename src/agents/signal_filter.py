# -*- coding: utf-8 -*-
"""
交易信号过滤器 - 改进买卖时机

解决问题:
1. 买早了 -> 过滤高位买入,等待回调
2. 卖早了 -> 区分回调和反转,避免被震出
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class TradingSignalFilter:
    """
    交易信号过滤器

    核心功能:
    - filter_buy_signal: 过滤不合理的买入信号
    - filter_sell_signal: 过滤不合理的卖出信号
    """

    def __init__(self, config=None):
        """
        初始化信号过滤器

        Args:
            config: 配置对象或字典
        """
        # 从配置中加载参数,如果没有则使用默认值
        filter_config = {}
        if config:
            if hasattr(config, 'get'):
                filter_config = config.get('trading_signal_filter', {})
            elif isinstance(config, dict):
                filter_config = config.get('trading_signal_filter', {})

        # 买入过滤参数
        buy_config = filter_config.get('buy_filter', {})
        self.max_recent_gain = buy_config.get('max_recent_gain_20d', 0.50)  # 最大近期涨幅50%
        self.min_pullback_from_high = buy_config.get('min_pullback_from_high', 0.15)  # 要求从高点回调至少15%
        self.price_position_threshold = buy_config.get('price_position_threshold', 0.80)  # 价格位置阈值80%

        # 卖出过滤参数
        sell_config = filter_config.get('sell_filter', {})
        self.min_holding_days = sell_config.get('min_holding_days', 15)  # 最小持有天数
        self.trend_reversal_threshold = sell_config.get('trend_reversal_threshold', -0.20)  # 趋势反转阈值-20%
        self.stop_loss_in_uptrend = sell_config.get('stop_loss_in_uptrend', -0.25)  # 趋势中的止损线-25%
        self.stop_loss_normal = sell_config.get('stop_loss_normal', -0.15)  # 普通止损线-15%

        # 是否启用过滤器
        self.enabled = filter_config.get('enabled', True)

        logger.info("交易信号过滤器初始化完成")
        logger.info(f"  - 买入过滤: 最大涨幅{self.max_recent_gain:.0%}, 价格位置阈值{self.price_position_threshold:.0%}")
        logger.info(f"  - 卖出过滤: 最小持有{self.min_holding_days}天, 趋势止损{self.stop_loss_in_uptrend:.0%}")

    def filter_buy_signal(self, symbol: str, data: pd.DataFrame,
                         ai_recommendation: str, confidence: float) -> Dict:
        """
        买入信号过滤 - 避免追高买入

        检查:
        1. 近期涨幅是否过大
        2. 是否处于高位区域
        3. 是否有充分回调

        Args:
            symbol: 股票代码
            data: 历史价格数据
            ai_recommendation: AI推荐(买入/卖出/持有)
            confidence: 置信度

        Returns:
            过滤结果字典: {allowed, reason, suggestion, adjusted_confidence}
        """
        if not self.enabled:
            return {"allowed": True, "reason": "过滤器未启用", "adjusted_confidence": confidence}

        if len(data) < 20:
            return {"allowed": True, "reason": "数据不足,无法过滤", "adjusted_confidence": confidence}

        current_price = data['Close'].iloc[-1]

        # 1. 检查价格位置 (20日高低点)
        recent_high_20 = data['High'].tail(20).max()
        recent_low_20 = data['Low'].tail(20).min()

        if recent_high_20 > recent_low_20:
            price_position_20 = (current_price - recent_low_20) / (recent_high_20 - recent_low_20)

            if price_position_20 > self.price_position_threshold:
                suggestion_price = recent_low_20 + (recent_high_20 - recent_low_20) * 0.5
                logger.info(f"[买入过滤] {symbol} 价格位置过高 {price_position_20:.1%} > {self.price_position_threshold:.1%}")
                return {
                    "allowed": False,
                    "reason": f"价格位置过高({price_position_20:.1%}),建议等待回调",
                    "suggestion": f"建议等待回调至{suggestion_price:.2f}元附近(20日中位)",
                    "adjusted_confidence": confidence * 0.5,
                    "filter_name": "price_position_filter"
                }

        # 2. 检查近期涨幅 (20日涨幅)
        if len(data) >= 20:
            price_20d_ago = data['Close'].iloc[-20]
            recent_gain_20d = (current_price - price_20d_ago) / price_20d_ago

            if recent_gain_20d > self.max_recent_gain:
                logger.info(f"[买入过滤] {symbol} 近20日涨幅过大 {recent_gain_20d:.1%} > {self.max_recent_gain:.1%}")
                return {
                    "allowed": False,
                    "reason": f"近20日涨幅过大({recent_gain_20d:.1%}),追高风险较高",
                    "suggestion": "建议等待5-10个交易日的回调后再观察",
                    "adjusted_confidence": confidence * 0.3,
                    "filter_name": "recent_gain_filter"
                }

        # 3. 检查60日高点回调 (如果有大幅上涨,要求充分回调)
        if len(data) >= 60:
            price_60d_high = data['High'].tail(60).max()
            price_60d_start = data['Close'].iloc[-60]
            pullback_from_high = (price_60d_high - current_price) / price_60d_high
            gain_from_60d_start = (price_60d_high - price_60d_start) / price_60d_start

            # 如果60日内涨幅超过30%,要求至少回调15%
            if gain_from_60d_start > 0.3 and pullback_from_high < self.min_pullback_from_high:
                target_price = price_60d_high * (1 - self.min_pullback_from_high)
                logger.info(f"[买入过滤] {symbol} 快速拉升后回调不足 {pullback_from_high:.1%} < {self.min_pullback_from_high:.1%}")
                return {
                    "allowed": False,
                    "reason": f"快速拉升({gain_from_60d_start:.1%})后回调不足({pullback_from_high:.1%})",
                    "suggestion": f"建议等待回调至{target_price:.2f}元附近(从高点回调{self.min_pullback_from_high:.0%})",
                    "adjusted_confidence": confidence * 0.4,
                    "filter_name": "pullback_filter"
                }

        # 通过所有检查,允许买入
        logger.info(f"[买入通过] {symbol} 买入时机合理,置信度: {confidence:.2f}")
        return {
            "allowed": True,
            "reason": "买入时机合理",
            "adjusted_confidence": confidence,
            "filter_name": "passed"
        }

    def filter_sell_signal(self, symbol: str, data: pd.DataFrame,
                          ai_recommendation: str, confidence: float,
                          holding_days: int = 0, buy_price: float = 0.0) -> Dict:
        """
        卖出信号过滤 - 避免过早止损

        检查:
        1. 是否满足最小持有期
        2. 是否是趋势中的正常回调
        3. 止损线设置是否合理

        Args:
            symbol: 股票代码
            data: 历史价格数据
            ai_recommendation: AI推荐
            confidence: 置信度
            holding_days: 持有天数
            buy_price: 买入价格

        Returns:
            过滤结果字典: {allowed, reason, suggestion, adjusted_confidence}
        """
        if not self.enabled:
            return {"allowed": True, "reason": "过滤器未启用", "adjusted_confidence": confidence}

        if len(data) < 20:
            return {"allowed": True, "reason": "数据不足,无法过滤", "adjusted_confidence": confidence}

        current_price = data['Close'].iloc[-1]

        # 如果没有持仓信息,无法过滤,允许卖出
        if buy_price <= 0:
            logger.warning(f"[卖出过滤] {symbol} 没有买入价格信息,无法过滤")
            return {"allowed": True, "reason": "无持仓信息", "adjusted_confidence": confidence}

        # 计算当前收益率
        current_return = (current_price - buy_price) / buy_price

        # 1. 检查最小持有期
        if holding_days < self.min_holding_days:
            # 除非亏损超过普通止损线,否则不允许卖出
            if current_return > self.stop_loss_normal:
                logger.info(f"[卖出过滤] {symbol} 持有时间过短 {holding_days}天 < {self.min_holding_days}天, 当前收益{current_return:.1%}")
                return {
                    "allowed": False,
                    "reason": f"持有时间过短({holding_days}天),建议继续持有",
                    "suggestion": f"最小持有期{self.min_holding_days}天,除非跌破止损线{buy_price * (1 + self.stop_loss_normal):.2f}元",
                    "adjusted_confidence": confidence * 0.3,
                    "filter_name": "min_holding_filter"
                }

        # 2. 判断趋势状态
        trend_state = self._detect_trend(data)
        logger.debug(f"[趋势检测] {symbol} 趋势状态: {trend_state}")

        if trend_state == "上涨":
            # 上涨趋势中,使用更宽松的止损
            if current_return > self.stop_loss_in_uptrend:
                # 计算从持有期间最高点的回撤
                if holding_days > 0 and holding_days <= len(data):
                    max_price_since_buy = data['High'].tail(holding_days).max()
                    drawdown_from_peak = (max_price_since_buy - current_price) / max_price_since_buy
                else:
                    # 使用20日最高点作为替代
                    max_price_since_buy = data['High'].tail(20).max()
                    drawdown_from_peak = (max_price_since_buy - current_price) / max_price_since_buy

                # 如果回撤小于反转阈值,认为是正常回调
                if drawdown_from_peak < abs(self.trend_reversal_threshold):
                    stop_loss_price = buy_price * (1 + self.stop_loss_in_uptrend)
                    logger.info(f"[卖出过滤] {symbol} 上涨趋势中的正常回调 {drawdown_from_peak:.1%}, 当前收益{current_return:.1%}")
                    return {
                        "allowed": False,
                        "reason": f"上涨趋势中的正常回调({drawdown_from_peak:.1%}),未达反转阈值",
                        "suggestion": f"建议继续持有,趋势止损线: {stop_loss_price:.2f}元({self.stop_loss_in_uptrend:.0%})",
                        "adjusted_confidence": confidence * 0.4,
                        "filter_name": "trend_pullback_filter"
                    }

        # 3. 检查是否真的需要止损
        if current_return < 0:  # 亏损状态
            if trend_state == "上涨":
                # 在上涨趋势中,只有跌破趋势止损线才卖出
                if current_return > self.stop_loss_in_uptrend:
                    logger.info(f"[卖出过滤] {symbol} 趋势未破坏,当前亏损{current_return:.1%}未达止损线{self.stop_loss_in_uptrend:.0%}")
                    return {
                        "allowed": False,
                        "reason": f"趋势未破坏,当前亏损({current_return:.1%})未达止损线",
                        "suggestion": f"趋势向上,建议继续持有,止损线: {buy_price * (1 + self.stop_loss_in_uptrend):.2f}元",
                        "adjusted_confidence": confidence * 0.5,
                        "filter_name": "stop_loss_filter"
                    }
            elif trend_state == "震荡":
                # 在震荡市中,使用普通止损线
                if current_return > self.stop_loss_normal:
                    logger.info(f"[卖出过滤] {symbol} 震荡市,当前亏损{current_return:.1%}未达止损线{self.stop_loss_normal:.0%}")
                    return {
                        "allowed": False,
                        "reason": f"震荡市中,当前亏损({current_return:.1%})未达止损线",
                        "suggestion": f"建议继续观察,止损线: {buy_price * (1 + self.stop_loss_normal):.2f}元",
                        "adjusted_confidence": confidence * 0.6,
                        "filter_name": "stop_loss_filter"
                    }

        # 通过检查,允许卖出
        logger.info(f"[卖出通过] {symbol} 卖出时机合理,当前收益{current_return:.1%}, 持有{holding_days}天, 趋势{trend_state}")
        return {
            "allowed": True,
            "reason": f"卖出时机合理(收益{current_return:.1%}, 持有{holding_days}天, 趋势{trend_state})",
            "adjusted_confidence": confidence,
            "filter_name": "passed"
        }

    def _detect_trend(self, data: pd.DataFrame) -> str:
        """
        检测趋势状态

        Args:
            data: 历史价格数据

        Returns:
            趋势状态: "上涨" / "下跌" / "震荡"
        """
        if len(data) < 20:
            return "未知"

        # 计算短期、中期、长期均线
        ma5 = data['Close'].tail(5).mean()
        ma20 = data['Close'].tail(20).mean()
        ma60 = data['Close'].tail(min(60, len(data))).mean()

        # 多头排列: MA5 > MA20 > MA60
        if ma5 > ma20 > ma60:
            return "上涨"
        # 空头排列: MA5 < MA20 < MA60
        elif ma5 < ma20 < ma60:
            return "下跌"
        # 其他情况视为震荡
        else:
            return "震荡"
