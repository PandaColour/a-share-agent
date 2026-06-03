# -*- coding: utf-8 -*-
"""
增强动量因子
包含加速动量、跳空缺口、趋势延续性、历史分位数等高级动量指标
"""

import pandas as pd
import numpy as np
from typing import Dict
import logging
from datetime import datetime
from scipy import stats
from scipy.signal import find_peaks

from .factor_manager import BaseFactor, FactorValue

logger = logging.getLogger(__name__)


class AccelerationMomentumFactor(BaseFactor):
    """动量加速度因子 - 检测动量变化率"""

    def __init__(self):
        super().__init__(
            name="acceleration_momentum",
            category="momentum",
            description="动量加速度因子，检测短期动量相对中期动量的加速/减速"
        )
        self.dependencies = ["price"]
        self.lookback_days = 25

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算动量加速度"""
        closes = data['price']['Close'].tail(self.lookback_days)

        if len(closes) < 20:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.5)

        # 短期动量 (5天)
        mom_5d = (closes.iloc[-1] - closes.iloc[-5]) / closes.iloc[-5]

        # 中期动量 (20天)
        mom_20d = (closes.iloc[-1] - closes.iloc[-20]) / closes.iloc[-20]

        # 动量加速度 = 短期动量 - 中期动量
        # 正值表示加速上涨，负值表示减速或加速下跌
        acceleration = mom_5d - mom_20d

        # 标准化到[-1, 1]
        normalized_signal = np.tanh(acceleration * 20)

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=normalized_signal,
            timestamp=datetime.now(),
            confidence=0.75,
            raw_data={
                'mom_5d': float(mom_5d),
                'mom_20d': float(mom_20d),
                'acceleration': float(acceleration)
            }
        )


class GapStrengthFactor(BaseFactor):
    """跳空缺口强度因子"""

    def __init__(self):
        super().__init__(
            name="gap_strength",
            category="momentum",
            description="跳空缺口强度检测，识别向上/向下跳空及其持续性"
        )
        self.dependencies = ["price"]
        self.lookback_days = 10

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算跳空缺口强度"""
        df = data['price'].tail(self.lookback_days)

        if len(df) < 3:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.5)

        gap_score = 0.0
        gap_count = 0

        # 检测最近的跳空缺口
        for i in range(len(df) - 1):
            prev_high = df['High'].iloc[i]
            prev_low = df['Low'].iloc[i]
            curr_open = df['Open'].iloc[i + 1]

            # 向上跳空
            if curr_open > prev_high:
                gap_size = (curr_open - prev_high) / prev_high
                # 检查是否回补
                is_filled = df['Low'].iloc[i + 1:].min() <= prev_high

                if not is_filled:
                    gap_score += gap_size * 10  # 未回补的缺口权重更高
                    gap_count += 1
                else:
                    gap_score += gap_size * 3

            # 向下跳空
            elif curr_open < prev_low:
                gap_size = (prev_low - curr_open) / prev_low
                is_filled = df['High'].iloc[i + 1:].max() >= prev_low

                if not is_filled:
                    gap_score -= gap_size * 10
                    gap_count += 1
                else:
                    gap_score -= gap_size * 3

        # 标准化
        normalized_signal = np.tanh(gap_score)

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=normalized_signal,
            timestamp=datetime.now(),
            confidence=0.70,
            raw_data={
                'gap_count': gap_count,
                'gap_score': float(gap_score)
            }
        )


class TrendPersistenceFactor(BaseFactor):
    """趋势延续性因子"""

    def __init__(self):
        super().__init__(
            name="trend_persistence",
            category="momentum",
            description="趋势延续性分析，评估当前趋势的持续强度"
        )
        self.dependencies = ["price"]
        self.lookback_days = 30

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算趋势延续性"""
        closes = data['price']['Close'].tail(self.lookback_days)

        if len(closes) < 20:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.5)

        # 1. 线性回归趋势
        x = np.arange(len(closes))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, closes)

        # 2. 趋势一致性（连续同向天数）
        returns = closes.pct_change().dropna()
        current_direction = 1 if returns.iloc[-1] > 0 else -1

        consecutive_days = 1
        for ret in reversed(returns.iloc[:-1].values):
            if (ret > 0 and current_direction > 0) or (ret < 0 and current_direction < 0):
                consecutive_days += 1
            else:
                break

        # 3. 价格相对趋势线的稳定性
        trend_line = slope * x + intercept
        deviations = np.abs(closes.values - trend_line)
        stability = 1.0 - (np.mean(deviations) / np.mean(closes))

        # 综合评分
        trend_strength = np.sign(slope) * (r_value ** 2) * stability
        persistence_boost = min(consecutive_days / 10, 1.0)  # 连续天数加成

        final_score = trend_strength * (1 + persistence_boost)
        normalized_signal = np.tanh(final_score * 3)

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=normalized_signal,
            timestamp=datetime.now(),
            confidence=0.78,
            raw_data={
                'slope': float(slope),
                'r_squared': float(r_value ** 2),
                'consecutive_days': consecutive_days,
                'stability': float(stability)
            }
        )


class HistoricalPercentileFactor(BaseFactor):
    """历史分位数因子 - 当前价格在历史中的相对位置"""

    def __init__(self):
        super().__init__(
            name="historical_percentile",
            category="mean_reversion",
            description="当前价格在历史分位数中的位置，用于均值回归策略"
        )
        self.dependencies = ["price"]
        self.lookback_days = 252  # 一年交易日

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算历史分位数"""
        closes = data['price']['Close'].tail(self.lookback_days)

        if len(closes) < 60:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.5)

        current_price = closes.iloc[-1]

        # 计算当前价格的百分位数
        percentile = stats.percentileofscore(closes, current_price) / 100

        # 转换为反转信号：
        # percentile接近1 -> 历史高位 -> 做空信号 -> 负值
        # percentile接近0 -> 历史低位 -> 做多信号 -> 正值
        reversion_signal = -2 * (percentile - 0.5)

        # 根据波动率调整信号强度
        volatility = closes.pct_change().std()
        adjusted_signal = reversion_signal * (1 + volatility * 5)

        normalized_signal = np.tanh(adjusted_signal)

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=normalized_signal,
            timestamp=datetime.now(),
            confidence=0.72,
            raw_data={
                'percentile': float(percentile),
                'volatility': float(volatility),
                'reversion_signal': float(reversion_signal)
            }
        )


class OvernightGapFactor(BaseFactor):
    """隔夜跳空因子 - 计算隔夜价格变化幅度"""

    def __init__(self):
        super().__init__(
            name="overnight_gap",
            category="momentum",
            description="隔夜跳空因子，衡量(前一日收盘价 - 当日开盘价)/当日开盘价"
        )
        self.dependencies = ["price"]
        self.lookback_days = 2  # 只需要2天数据

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算隔夜跳空"""
        df = data['price'].tail(self.lookback_days)

        if len(df) < 2:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.5)

        prev_close = df['Close'].iloc[-2]  # 前一日收盘价
        curr_open = df['Open'].iloc[-1]    # 当日开盘价

        # 隔夜跳空 = (前一日收盘价 - 当日开盘价) / 当日开盘价
        overnight_gap = (prev_close - curr_open) / curr_open

        # 标准化到[-1, 1]区间
        normalized_signal = np.tanh(overnight_gap * 20)

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=normalized_signal,
            timestamp=datetime.now(),
            confidence=0.75,
            raw_data={
                'prev_close': float(prev_close),
                'curr_open': float(curr_open),
                'overnight_gap_raw': float(overnight_gap)
            }
        )


def register_momentum_enhanced_factors():
    """注册所有增强动量因子"""
    from .factor_manager import get_factor_manager

    factor_manager = get_factor_manager()

    factor_manager.register_factor(AccelerationMomentumFactor())
    factor_manager.register_factor(GapStrengthFactor())
    factor_manager.register_factor(TrendPersistenceFactor())
    factor_manager.register_factor(HistoricalPercentileFactor())
    factor_manager.register_factor(OvernightGapFactor())  # 新增

    logger.info("✅ 增强动量因子注册完成 (5个因子)")
