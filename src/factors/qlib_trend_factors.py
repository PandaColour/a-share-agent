# -*- coding: utf-8 -*-
"""
Qlib Trend Factors
拆分自Alpha158的trend类因子（共18个）
每个因子独立参与IC评估和权重优化
"""

from .qlib_base_factor import QlibBaseFactor


class QlibTrendMaRatio510Factor(QlibBaseFactor):
    """
    5日/10日均线比率

    Qlib表达式: Mean($close, 5) / Mean($close, 10) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_ratio_5_10",
            qlib_expression="Mean($close, 5) / Mean($close, 10) - 1",
            description="5日/10日均线比率"
        )


class QlibTrendMaDiff510Factor(QlibBaseFactor):
    """
    5日-10日均线差

    Qlib表达式: (Mean($close, 5) - Mean($close, 10)) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_diff_5_10",
            qlib_expression="(Mean($close, 5) - Mean($close, 10)) / $close",
            description="5日-10日均线差"
        )


class QlibTrendMaRatio520Factor(QlibBaseFactor):
    """
    5日/20日均线比率

    Qlib表达式: Mean($close, 5) / Mean($close, 20) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_ratio_5_20",
            qlib_expression="Mean($close, 5) / Mean($close, 20) - 1",
            description="5日/20日均线比率"
        )


class QlibTrendMaDiff520Factor(QlibBaseFactor):
    """
    5日-20日均线差

    Qlib表达式: (Mean($close, 5) - Mean($close, 20)) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_diff_5_20",
            qlib_expression="(Mean($close, 5) - Mean($close, 20)) / $close",
            description="5日-20日均线差"
        )


class QlibTrendMaRatio1020Factor(QlibBaseFactor):
    """
    10日/20日均线比率

    Qlib表达式: Mean($close, 10) / Mean($close, 20) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_ratio_10_20",
            qlib_expression="Mean($close, 10) / Mean($close, 20) - 1",
            description="10日/20日均线比率"
        )


class QlibTrendMaDiff1020Factor(QlibBaseFactor):
    """
    10日-20日均线差

    Qlib表达式: (Mean($close, 10) - Mean($close, 20)) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_diff_10_20",
            qlib_expression="(Mean($close, 10) - Mean($close, 20)) / $close",
            description="10日-20日均线差"
        )


class QlibTrendMaRatio1030Factor(QlibBaseFactor):
    """
    10日/30日均线比率

    Qlib表达式: Mean($close, 10) / Mean($close, 30) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_ratio_10_30",
            qlib_expression="Mean($close, 10) / Mean($close, 30) - 1",
            description="10日/30日均线比率"
        )


class QlibTrendMaDiff1030Factor(QlibBaseFactor):
    """
    10日-30日均线差

    Qlib表达式: (Mean($close, 10) - Mean($close, 30)) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_diff_10_30",
            qlib_expression="(Mean($close, 10) - Mean($close, 30)) / $close",
            description="10日-30日均线差"
        )


class QlibTrendMaRatio2060Factor(QlibBaseFactor):
    """
    20日/60日均线比率

    Qlib表达式: Mean($close, 20) / Mean($close, 60) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_ratio_20_60",
            qlib_expression="Mean($close, 20) / Mean($close, 60) - 1",
            description="20日/60日均线比率"
        )


class QlibTrendMaDiff2060Factor(QlibBaseFactor):
    """
    20日-60日均线差

    Qlib表达式: (Mean($close, 20) - Mean($close, 60)) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_diff_20_60",
            qlib_expression="(Mean($close, 20) - Mean($close, 60)) / $close",
            description="20日-60日均线差"
        )


class QlibTrendMaSlope5dFactor(QlibBaseFactor):
    """
    5日均线斜率

    Qlib表达式: (Mean($close, 5) - Ref(Mean($close, 5), 5)) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_slope_5d",
            qlib_expression="(Mean($close, 5) - Ref(Mean($close, 5), 5)) / $close",
            description="5日均线斜率"
        )


class QlibTrendMaSlope10dFactor(QlibBaseFactor):
    """
    10日均线斜率

    Qlib表达式: (Mean($close, 10) - Ref(Mean($close, 10), 10)) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_slope_10d",
            qlib_expression="(Mean($close, 10) - Ref(Mean($close, 10), 10)) / $close",
            description="10日均线斜率"
        )


class QlibTrendMaSlope20dFactor(QlibBaseFactor):
    """
    20日均线斜率

    Qlib表达式: (Mean($close, 20) - Ref(Mean($close, 20), 20)) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_ma_slope_20d",
            qlib_expression="(Mean($close, 20) - Ref(Mean($close, 20), 20)) / $close",
            description="20日均线斜率"
        )


class QlibTrendPriceDev5dFactor(QlibBaseFactor):
    """
    价格偏离5日均线

    Qlib表达式: $close / Mean($close, 5) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_price_dev_5d",
            qlib_expression="$close / Mean($close, 5) - 1",
            description="价格偏离5日均线"
        )


class QlibTrendPriceDev10dFactor(QlibBaseFactor):
    """
    价格偏离10日均线

    Qlib表达式: $close / Mean($close, 10) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_price_dev_10d",
            qlib_expression="$close / Mean($close, 10) - 1",
            description="价格偏离10日均线"
        )


class QlibTrendPriceDev20dFactor(QlibBaseFactor):
    """
    价格偏离20日均线

    Qlib表达式: $close / Mean($close, 20) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_price_dev_20d",
            qlib_expression="$close / Mean($close, 20) - 1",
            description="价格偏离20日均线"
        )


class QlibTrendPriceDev30dFactor(QlibBaseFactor):
    """
    价格偏离30日均线

    Qlib表达式: $close / Mean($close, 30) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_price_dev_30d",
            qlib_expression="$close / Mean($close, 30) - 1",
            description="价格偏离30日均线"
        )


class QlibTrendPriceDev60dFactor(QlibBaseFactor):
    """
    价格偏离60日均线

    Qlib表达式: $close / Mean($close, 60) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_trend_price_dev_60d",
            qlib_expression="$close / Mean($close, 60) - 1",
            description="价格偏离60日均线"
        )


def get_trend_factors():
    """返回所有18个trend因子实例"""
    return [
        QlibTrendMaRatio510Factor(),
        QlibTrendMaDiff510Factor(),
        QlibTrendMaRatio520Factor(),
        QlibTrendMaDiff520Factor(),
        QlibTrendMaRatio1020Factor(),
        QlibTrendMaDiff1020Factor(),
        QlibTrendMaRatio1030Factor(),
        QlibTrendMaDiff1030Factor(),
        QlibTrendMaRatio2060Factor(),
        QlibTrendMaDiff2060Factor(),
        QlibTrendMaSlope5dFactor(),
        QlibTrendMaSlope10dFactor(),
        QlibTrendMaSlope20dFactor(),
        QlibTrendPriceDev5dFactor(),
        QlibTrendPriceDev10dFactor(),
        QlibTrendPriceDev20dFactor(),
        QlibTrendPriceDev30dFactor(),
        QlibTrendPriceDev60dFactor(),
    ]
