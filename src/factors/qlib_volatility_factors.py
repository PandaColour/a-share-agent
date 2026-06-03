# -*- coding: utf-8 -*-
"""
Qlib Volatility Factors
拆分自Alpha158的volatility类因子（共20个）
每个因子独立参与IC评估和权重优化
"""

from .qlib_base_factor import QlibBaseFactor


class QlibVolatilityStd5dFactor(QlibBaseFactor):
    """
    5日收盘价标准差

    Qlib表达式: Std($close, 5)/$close
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_std_5d",
            qlib_expression="Std($close, 5)/$close",
            description="5日收盘价标准差"
        )


class QlibVolatilityStd10dFactor(QlibBaseFactor):
    """
    10日收盘价标准差

    Qlib表达式: Std($close, 10)/$close
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_std_10d",
            qlib_expression="Std($close, 10)/$close",
            description="10日收盘价标准差"
        )


class QlibVolatilityStd20dFactor(QlibBaseFactor):
    """
    20日收盘价标准差

    Qlib表达式: Std($close, 20)/$close
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_std_20d",
            qlib_expression="Std($close, 20)/$close",
            description="20日收盘价标准差"
        )


class QlibVolatilityStd30dFactor(QlibBaseFactor):
    """
    30日收盘价标准差

    Qlib表达式: Std($close, 30)/$close
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_std_30d",
            qlib_expression="Std($close, 30)/$close",
            description="30日收盘价标准差"
        )


class QlibVolatilityStd60dFactor(QlibBaseFactor):
    """
    60日收盘价标准差

    Qlib表达式: Std($close, 60)/$close
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_std_60d",
            qlib_expression="Std($close, 60)/$close",
            description="60日收盘价标准差"
        )


class QlibVolatilityRetvol5dFactor(QlibBaseFactor):
    """
    5日收益波动率

    Qlib表达式: Std($close / Ref($close, 1) - 1, 5)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_retvol_5d",
            qlib_expression="Std($close / Ref($close, 1) - 1, 5)",
            description="5日收益波动率"
        )


class QlibVolatilityRetvol10dFactor(QlibBaseFactor):
    """
    10日收益波动率

    Qlib表达式: Std($close / Ref($close, 1) - 1, 10)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_retvol_10d",
            qlib_expression="Std($close / Ref($close, 1) - 1, 10)",
            description="10日收益波动率"
        )


class QlibVolatilityRetvol20dFactor(QlibBaseFactor):
    """
    20日收益波动率

    Qlib表达式: Std($close / Ref($close, 1) - 1, 20)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_retvol_20d",
            qlib_expression="Std($close / Ref($close, 1) - 1, 20)",
            description="20日收益波动率"
        )


class QlibVolatilityRetvol30dFactor(QlibBaseFactor):
    """
    30日收益波动率

    Qlib表达式: Std($close / Ref($close, 1) - 1, 30)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_retvol_30d",
            qlib_expression="Std($close / Ref($close, 1) - 1, 30)",
            description="30日收益波动率"
        )


class QlibVolatilityRetvol60dFactor(QlibBaseFactor):
    """
    60日收益波动率

    Qlib表达式: Std($close / Ref($close, 1) - 1, 60)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_retvol_60d",
            qlib_expression="Std($close / Ref($close, 1) - 1, 60)",
            description="60日收益波动率"
        )


class QlibVolatilityRangeDailyFactor(QlibBaseFactor):
    """
    日内振幅

    Qlib表达式: ($high - $low)/$close
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_range_daily",
            qlib_expression="($high - $low)/$close",
            description="日内振幅"
        )


class QlibVolatilityRangeAvg5dFactor(QlibBaseFactor):
    """
    5日平均振幅

    Qlib表达式: Mean(($high - $low)/$close, 5)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_range_avg_5d",
            qlib_expression="Mean(($high - $low)/$close, 5)",
            description="5日平均振幅"
        )


class QlibVolatilityRangeAvg10dFactor(QlibBaseFactor):
    """
    10日平均振幅

    Qlib表达式: Mean(($high - $low)/$close, 10)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_range_avg_10d",
            qlib_expression="Mean(($high - $low)/$close, 10)",
            description="10日平均振幅"
        )


class QlibVolatilityRangeAvg20dFactor(QlibBaseFactor):
    """
    20日平均振幅

    Qlib表达式: Mean(($high - $low)/$close, 20)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_range_avg_20d",
            qlib_expression="Mean(($high - $low)/$close, 20)",
            description="20日平均振幅"
        )


class QlibVolatilityRangeAvg30dFactor(QlibBaseFactor):
    """
    30日平均振幅

    Qlib表达式: Mean(($high - $low)/$close, 30)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_range_avg_30d",
            qlib_expression="Mean(($high - $low)/$close, 30)",
            description="30日平均振幅"
        )


class QlibVolatilityHlratioStd5dFactor(QlibBaseFactor):
    """
    5日高低价比波动

    Qlib表达式: Std($high/$low, 5)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_hlratio_std_5d",
            qlib_expression="Std($high/$low, 5)",
            description="5日高低价比波动"
        )


class QlibVolatilityHlratioStd10dFactor(QlibBaseFactor):
    """
    10日高低价比波动

    Qlib表达式: Std($high/$low, 10)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_hlratio_std_10d",
            qlib_expression="Std($high/$low, 10)",
            description="10日高低价比波动"
        )


class QlibVolatilityRangeStd20dFactor(QlibBaseFactor):
    """
    20日振幅标准差

    Qlib表达式: Std(($high - $low)/$close, 20)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_range_std_20d",
            qlib_expression="Std(($high - $low)/$close, 20)",
            description="20日振幅标准差"
        )


class QlibVolatilityVolatilityRatio20dFactor(QlibBaseFactor):
    """
    20日波动率比率

    Qlib表达式: Std($close, 20) / Mean($close, 20)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_volatility_ratio_20d",
            qlib_expression="Std($close, 20) / Mean($close, 20)",
            description="20日波动率比率"
        )


class QlibVolatilityAtrRatio14dFactor(QlibBaseFactor):
    """
    14日ATR比率

    Qlib表达式: Mean(Max(Max($high - $low, Abs($high - Ref($close, 1))), Abs($low - Ref($close, 1))), 14) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_volatility_atr_ratio_14d",
            qlib_expression="Mean(Max(Max($high - $low, Abs($high - Ref($close, 1))), Abs($low - Ref($close, 1))), 14) / $close",
            description="14日ATR比率"
        )


def get_volatility_factors():
    """返回所有20个volatility因子实例"""
    return [
        QlibVolatilityStd5dFactor(),
        QlibVolatilityStd10dFactor(),
        QlibVolatilityStd20dFactor(),
        QlibVolatilityStd30dFactor(),
        QlibVolatilityStd60dFactor(),
        QlibVolatilityRetvol5dFactor(),
        QlibVolatilityRetvol10dFactor(),
        QlibVolatilityRetvol20dFactor(),
        QlibVolatilityRetvol30dFactor(),
        QlibVolatilityRetvol60dFactor(),
        QlibVolatilityRangeDailyFactor(),
        QlibVolatilityRangeAvg5dFactor(),
        QlibVolatilityRangeAvg10dFactor(),
        QlibVolatilityRangeAvg20dFactor(),
        QlibVolatilityRangeAvg30dFactor(),
        QlibVolatilityHlratioStd5dFactor(),
        QlibVolatilityHlratioStd10dFactor(),
        QlibVolatilityRangeStd20dFactor(),
        QlibVolatilityVolatilityRatio20dFactor(),
        QlibVolatilityAtrRatio14dFactor(),
    ]
