# -*- coding: utf-8 -*-
"""
Qlib Momentum Factors
拆分自Alpha158的momentum类因子（共23个）
每个因子独立参与IC评估和权重优化
"""

from .qlib_base_factor import QlibBaseFactor


class QlibMomentumCloseRet1dFactor(QlibBaseFactor):
    """
    1日收盘价动量

    Qlib表达式: Ref($close, 1)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_close_ret_1d",
            qlib_expression="Ref($close, 1)/$close - 1",
            description="1日收盘价动量"
        )


class QlibMomentumCloseRet5dFactor(QlibBaseFactor):
    """
    5日收盘价动量

    Qlib表达式: Ref($close, 5)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_close_ret_5d",
            qlib_expression="Ref($close, 5)/$close - 1",
            description="5日收盘价动量"
        )


class QlibMomentumCloseRet10dFactor(QlibBaseFactor):
    """
    10日收盘价动量

    Qlib表达式: Ref($close, 10)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_close_ret_10d",
            qlib_expression="Ref($close, 10)/$close - 1",
            description="10日收盘价动量"
        )


class QlibMomentumCloseRet20dFactor(QlibBaseFactor):
    """
    20日收盘价动量

    Qlib表达式: Ref($close, 20)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_close_ret_20d",
            qlib_expression="Ref($close, 20)/$close - 1",
            description="20日收盘价动量"
        )


class QlibMomentumCloseRet30dFactor(QlibBaseFactor):
    """
    30日收盘价动量

    Qlib表达式: Ref($close, 30)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_close_ret_30d",
            qlib_expression="Ref($close, 30)/$close - 1",
            description="30日收盘价动量"
        )


class QlibMomentumCloseRet60dFactor(QlibBaseFactor):
    """
    60日收盘价动量

    Qlib表达式: Ref($close, 60)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_close_ret_60d",
            qlib_expression="Ref($close, 60)/$close - 1",
            description="60日收盘价动量"
        )


class QlibMomentumOpenRet1dFactor(QlibBaseFactor):
    """
    1日开盘价动量

    Qlib表达式: Ref($open, 1)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_open_ret_1d",
            qlib_expression="Ref($open, 1)/$close - 1",
            description="1日开盘价动量"
        )


class QlibMomentumOpenRet5dFactor(QlibBaseFactor):
    """
    5日开盘价动量

    Qlib表达式: Ref($open, 5)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_open_ret_5d",
            qlib_expression="Ref($open, 5)/$close - 1",
            description="5日开盘价动量"
        )


class QlibMomentumOpenRet10dFactor(QlibBaseFactor):
    """
    10日开盘价动量

    Qlib表达式: Ref($open, 10)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_open_ret_10d",
            qlib_expression="Ref($open, 10)/$close - 1",
            description="10日开盘价动量"
        )


class QlibMomentumOpenRet20dFactor(QlibBaseFactor):
    """
    20日开盘价动量

    Qlib表达式: Ref($open, 20)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_open_ret_20d",
            qlib_expression="Ref($open, 20)/$close - 1",
            description="20日开盘价动量"
        )


class QlibMomentumOpenRet30dFactor(QlibBaseFactor):
    """
    30日开盘价动量

    Qlib表达式: Ref($open, 30)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_open_ret_30d",
            qlib_expression="Ref($open, 30)/$close - 1",
            description="30日开盘价动量"
        )


class QlibMomentumOpenRet60dFactor(QlibBaseFactor):
    """
    60日开盘价动量

    Qlib表达式: Ref($open, 60)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_open_ret_60d",
            qlib_expression="Ref($open, 60)/$close - 1",
            description="60日开盘价动量"
        )


class QlibMomentumHighRet5dFactor(QlibBaseFactor):
    """
    5日最高价动量

    Qlib表达式: Ref($high, 5)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_high_ret_5d",
            qlib_expression="Ref($high, 5)/$close - 1",
            description="5日最高价动量"
        )


class QlibMomentumHighRet10dFactor(QlibBaseFactor):
    """
    10日最高价动量

    Qlib表达式: Ref($high, 10)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_high_ret_10d",
            qlib_expression="Ref($high, 10)/$close - 1",
            description="10日最高价动量"
        )


class QlibMomentumHighRet20dFactor(QlibBaseFactor):
    """
    20日最高价动量

    Qlib表达式: Ref($high, 20)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_high_ret_20d",
            qlib_expression="Ref($high, 20)/$close - 1",
            description="20日最高价动量"
        )


class QlibMomentumHighRet30dFactor(QlibBaseFactor):
    """
    30日最高价动量

    Qlib表达式: Ref($high, 30)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_high_ret_30d",
            qlib_expression="Ref($high, 30)/$close - 1",
            description="30日最高价动量"
        )


class QlibMomentumLowRet5dFactor(QlibBaseFactor):
    """
    5日最低价动量

    Qlib表达式: Ref($low, 5)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_low_ret_5d",
            qlib_expression="Ref($low, 5)/$close - 1",
            description="5日最低价动量"
        )


class QlibMomentumLowRet10dFactor(QlibBaseFactor):
    """
    10日最低价动量

    Qlib表达式: Ref($low, 10)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_low_ret_10d",
            qlib_expression="Ref($low, 10)/$close - 1",
            description="10日最低价动量"
        )


class QlibMomentumLowRet20dFactor(QlibBaseFactor):
    """
    20日最低价动量

    Qlib表达式: Ref($low, 20)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_low_ret_20d",
            qlib_expression="Ref($low, 20)/$close - 1",
            description="20日最低价动量"
        )


class QlibMomentumLowRet30dFactor(QlibBaseFactor):
    """
    30日最低价动量

    Qlib表达式: Ref($low, 30)/$close - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_low_ret_30d",
            qlib_expression="Ref($low, 30)/$close - 1",
            description="30日最低价动量"
        )


class QlibMomentumCumRet5dFactor(QlibBaseFactor):
    """
    5日累计收益率

    Qlib表达式: $close / Ref($close, 5) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_cum_ret_5d",
            qlib_expression="$close / Ref($close, 5) - 1",
            description="5日累计收益率"
        )


class QlibMomentumCumRet10dFactor(QlibBaseFactor):
    """
    10日累计收益率

    Qlib表达式: $close / Ref($close, 10) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_cum_ret_10d",
            qlib_expression="$close / Ref($close, 10) - 1",
            description="10日累计收益率"
        )


class QlibMomentumCumRet20dFactor(QlibBaseFactor):
    """
    20日累计收益率

    Qlib表达式: $close / Ref($close, 20) - 1
    """

    def __init__(self):
        super().__init__(
            name="qlib_momentum_cum_ret_20d",
            qlib_expression="$close / Ref($close, 20) - 1",
            description="20日累计收益率"
        )


def get_momentum_factors():
    """返回所有23个momentum因子实例"""
    return [
        QlibMomentumCloseRet1dFactor(),
        QlibMomentumCloseRet5dFactor(),
        QlibMomentumCloseRet10dFactor(),
        QlibMomentumCloseRet20dFactor(),
        QlibMomentumCloseRet30dFactor(),
        QlibMomentumCloseRet60dFactor(),
        QlibMomentumOpenRet1dFactor(),
        QlibMomentumOpenRet5dFactor(),
        QlibMomentumOpenRet10dFactor(),
        QlibMomentumOpenRet20dFactor(),
        QlibMomentumOpenRet30dFactor(),
        QlibMomentumOpenRet60dFactor(),
        QlibMomentumHighRet5dFactor(),
        QlibMomentumHighRet10dFactor(),
        QlibMomentumHighRet20dFactor(),
        QlibMomentumHighRet30dFactor(),
        QlibMomentumLowRet5dFactor(),
        QlibMomentumLowRet10dFactor(),
        QlibMomentumLowRet20dFactor(),
        QlibMomentumLowRet30dFactor(),
        QlibMomentumCumRet5dFactor(),
        QlibMomentumCumRet10dFactor(),
        QlibMomentumCumRet20dFactor(),
    ]
