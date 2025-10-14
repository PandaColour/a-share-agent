# -*- coding: utf-8 -*-
"""
市场状态监控器
实时监控市场整体状态，识别系统性风险
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class MarketTrend(Enum):
    """市场趋势枚举"""
    STRONG_BULL = "强势上涨"      # > +2%
    MODERATE_BULL = "温和上涨"    # +0.5% ~ +2%
    NEUTRAL = "震荡整理"          # -0.5% ~ +0.5%
    MODERATE_BEAR = "温和下跌"    # -2% ~ -0.5%
    STRONG_BEAR = "急跌恐慌"      # < -2%
    CRASH = "暴跌崩盘"            # < -4%


class MarketMonitor:
    """市场状态监控器"""

    def __init__(self, config_manager=None):
        """
        初始化市场监控器

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.market_config = {}

        if config_manager:
            self.market_config = config_manager.get('analysis_settings.market_analysis', {})

        self.enabled = self.market_config.get('enabled', True)
        self.benchmark_symbol = '000300'  # 沪深300

        logger.info(f"🌐 市场监控器初始化: {'已启用' if self.enabled else '已禁用'}")

    def get_market_state(self, data_provider, date: Optional[str] = None) -> Dict:
        """
        获取市场整体状态

        Args:
            data_provider: 数据提供者
            date: 指定日期，None表示最新

        Returns:
            Dict: 市场状态详情，包含：
                - trend: 市场趋势
                - daily_return: 今日涨跌幅
                - returns_5d: 5日涨跌幅
                - returns_20d: 20日涨跌幅
                - volatility_20d: 20日年化波动率
                - risk_level: 风险等级（低/中/高/极高）
                - suggested_action: 建议操作
                - timestamp: 时间戳
                - confidence: 置信度
        """
        if not self.enabled:
            logger.warning("⚠️ 市场监控已禁用")
            return self._default_market_state()

        try:
            # 获取沪深300数据作为市场基准
            benchmark_data = self._get_benchmark_data(data_provider, self.benchmark_symbol, days=250)

            if benchmark_data is None or len(benchmark_data) < 20:
                logger.warning("⚠️ 沪深300数据不足，使用默认市场状态")
                return self._default_market_state()

            # 分析市场状态
            market_state = self._analyze_market_state(benchmark_data)

            logger.info(f"📊 市场状态: {market_state['trend'].value}, "
                       f"今日: {market_state['daily_return']:.2%}, "
                       f"风险: {market_state['risk_level']}")

            return market_state

        except Exception as e:
            logger.error(f"❌ 获取市场状态失败: {e}")
            return self._default_market_state()

    def _get_benchmark_data(self, data_provider, symbol: str, days: int = 250) -> Optional[pd.DataFrame]:
        """
        获取基准指数数据

        Args:
            data_provider: 数据提供者
            symbol: 指数代码
            days: 获取天数

        Returns:
            pd.DataFrame: 指数数据
        """
        try:
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # 获取指数数据
            data = data_provider.get_stock_data(
                symbol,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )

            if data is not None and len(data) > 0:
                logger.debug(f"✅ 获取 {symbol} 数据: {len(data)} 条")
                return data
            else:
                logger.warning(f"⚠️ {symbol} 数据为空")
                return None

        except Exception as e:
            logger.error(f"❌ 获取 {symbol} 数据失败: {e}")
            return None

    def _analyze_market_state(self, market_data: pd.DataFrame) -> Dict:
        """
        分析市场状态

        Args:
            market_data: 市场数据

        Returns:
            Dict: 市场状态分析结果
        """
        # 确保数据按日期排序
        if not market_data.index.is_monotonic_increasing:
            market_data = market_data.sort_index()

        # 计算收益率 (支持大小写列名)
        close_col = 'Close' if 'Close' in market_data.columns else 'close'
        returns = market_data[close_col].pct_change()

        # 今日涨跌幅
        daily_return = returns.iloc[-1]

        # 近期涨跌幅
        returns_5d = (market_data[close_col].iloc[-1] / market_data[close_col].iloc[-6] - 1) \
            if len(market_data) >= 6 else 0
        returns_20d = (market_data[close_col].iloc[-1] / market_data[close_col].iloc[-21] - 1) \
            if len(market_data) >= 21 else 0

        # 判断趋势
        trend = self._determine_trend(daily_return)

        # 波动率（年化）
        volatility_20d = returns.tail(20).std() * np.sqrt(252) if len(returns) >= 20 else 0.2

        # 风险等级
        risk_level = self._assess_risk_level(daily_return, returns_5d, volatility_20d)

        # 建议操作
        suggested_action = self._suggest_action(trend, risk_level)

        # 置信度
        confidence = self._calculate_confidence(market_data)

        return {
            "trend": trend,
            "daily_return": daily_return,
            "returns_5d": returns_5d,
            "returns_20d": returns_20d,
            "volatility_20d": volatility_20d,
            "risk_level": risk_level,
            "suggested_action": suggested_action,
            "timestamp": datetime.now().isoformat(),
            "confidence": confidence,
            "benchmark": self.benchmark_symbol
        }

    def _determine_trend(self, daily_return: float) -> MarketTrend:
        """
        判断市场趋势

        Args:
            daily_return: 日收益率

        Returns:
            MarketTrend: 市场趋势
        """
        if daily_return > 0.04:
            return MarketTrend.STRONG_BULL
        elif daily_return > 0.02:
            return MarketTrend.MODERATE_BULL
        elif daily_return > 0.005:
            return MarketTrend.NEUTRAL
        elif daily_return > -0.005:
            return MarketTrend.NEUTRAL
        elif daily_return > -0.02:
            return MarketTrend.MODERATE_BEAR
        elif daily_return > -0.04:
            return MarketTrend.STRONG_BEAR
        else:
            return MarketTrend.CRASH

    def _assess_risk_level(self, daily_return: float, returns_5d: float, volatility: float) -> str:
        """
        评估风险等级

        Args:
            daily_return: 日收益率
            returns_5d: 5日收益率
            volatility: 波动率

        Returns:
            str: 风险等级
        """
        risk_score = 0

        # 日内跌幅贡献
        if daily_return < -0.04:
            risk_score += 3
        elif daily_return < -0.02:
            risk_score += 2
        elif daily_return < -0.01:
            risk_score += 1

        # 近期走势贡献
        if returns_5d < -0.05:
            risk_score += 2
        elif returns_5d < -0.02:
            risk_score += 1

        # 波动率贡献
        if volatility > 0.40:
            risk_score += 2
        elif volatility > 0.25:
            risk_score += 1

        # 风险等级映射
        if risk_score >= 5:
            return "极高"
        elif risk_score >= 3:
            return "高"
        elif risk_score >= 1:
            return "中"
        else:
            return "低"

    def _suggest_action(self, trend: MarketTrend, risk_level: str) -> str:
        """
        建议操作

        Args:
            trend: 市场趋势
            risk_level: 风险等级

        Returns:
            str: 建议操作
        """
        if trend == MarketTrend.CRASH or risk_level == "极高":
            return "全面规避"
        elif trend == MarketTrend.STRONG_BEAR or risk_level == "高":
            return "谨慎持有"
        elif trend == MarketTrend.MODERATE_BEAR:
            return "等待观望"
        elif trend == MarketTrend.NEUTRAL:
            return "正常操作"
        elif trend == MarketTrend.MODERATE_BULL:
            return "积极配置"
        else:  # STRONG_BULL
            return "追涨谨慎"

    def _calculate_confidence(self, market_data: pd.DataFrame) -> float:
        """
        计算置信度

        Args:
            market_data: 市场数据

        Returns:
            float: 置信度
        """
        data_points = len(market_data)

        if data_points >= 60:
            return 0.9
        elif data_points >= 20:
            return 0.7
        else:
            return 0.5

    def _default_market_state(self) -> Dict:
        """
        默认市场状态（数据不可用时）

        Returns:
            Dict: 默认市场状态
        """
        return {
            "trend": MarketTrend.NEUTRAL,
            "daily_return": 0.0,
            "returns_5d": 0.0,
            "returns_20d": 0.0,
            "volatility_20d": 0.20,
            "risk_level": "中",
            "suggested_action": "正常操作",
            "timestamp": datetime.now().isoformat(),
            "confidence": 0.0,
            "benchmark": self.benchmark_symbol
        }


# 便捷函数
def get_market_state(data_provider, config_manager=None) -> Dict:
    """
    获取市场状态的便捷函数

    Args:
        data_provider: 数据提供者
        config_manager: 配置管理器

    Returns:
        Dict: 市场状态
    """
    monitor = MarketMonitor(config_manager)
    return monitor.get_market_state(data_provider)