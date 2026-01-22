# -*- coding: utf-8 -*-
"""
基本面AI因子
包含估值、盈利能力、成长性、财务健康等基本面分析因子
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from .factor_manager import BaseFactor, FactorValue

logger = logging.getLogger(__name__)


class ValuePEFactor(BaseFactor):
    """市盈率估值因子（低PE = 高分）"""

    def __init__(self):
        super().__init__(
            name="value_pe",
            category="fundamental",
            description="基于市盈率的估值因子，低PE股票获得高分"
        )
        self.dependencies = ["fundamental"]
        self.lookback_days = 1  # 基本面数据不需要时间序列

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算PE估值因子

        逻辑：
        - PE < 10: 极度低估，得分 0.8-1.0
        - PE 10-20: 合理偏低，得分 0.4-0.8
        - PE 20-30: 合理偏高，得分 0.0-0.4
        - PE 30-50: 高估，得分 -0.4-0.0
        - PE > 50: 极度高估，得分 -1.0--0.4
        - PE <= 0: 亏损公司，得分 -0.8
        """
        fundamental = data.get("fundamental", {})

        if not fundamental or not isinstance(fundamental, dict):
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3)

        pe_ratio = fundamental.get('pe_ratio', 0)

        # 处理异常值
        if pe_ratio is None or pe_ratio <= 0:
            # 亏损公司或无效PE
            score = -0.8
            confidence = 0.4
        elif pe_ratio < 10:
            # 极度低估
            score = 0.8 + (10 - pe_ratio) / 10 * 0.2  # 0.8-1.0
            confidence = 0.9
        elif pe_ratio < 20:
            # 合理偏低
            score = 0.4 + (20 - pe_ratio) / 10 * 0.4  # 0.4-0.8
            confidence = 0.85
        elif pe_ratio < 30:
            # 合理偏高
            score = 0.0 + (30 - pe_ratio) / 10 * 0.4  # 0.0-0.4
            confidence = 0.75
        elif pe_ratio < 50:
            # 高估
            score = -0.4 + (50 - pe_ratio) / 20 * 0.4  # -0.4-0.0
            confidence = 0.7
        else:
            # 极度高估
            score = max(-1.0, -0.4 - (pe_ratio - 50) / 100 * 0.6)  # -1.0--0.4
            confidence = 0.65

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=score,
            timestamp=datetime.now(),
            confidence=confidence,
            raw_data={'pe_ratio': pe_ratio}
        )


class ValuePBFactor(BaseFactor):
    """市净率估值因子（低PB = 高分）"""

    def __init__(self):
        super().__init__(
            name="value_pb",
            category="fundamental",
            description="基于市净率的估值因子，低PB股票获得高分"
        )
        self.dependencies = ["fundamental"]
        self.lookback_days = 1

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算PB估值因子

        逻辑：
        - PB < 1: 破净，得分 0.7-1.0
        - PB 1-2: 合理偏低，得分 0.3-0.7
        - PB 2-3: 合理偏高，得分 0.0-0.3
        - PB 3-5: 高估，得分 -0.3-0.0
        - PB > 5: 极度高估，得分 -1.0--0.3
        - PB <= 0: 资不抵债，得分 -0.9
        """
        fundamental = data.get("fundamental", {})

        if not fundamental or not isinstance(fundamental, dict):
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3)

        pb_ratio = fundamental.get('pb_ratio', 0)

        if pb_ratio is None or pb_ratio <= 0:
            # 资不抵债或无效PB
            score = -0.9
            confidence = 0.4
        elif pb_ratio < 1:
            # 破净
            score = 0.7 + (1 - pb_ratio) / 1 * 0.3  # 0.7-1.0
            confidence = 0.9
        elif pb_ratio < 2:
            # 合理偏低
            score = 0.3 + (2 - pb_ratio) / 1 * 0.4  # 0.3-0.7
            confidence = 0.85
        elif pb_ratio < 3:
            # 合理偏高
            score = 0.0 + (3 - pb_ratio) / 1 * 0.3  # 0.0-0.3
            confidence = 0.75
        elif pb_ratio < 5:
            # 高估
            score = -0.3 + (5 - pb_ratio) / 2 * 0.3  # -0.3-0.0
            confidence = 0.7
        else:
            # 极度高估
            score = max(-1.0, -0.3 - (pb_ratio - 5) / 10 * 0.7)  # -1.0--0.3
            confidence = 0.65

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=score,
            timestamp=datetime.now(),
            confidence=confidence,
            raw_data={'pb_ratio': pb_ratio}
        )


class ProfitabilityROEFactor(BaseFactor):
    """ROE盈利能力因子（高ROE = 高分）"""

    def __init__(self):
        super().__init__(
            name="profitability_roe",
            category="fundamental",
            description="基于净资产收益率的盈利能力因子，高ROE获得高分"
        )
        self.dependencies = ["fundamental"]
        self.lookback_days = 1

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算ROE盈利能力因子

        逻辑：
        - ROE > 20%: 优秀，得分 0.7-1.0
        - ROE 15%-20%: 良好，得分 0.4-0.7
        - ROE 10%-15%: 一般，得分 0.1-0.4
        - ROE 5%-10%: 偏弱，得分 -0.2-0.1
        - ROE 0-5%: 较差，得分 -0.5--0.2
        - ROE < 0: 亏损，得分 -1.0--0.5
        """
        fundamental = data.get("fundamental", {})

        if not fundamental or not isinstance(fundamental, dict):
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3)

        roe = fundamental.get('roe', 0)

        if roe is None:
            score = 0.0
            confidence = 0.3
        elif roe > 20:
            # 优秀（ROE以百分比形式存储，如20表示20%）
            score = min(1.0, 0.7 + (roe - 20) / 30 * 0.3)  # 0.7-1.0
            confidence = 0.95
        elif roe > 15:
            # 良好
            score = 0.4 + (roe - 15) / 5 * 0.3  # 0.4-0.7
            confidence = 0.9
        elif roe > 10:
            # 一般
            score = 0.1 + (roe - 10) / 5 * 0.3  # 0.1-0.4
            confidence = 0.8
        elif roe > 5:
            # 偏弱
            score = -0.2 + (roe - 5) / 5 * 0.3  # -0.2-0.1
            confidence = 0.7
        elif roe > 0:
            # 较差
            score = -0.5 + roe / 5 * 0.3  # -0.5--0.2
            confidence = 0.6
        else:
            # 亏损
            score = max(-1.0, -0.5 + roe / 20 * 0.5)  # -1.0--0.5
            confidence = 0.5

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=score,
            timestamp=datetime.now(),
            confidence=confidence,
            raw_data={'roe': roe}
        )


class GrowthRevenueFactor(BaseFactor):
    """营收增长因子（高增长 = 高分）"""

    def __init__(self):
        super().__init__(
            name="growth_revenue",
            category="fundamental",
            description="基于营收同比增长率的成长性因子，高增长获得高分"
        )
        self.dependencies = ["fundamental"]
        self.lookback_days = 1

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算营收增长因子

        逻辑：
        - 增长 > 30%: 高成长，得分 0.7-1.0
        - 增长 20%-30%: 快速增长，得分 0.5-0.7
        - 增长 10%-20%: 稳健增长，得分 0.2-0.5
        - 增长 0-10%: 低速增长，得分 0.0-0.2
        - 增长 -10%-0: 轻微下滑，得分 -0.3-0.0
        - 增长 < -10%: 明显下滑，得分 -1.0--0.3
        """
        fundamental = data.get("fundamental", {})

        if not fundamental or not isinstance(fundamental, dict):
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3)

        revenue_yoy = fundamental.get('revenue_yoy', 0)

        if revenue_yoy is None:
            score = 0.0
            confidence = 0.3
        elif revenue_yoy > 30:
            # 高成长
            score = min(1.0, 0.7 + (revenue_yoy - 30) / 50 * 0.3)  # 0.7-1.0
            confidence = 0.9
        elif revenue_yoy > 20:
            # 快速增长
            score = 0.5 + (revenue_yoy - 20) / 10 * 0.2  # 0.5-0.7
            confidence = 0.85
        elif revenue_yoy > 10:
            # 稳健增长
            score = 0.2 + (revenue_yoy - 10) / 10 * 0.3  # 0.2-0.5
            confidence = 0.8
        elif revenue_yoy > 0:
            # 低速增长
            score = 0.0 + revenue_yoy / 10 * 0.2  # 0.0-0.2
            confidence = 0.7
        elif revenue_yoy > -10:
            # 轻微下滑
            score = -0.3 + (revenue_yoy + 10) / 10 * 0.3  # -0.3-0.0
            confidence = 0.6
        else:
            # 明显下滑
            score = max(-1.0, -0.3 + (revenue_yoy + 10) / 30 * 0.7)  # -1.0--0.3
            confidence = 0.5

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=score,
            timestamp=datetime.now(),
            confidence=confidence,
            raw_data={'revenue_yoy': revenue_yoy}
        )


class ProfitQualityFactor(BaseFactor):
    """盈利质量因子（高毛利率 = 高分）"""

    def __init__(self):
        super().__init__(
            name="profit_quality",
            category="fundamental",
            description="基于毛利率的盈利质量因子，高毛利率获得高分"
        )
        self.dependencies = ["fundamental"]
        self.lookback_days = 1

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算盈利质量因子

        逻辑：
        - 毛利率 > 50%: 优质，得分 0.7-1.0
        - 毛利率 40%-50%: 良好，得分 0.5-0.7
        - 毛利率 30%-40%: 一般，得分 0.2-0.5
        - 毛利率 20%-30%: 偏低，得分 0.0-0.2
        - 毛利率 10%-20%: 较低，得分 -0.3-0.0
        - 毛利率 < 10%: 微利，得分 -0.7--0.3
        - 毛利率 < 0: 亏损，得分 -1.0
        """
        fundamental = data.get("fundamental", {})

        if not fundamental or not isinstance(fundamental, dict):
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3)

        gross_margin = fundamental.get('grossprofit_margin', 0)

        if gross_margin is None:
            score = 0.0
            confidence = 0.3
        elif gross_margin > 50:
            # 优质
            score = min(1.0, 0.7 + (gross_margin - 50) / 50 * 0.3)  # 0.7-1.0
            confidence = 0.95
        elif gross_margin > 40:
            # 良好
            score = 0.5 + (gross_margin - 40) / 10 * 0.2  # 0.5-0.7
            confidence = 0.9
        elif gross_margin > 30:
            # 一般
            score = 0.2 + (gross_margin - 30) / 10 * 0.3  # 0.2-0.5
            confidence = 0.85
        elif gross_margin > 20:
            # 偏低
            score = 0.0 + (gross_margin - 20) / 10 * 0.2  # 0.0-0.2
            confidence = 0.75
        elif gross_margin > 10:
            # 较低
            score = -0.3 + (gross_margin - 10) / 10 * 0.3  # -0.3-0.0
            confidence = 0.65
        elif gross_margin > 0:
            # 微利
            score = -0.7 + gross_margin / 10 * 0.4  # -0.7--0.3
            confidence = 0.55
        else:
            # 亏损
            score = -1.0
            confidence = 0.5

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=score,
            timestamp=datetime.now(),
            confidence=confidence,
            raw_data={'grossprofit_margin': gross_margin}
        )


class FinancialHealthFactor(BaseFactor):
    """财务健康因子（低债务权益比 = 高分）"""

    def __init__(self):
        super().__init__(
            name="financial_health",
            category="fundamental",
            description="基于债务权益比的财务健康因子，低杠杆获得高分"
        )
        self.dependencies = ["fundamental"]
        self.lookback_days = 1

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算财务健康因子

        逻辑：
        - D/E < 0.3: 极低杠杆，得分 0.7-1.0
        - D/E 0.3-0.5: 低杠杆，得分 0.5-0.7
        - D/E 0.5-1.0: 适度杠杆，得分 0.2-0.5
        - D/E 1.0-1.5: 偏高杠杆，得分 0.0-0.2
        - D/E 1.5-2.0: 高杠杆，得分 -0.3-0.0
        - D/E > 2.0: 过高杠杆，得分 -1.0--0.3
        - D/E < 0: 异常（资不抵债），得分 -0.9
        """
        fundamental = data.get("fundamental", {})

        if not fundamental or not isinstance(fundamental, dict):
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3)

        debt_to_equity = fundamental.get('debt_to_equity', 0)

        if debt_to_equity is None:
            score = 0.0
            confidence = 0.3
        elif debt_to_equity < 0:
            # 异常情况（可能资不抵债）
            score = -0.9
            confidence = 0.4
        elif debt_to_equity < 0.3:
            # 极低杠杆
            score = 0.7 + (0.3 - debt_to_equity) / 0.3 * 0.3  # 0.7-1.0
            confidence = 0.95
        elif debt_to_equity < 0.5:
            # 低杠杆
            score = 0.5 + (0.5 - debt_to_equity) / 0.2 * 0.2  # 0.5-0.7
            confidence = 0.9
        elif debt_to_equity < 1.0:
            # 适度杠杆
            score = 0.2 + (1.0 - debt_to_equity) / 0.5 * 0.3  # 0.2-0.5
            confidence = 0.85
        elif debt_to_equity < 1.5:
            # 偏高杠杆
            score = 0.0 + (1.5 - debt_to_equity) / 0.5 * 0.2  # 0.0-0.2
            confidence = 0.75
        elif debt_to_equity < 2.0:
            # 高杠杆
            score = -0.3 + (2.0 - debt_to_equity) / 0.5 * 0.3  # -0.3-0.0
            confidence = 0.65
        else:
            # 过高杠杆
            score = max(-1.0, -0.3 - (debt_to_equity - 2.0) / 3.0 * 0.7)  # -1.0--0.3
            confidence = 0.55

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=score,
            timestamp=datetime.now(),
            confidence=confidence,
            raw_data={'debt_to_equity': debt_to_equity}
        )
