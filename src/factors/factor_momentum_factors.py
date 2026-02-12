# -*- coding: utf-8 -*-
"""
因子动量因子模块
基于历史因子评分变化趋势，捕捉股票在多个时间窗口的因子改善或恶化趋势
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging
from datetime import datetime
from scipy import stats

from .factor_manager import BaseFactor, FactorValue

logger = logging.getLogger(__name__)


class BaseFactorMomentumFactor(BaseFactor):
    """因子动量基类（抽象）"""

    def __init__(self, name: str, time_window: int):
        """
        初始化因子动量因子

        Args:
            name: 因子名称
            time_window: 时间窗口（天数）
        """
        super().__init__(
            name=name,
            category="meta",  # 元因子（基于其他因子计算）
            description=f"基于过去{time_window}天因子评分变化趋势的动量因子"
        )
        self.time_window = time_window
        self.dependencies = []  # 不依赖价格数据，依赖历史因子
        self.lookback_days = time_window

    def calculate(self, data: Dict, symbol: str, **kwargs) -> FactorValue:
        """
        计算因子动量值

        Args:
            data: 数据字典（本因子不使用）
            symbol: 股票代码
            **kwargs: 额外参数，需要包含factor_manager

        Returns:
            FactorValue对象
        """
        # 1. 获取FactorManager和DataCollector
        factor_manager = kwargs.get('factor_manager')
        if not factor_manager:
            return self._create_zero_value(symbol, "缺少factor_manager")

        data_collector = getattr(factor_manager, 'data_collector', None)
        if not data_collector:
            return self._create_zero_value(symbol, "缺少data_collector")

        # 2. 获取启用的因子列表和权重
        enabled_factors = self._get_enabled_factors(factor_manager)
        if not enabled_factors:
            return self._create_zero_value(symbol, "没有启用的因子")

        # 3. 获取历史日期列表（最近N天）
        available_dates = sorted(data_collector.get_available_dates())
        if len(available_dates) < 2:
            return self._create_zero_value(symbol, f"历史数据不足（需要至少2天，当前{len(available_dates)}天）")

        # 4. 计算指定时间窗口的斜率
        slopes = self._calculate_window_slopes(
            symbol, self.time_window, enabled_factors,
            data_collector, available_dates
        )

        # 如果没有计算出任何斜率，返回0
        if not slopes:
            return self._create_zero_value(symbol, "无法计算任何因子的斜率")

        # 5. 加权聚合斜率
        weighted_slope = self._aggregate_slopes(slopes, factor_manager.factor_weights)

        # 6. 计算置信度
        confidence = self._calculate_confidence(available_dates, enabled_factors, self.time_window)

        # 7. 归一化到[-1, 1]范围
        normalized_score = np.tanh(weighted_slope * 10)  # 放大10倍后tanh

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=float(normalized_score),
            timestamp=datetime.now(),
            confidence=float(confidence),
            raw_data={
                'time_window': self.time_window,
                'individual_slopes': {k: float(v) for k, v in slopes.items()},
                'weighted_slope': float(weighted_slope),
                'enabled_factors_count': len(enabled_factors),
                'available_days': len(available_dates)
            },
            metadata={
                'calculation_method': 'linear_regression_weighted',
                'normalization': 'tanh'
            }
        )

    def _calculate_window_slopes(self, symbol: str, window: int,
                                  enabled_factors: Dict[str, float],
                                  data_collector,
                                  available_dates: List[str]) -> Dict[str, float]:
        """
        计算指定时间窗口内各因子的斜率

        Args:
            symbol: 股票代码
            window: 时间窗口
            enabled_factors: 启用的因子字典 {factor_name: weight}
            data_collector: 数据收集器
            available_dates: 可用日期列表

        Returns:
            {factor_name: slope} 斜率字典
        """
        slopes = {}

        # 选择最近window天的日期
        recent_dates = available_dates[-window:] if len(available_dates) >= window else available_dates

        # 如果日期少于2个，无法计算斜率
        if len(recent_dates) < 2:
            logger.debug(f"日期数量不足，无法计算斜率: {len(recent_dates)}")
            return slopes

        for factor_name, weight in enabled_factors.items():
            try:
                # 跳过因子动量因子本身（避免循环依赖）
                if 'factor_momentum' in factor_name:
                    continue

                # 获取该因子在这些日期的评分
                factor_values = []
                valid_dates = []

                for date in recent_dates:
                    date_values = data_collector.get_factor_values_by_date(factor_name, date)
                    if symbol in date_values and not pd.isna(date_values[symbol]):
                        factor_values.append(float(date_values[symbol]))
                        valid_dates.append(date)

                # 至少需要2个点才能计算斜率
                if len(factor_values) >= 2:
                    # 转换日期为数值（天数序号）
                    x = np.arange(len(factor_values), dtype=float)
                    y = np.array(factor_values, dtype=float)

                    # 线性回归计算斜率
                    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

                    # 只记录有效的斜率（非NaN，非无穷）
                    if np.isfinite(slope):
                        slopes[factor_name] = float(slope)
                        logger.debug(f"  {factor_name}: slope={slope:.6f}, r²={r_value**2:.4f}")

            except Exception as e:
                logger.debug(f"计算{factor_name}斜率失败: {e}")
                continue

        logger.debug(f"计算了 {len(slopes)}/{len(enabled_factors)} 个因子的斜率")
        return slopes

    def _aggregate_slopes(self, slopes: Dict[str, float],
                         factor_weights: Dict[str, float]) -> float:
        """
        使用因子权重聚合斜率

        Args:
            slopes: 斜率字典
            factor_weights: 因子权重字典

        Returns:
            加权平均斜率
        """
        if not slopes:
            return 0.0

        weighted_sum = 0.0
        weight_sum = 0.0

        for factor_name, slope in slopes.items():
            weight = factor_weights.get(factor_name, 1.0)
            weighted_sum += slope * weight
            weight_sum += weight

        return weighted_sum / weight_sum if weight_sum > 0 else 0.0

    def _calculate_confidence(self, available_dates: List[str],
                             enabled_factors: Dict[str, float],
                             required_days: int) -> float:
        """
        计算置信度

        Args:
            available_dates: 可用日期列表
            enabled_factors: 启用的因子字典
            required_days: 所需天数

        Returns:
            置信度 [0, 1]
        """
        # 基于历史数据充足性
        data_sufficiency = min(1.0, len(available_dates) / required_days)

        # 基于启用因子数量（10个因子为满分）
        factor_coverage = min(1.0, len(enabled_factors) / 10)

        # 综合置信度
        confidence = (data_sufficiency + factor_coverage) / 2

        return float(confidence)

    def _get_enabled_factors(self, factor_manager) -> Dict[str, float]:
        """
        获取启用的因子列表及其权重

        Args:
            factor_manager: 因子管理器

        Returns:
            {factor_name: weight} 字典
        """
        enabled = {}

        factor_weights = getattr(factor_manager, 'factor_weights', {})
        disabled_factors = getattr(factor_manager, 'disabled_factors', set())

        for factor_name, weight in factor_weights.items():
            if weight > 0 and factor_name not in disabled_factors:
                enabled[factor_name] = weight

        return enabled

    def _create_zero_value(self, symbol: str, reason: str) -> FactorValue:
        """
        创建零值返回（数据不足时）

        Args:
            symbol: 股票代码
            reason: 原因说明

        Returns:
            值为0的FactorValue对象
        """
        logger.debug(f"因子动量({self.name})计算返回0: {reason}")
        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=0.0,
            timestamp=datetime.now(),
            confidence=0.0,
            raw_data={'reason': reason}
        )


class FactorMomentum3dFactor(BaseFactorMomentumFactor):
    """3天因子动量（短期）"""

    def __init__(self):
        super().__init__(
            name="factor_momentum_3d",
            time_window=3
        )


class FactorMomentum5dFactor(BaseFactorMomentumFactor):
    """5天因子动量（短中期）"""

    def __init__(self):
        super().__init__(
            name="factor_momentum_5d",
            time_window=5
        )


class FactorMomentum15dFactor(BaseFactorMomentumFactor):
    """15天因子动量（中期）"""

    def __init__(self):
        super().__init__(
            name="factor_momentum_15d",
            time_window=15
        )


class FactorMomentum20dFactor(BaseFactorMomentumFactor):
    """20天因子动量（中长期）"""

    def __init__(self):
        super().__init__(
            name="factor_momentum_20d",
            time_window=20
        )


# 便捷注册函数
def register_factor_momentum_factors():
    """注册所有因子动量因子"""
    from .factor_manager import get_factor_manager

    manager = get_factor_manager()

    # 注册4个时间窗口因子
    factors = [
        FactorMomentum3dFactor(),
        FactorMomentum5dFactor(),
        FactorMomentum15dFactor(),
        FactorMomentum20dFactor()
    ]

    for factor in factors:
        manager.register_factor(factor)
        logger.info(f"[OK] Registered factor momentum: {factor.name} ({factor.time_window} days)")

    print(f"[OK] Factor momentum factors registered: 4 time windows (3d, 5d, 15d, 20d)")
