# -*- coding: utf-8 -*-
"""
Qlib Technical Factors
拆分自Alpha158的technical类因子（共19个）
每个因子独立参与IC评估和权重优化
"""

from .qlib_base_factor import QlibBaseFactor


class QlibTechnicalRsi6Factor(QlibBaseFactor):
    """
    6日RSI

    Qlib表达式: Mean(Max($close - Ref($close, 1), 0), 6) / (Mean(Abs($close - Ref($close, 1)), 6) + 1e-12)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_rsi_6",
            qlib_expression="Mean(Max($close - Ref($close, 1), 0), 6) / (Mean(Abs($close - Ref($close, 1)), 6) + 1e-12)",
            description="6日RSI"
        )


class QlibTechnicalRsi12Factor(QlibBaseFactor):
    """
    12日RSI

    Qlib表达式: Mean(Max($close - Ref($close, 1), 0), 12) / (Mean(Abs($close - Ref($close, 1)), 12) + 1e-12)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_rsi_12",
            qlib_expression="Mean(Max($close - Ref($close, 1), 0), 12) / (Mean(Abs($close - Ref($close, 1)), 12) + 1e-12)",
            description="12日RSI"
        )


class QlibTechnicalRsi24Factor(QlibBaseFactor):
    """
    24日RSI

    Qlib表达式: Mean(Max($close - Ref($close, 1), 0), 24) / (Mean(Abs($close - Ref($close, 1)), 24) + 1e-12)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_rsi_24",
            qlib_expression="Mean(Max($close - Ref($close, 1), 0), 24) / (Mean(Abs($close - Ref($close, 1)), 24) + 1e-12)",
            description="24日RSI"
        )


class QlibTechnicalEmaShort12Factor(QlibBaseFactor):
    """
    12日短期EMA

    Qlib表达式: EMA($close, 12) / $close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_ema_short_12",
            qlib_expression="EMA($close, 12) / $close - 1",
            description="12日短期EMA"
        )


class QlibTechnicalEmaLong26Factor(QlibBaseFactor):
    """
    26日长期EMA

    Qlib表达式: EMA($close, 26) / $close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_ema_long_26",
            qlib_expression="EMA($close, 26) / $close - 1",
            description="26日长期EMA"
        )


class QlibTechnicalMacdDifFactor(QlibBaseFactor):
    """
    MACD DIF

    Qlib表达式: (EMA($close, 12) - EMA($close, 26)) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_macd_dif",
            qlib_expression="(EMA($close, 12) - EMA($close, 26)) / $close",
            description="MACD DIF"
        )


class QlibTechnicalMacdDeaFactor(QlibBaseFactor):
    """
    MACD DEA

    Qlib表达式: EMA(EMA($close, 12) - EMA($close, 26), 9) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_macd_dea",
            qlib_expression="EMA(EMA($close, 12) - EMA($close, 26), 9) / $close",
            description="MACD DEA"
        )


class QlibTechnicalBollPos10dFactor(QlibBaseFactor):
    """
    10日布林带位置

    Qlib表达式: ($close - Mean($close, 10)) / Std($close, 10)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_boll_pos_10d",
            qlib_expression="($close - Mean($close, 10)) / Std($close, 10)",
            description="10日布林带位置"
        )


class QlibTechnicalBollPos20dFactor(QlibBaseFactor):
    """
    20日布林带位置

    Qlib表达式: ($close - Mean($close, 20)) / Std($close, 20)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_boll_pos_20d",
            qlib_expression="($close - Mean($close, 20)) / Std($close, 20)",
            description="20日布林带位置"
        )


class QlibTechnicalBollWidth10dFactor(QlibBaseFactor):
    """
    10日布林带宽度

    Qlib表达式: Std($close, 10) / Mean($close, 10)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_boll_width_10d",
            qlib_expression="Std($close, 10) / Mean($close, 10)",
            description="10日布林带宽度"
        )


class QlibTechnicalBollWidth20dFactor(QlibBaseFactor):
    """
    20日布林带宽度

    Qlib表达式: Std($close, 20) / Mean($close, 20)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_boll_width_20d",
            qlib_expression="Std($close, 20) / Mean($close, 20)",
            description="20日布林带宽度"
        )


class QlibTechnicalWilliams6Factor(QlibBaseFactor):
    """
    6日威廉指标

    Qlib表达式: ($close - Min($low, 6)) / (Max($high, 6) - Min($low, 6) + 1e-12)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_williams_6",
            qlib_expression="($close - Min($low, 6)) / (Max($high, 6) - Min($low, 6) + 1e-12)",
            description="6日威廉指标"
        )


class QlibTechnicalWilliams10Factor(QlibBaseFactor):
    """
    10日威廉指标

    Qlib表达式: ($close - Min($low, 10)) / (Max($high, 10) - Min($low, 10) + 1e-12)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_williams_10",
            qlib_expression="($close - Min($low, 10)) / (Max($high, 10) - Min($low, 10) + 1e-12)",
            description="10日威廉指标"
        )


class QlibTechnicalKdj9Factor(QlibBaseFactor):
    """
    9日KDJ

    Qlib表达式: ($close - Min($low, 9)) / (Max($high, 9) - Min($low, 9) + 1e-12)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_kdj_9",
            qlib_expression="($close - Min($low, 9)) / (Max($high, 9) - Min($low, 9) + 1e-12)",
            description="9日KDJ"
        )


class QlibTechnicalKdj14Factor(QlibBaseFactor):
    """
    14日KDJ

    Qlib表达式: ($close - Min($low, 14)) / (Max($high, 14) - Min($low, 14) + 1e-12)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_kdj_14",
            qlib_expression="($close - Min($low, 14)) / (Max($high, 14) - Min($low, 14) + 1e-12)",
            description="14日KDJ"
        )


class QlibTechnicalAtr14Factor(QlibBaseFactor):
    """
    14日ATR

    Qlib表达式: Mean(Max(Max($high - $low, Abs($high - Ref($close, 1))), Abs($low - Ref($close, 1))), 14) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_atr_14",
            qlib_expression="Mean(Max(Max($high - $low, Abs($high - Ref($close, 1))), Abs($low - Ref($close, 1))), 14) / $close",
            description="14日ATR"
        )


class QlibTechnicalAtr20Factor(QlibBaseFactor):
    """
    20日ATR

    Qlib表达式: Mean(Max(Max($high - $low, Abs($high - Ref($close, 1))), Abs($low - Ref($close, 1))), 20) / $close
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_atr_20",
            qlib_expression="Mean(Max(Max($high - $low, Abs($high - Ref($close, 1))), Abs($low - Ref($close, 1))), 20) / $close",
            description="20日ATR"
        )


class QlibTechnicalCci14Factor(QlibBaseFactor):
    """
    14日CCI

    Qlib表达式: (($high + $low + $close) / 3 - Mean(($high + $low + $close) / 3, 14)) / (Std(($high + $low + $close) / 3, 14) * 0.015 + 1e-12)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_cci_14",
            qlib_expression="(($high + $low + $close) / 3 - Mean(($high + $low + $close) / 3, 14)) / (Std(($high + $low + $close) / 3, 14) * 0.015 + 1e-12)",
            description="14日CCI"
        )


class QlibTechnicalCci20Factor(QlibBaseFactor):
    """
    20日CCI

    Qlib表达式: (($high + $low + $close) / 3 - Mean(($high + $low + $close) / 3, 20)) / (Std(($high + $low + $close) / 3, 20) * 0.015 + 1e-12)
    """

    def __init__(self):
        super().__init__(
            name="qlib_technical_cci_20",
            qlib_expression="(($high + $low + $close) / 3 - Mean(($high + $low + $close) / 3, 20)) / (Std(($high + $low + $close) / 3, 20) * 0.015 + 1e-12)",
            description="20日CCI"
        )


def get_technical_factors():
    """返回所有19个technical因子实例"""
    return [
        QlibTechnicalRsi6Factor(),
        QlibTechnicalRsi12Factor(),
        QlibTechnicalRsi24Factor(),
        QlibTechnicalEmaShort12Factor(),
        QlibTechnicalEmaLong26Factor(),
        QlibTechnicalMacdDifFactor(),
        QlibTechnicalMacdDeaFactor(),
        QlibTechnicalBollPos10dFactor(),
        QlibTechnicalBollPos20dFactor(),
        QlibTechnicalBollWidth10dFactor(),
        QlibTechnicalBollWidth20dFactor(),
        QlibTechnicalWilliams6Factor(),
        QlibTechnicalWilliams10Factor(),
        QlibTechnicalKdj9Factor(),
        QlibTechnicalKdj14Factor(),
        QlibTechnicalAtr14Factor(),
        QlibTechnicalAtr20Factor(),
        QlibTechnicalCci14Factor(),
        QlibTechnicalCci20Factor(),
    ]
