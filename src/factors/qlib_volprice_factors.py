# -*- coding: utf-8 -*-
"""
Qlib Volprice Factors
拆分自Alpha158的volprice类因子（共17个）
每个因子独立参与IC评估和权重优化
"""

from .qlib_base_factor import QlibBaseFactor


class QlibVolpriceVolratio5dFactor(QlibBaseFactor):
    """
    5日成交量比率

    Qlib表达式: $volume / Mean($volume, 5)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_volratio_5d",
            qlib_expression="$volume / Mean($volume, 5)",
            description="5日成交量比率"
        )


class QlibVolpriceVolratio10dFactor(QlibBaseFactor):
    """
    10日成交量比率

    Qlib表达式: $volume / Mean($volume, 10)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_volratio_10d",
            qlib_expression="$volume / Mean($volume, 10)",
            description="10日成交量比率"
        )


class QlibVolpriceVolratio20dFactor(QlibBaseFactor):
    """
    20日成交量比率

    Qlib表达式: $volume / Mean($volume, 20)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_volratio_20d",
            qlib_expression="$volume / Mean($volume, 20)",
            description="20日成交量比率"
        )


class QlibVolpriceVolratio30dFactor(QlibBaseFactor):
    """
    30日成交量比率

    Qlib表达式: $volume / Mean($volume, 30)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_volratio_30d",
            qlib_expression="$volume / Mean($volume, 30)",
            description="30日成交量比率"
        )


class QlibVolpriceVolcv5dFactor(QlibBaseFactor):
    """
    5日成交量变异系数

    Qlib表达式: Std($volume, 5) / Mean($volume, 5)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_volcv_5d",
            qlib_expression="Std($volume, 5) / Mean($volume, 5)",
            description="5日成交量变异系数"
        )


class QlibVolpriceVolcv10dFactor(QlibBaseFactor):
    """
    10日成交量变异系数

    Qlib表达式: Std($volume, 10) / Mean($volume, 10)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_volcv_10d",
            qlib_expression="Std($volume, 10) / Mean($volume, 10)",
            description="10日成交量变异系数"
        )


class QlibVolpriceVolcv20dFactor(QlibBaseFactor):
    """
    20日成交量变异系数

    Qlib表达式: Std($volume, 20) / Mean($volume, 20)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_volcv_20d",
            qlib_expression="Std($volume, 20) / Mean($volume, 20)",
            description="20日成交量变异系数"
        )


class QlibVolpriceVolcv30dFactor(QlibBaseFactor):
    """
    30日成交量变异系数

    Qlib表达式: Std($volume, 30) / Mean($volume, 30)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_volcv_30d",
            qlib_expression="Std($volume, 30) / Mean($volume, 30)",
            description="30日成交量变异系数"
        )


class QlibVolpricePvcorr5dFactor(QlibBaseFactor):
    """
    5日价量相关性

    Qlib表达式: Corr($close, $volume, 5)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_pvcorr_5d",
            qlib_expression="Corr($close, $volume, 5)",
            description="5日价量相关性"
        )


class QlibVolpricePvcorr10dFactor(QlibBaseFactor):
    """
    10日价量相关性

    Qlib表达式: Corr($close, $volume, 10)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_pvcorr_10d",
            qlib_expression="Corr($close, $volume, 10)",
            description="10日价量相关性"
        )


class QlibVolpricePvcorr20dFactor(QlibBaseFactor):
    """
    20日价量相关性

    Qlib表达式: Corr($close, $volume, 20)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_pvcorr_20d",
            qlib_expression="Corr($close, $volume, 20)",
            description="20日价量相关性"
        )


class QlibVolpriceRetvolcorr5dFactor(QlibBaseFactor):
    """
    5日收益率与成交量相关性

    Qlib表达式: Corr($close / Ref($close, 1) - 1, $volume, 5)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_retvolcorr_5d",
            qlib_expression="Corr($close / Ref($close, 1) - 1, $volume, 5)",
            description="5日收益率与成交量相关性"
        )


class QlibVolpriceRetvolcorr10dFactor(QlibBaseFactor):
    """
    10日收益率与成交量相关性

    Qlib表达式: Corr($close / Ref($close, 1) - 1, $volume, 10)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_retvolcorr_10d",
            qlib_expression="Corr($close / Ref($close, 1) - 1, $volume, 10)",
            description="10日收益率与成交量相关性"
        )


class QlibVolpriceRetvolcorr20dFactor(QlibBaseFactor):
    """
    20日收益率与成交量相关性

    Qlib表达式: Corr($close / Ref($close, 1) - 1, $volume, 20)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_retvolcorr_20d",
            qlib_expression="Corr($close / Ref($close, 1) - 1, $volume, 20)",
            description="20日收益率与成交量相关性"
        )


class QlibVolpriceTurnover5dFactor(QlibBaseFactor):
    """
    5日成交额比率

    Qlib表达式: $close * $volume / Mean($close * $volume, 5)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_turnover_5d",
            qlib_expression="$close * $volume / Mean($close * $volume, 5)",
            description="5日成交额比率"
        )


class QlibVolpriceTurnover10dFactor(QlibBaseFactor):
    """
    10日成交额比率

    Qlib表达式: $close * $volume / Mean($close * $volume, 10)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_turnover_10d",
            qlib_expression="$close * $volume / Mean($close * $volume, 10)",
            description="10日成交额比率"
        )


class QlibVolpriceTurnover20dFactor(QlibBaseFactor):
    """
    20日成交额比率

    Qlib表达式: $close * $volume / Mean($close * $volume, 20)
    """

    def __init__(self):
        super().__init__(
            name="qlib_volprice_turnover_20d",
            qlib_expression="$close * $volume / Mean($close * $volume, 20)",
            description="20日成交额比率"
        )


def get_volprice_factors():
    """返回所有17个volprice因子实例"""
    return [
        QlibVolpriceVolratio5dFactor(),
        QlibVolpriceVolratio10dFactor(),
        QlibVolpriceVolratio20dFactor(),
        QlibVolpriceVolratio30dFactor(),
        QlibVolpriceVolcv5dFactor(),
        QlibVolpriceVolcv10dFactor(),
        QlibVolpriceVolcv20dFactor(),
        QlibVolpriceVolcv30dFactor(),
        QlibVolpricePvcorr5dFactor(),
        QlibVolpricePvcorr10dFactor(),
        QlibVolpricePvcorr20dFactor(),
        QlibVolpriceRetvolcorr5dFactor(),
        QlibVolpriceRetvolcorr10dFactor(),
        QlibVolpriceRetvolcorr20dFactor(),
        QlibVolpriceTurnover5dFactor(),
        QlibVolpriceTurnover10dFactor(),
        QlibVolpriceTurnover20dFactor(),
    ]
