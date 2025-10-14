# -*- coding: utf-8 -*-
"""
Beta系数计算器
计算个股相对市场的系统性风险敞口
"""

import logging
import pandas as pd
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)


class BetaCalculator:
    """Beta系数计算器"""

    def __init__(self, config_manager=None):
        """
        初始化Beta计算器

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.beta_config = {}

        if config_manager:
            self.beta_config = config_manager.get('analysis_settings.market_analysis.beta_analysis', {})

        self.enabled = self.beta_config.get('enabled', True)
        self.rolling_window = self.beta_config.get('rolling_window', 60)
        self.high_beta_threshold = self.beta_config.get('beta_thresholds', {}).get('high_beta', 1.2)
        self.low_beta_threshold = self.beta_config.get('beta_thresholds', {}).get('low_beta', 0.8)

        logger.info(f"📊 Beta计算器初始化: {'已启用' if self.enabled else '已禁用'}, "
                   f"窗口={self.rolling_window}天")

    def calculate_beta(self,
                      stock_data: pd.DataFrame,
                      market_data: pd.DataFrame,
                      window: Optional[int] = None) -> float:
        """
        计算个股Beta系数

        Beta = Cov(Stock_Returns, Market_Returns) / Var(Market_Returns)

        Args:
            stock_data: 个股数据（必须包含'close'列）
            market_data: 市场数据（必须包含'close'列）
            window: 计算窗口天数，None则使用配置值

        Returns:
            float: Beta系数，1.0表示与市场同步，>1.0表示更激进，<1.0表示更保守
        """
        if not self.enabled:
            logger.debug("Beta计算已禁用，返回默认值1.0")
            return 1.0

        try:
            window = window or self.rolling_window

            # 计算收益率 (支持大小写列名)
            close_col = 'Close' if 'Close' in stock_data.columns else 'close'
            stock_returns = stock_data[close_col].pct_change().dropna()
            market_returns = market_data[close_col].pct_change().dropna()

            # 找到共同日期
            common_dates = stock_returns.index.intersection(market_returns.index)

            if len(common_dates) < window:
                logger.warning(f"⚠️ 共同数据点不足: {len(common_dates)} < {window}，返回默认Beta")
                return 1.0

            # 取最近window天的数据
            stock_returns_aligned = stock_returns.loc[common_dates].tail(window)
            market_returns_aligned = market_returns.loc[common_dates].tail(window)

            # 计算Beta
            covariance = np.cov(stock_returns_aligned, market_returns_aligned)[0, 1]
            market_variance = np.var(market_returns_aligned)

            if market_variance == 0:
                logger.warning("⚠️ 市场方差为0，返回默认Beta")
                return 1.0

            beta = covariance / market_variance

            # 异常值检查
            if abs(beta) > 5:
                logger.warning(f"⚠️ Beta异常值: {beta:.2f}，限制到合理范围")
                beta = 5.0 if beta > 0 else -5.0

            logger.debug(f"✅ Beta计算完成: {beta:.3f}")
            return float(beta)

        except Exception as e:
            logger.error(f"❌ Beta计算失败: {e}")
            return 1.0

    def classify_beta(self, beta: float) -> str:
        """
        分类Beta风险等级

        Args:
            beta: Beta系数

        Returns:
            str: Beta分类（高Beta/中Beta/低Beta/负Beta）
        """
        if beta < 0:
            return "负Beta"
        elif beta < self.low_beta_threshold:
            return "低Beta"
        elif beta < self.high_beta_threshold:
            return "中Beta"
        else:
            return "高Beta"

    def get_beta_description(self, beta: float) -> str:
        """
        获取Beta的描述

        Args:
            beta: Beta系数

        Returns:
            str: Beta描述
        """
        classification = self.classify_beta(beta)

        descriptions = {
            "负Beta": f"与市场负相关(β={beta:.2f})，市场下跌时可能上涨",
            "低Beta": f"防御型股票(β={beta:.2f})，波动小于市场",
            "中Beta": f"市场同步(β={beta:.2f})，与大盘趋势一致",
            "高Beta": f"进攻型股票(β={beta:.2f})，波动大于市场"
        }

        return descriptions.get(classification, f"Beta系数: {beta:.2f}")

    def calculate_systematic_risk_contribution(self, beta: float, market_volatility: float) -> float:
        """
        计算系统性风险贡献

        Args:
            beta: Beta系数
            market_volatility: 市场波动率

        Returns:
            float: 系统性风险贡献（年化）
        """
        return abs(beta * market_volatility)


# 便捷函数
def calculate_stock_beta(stock_data: pd.DataFrame,
                        market_data: pd.DataFrame,
                        config_manager=None,
                        window: Optional[int] = None) -> float:
    """
    计算个股Beta系数的便捷函数

    Args:
        stock_data: 个股数据
        market_data: 市场数据
        config_manager: 配置管理器
        window: 计算窗口

    Returns:
        float: Beta系数
    """
    calculator = BetaCalculator(config_manager)
    return calculator.calculate_beta(stock_data, market_data, window)