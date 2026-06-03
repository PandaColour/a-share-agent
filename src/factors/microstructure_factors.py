# -*- coding: utf-8 -*-
"""
市场微观结构因子
包含大单资金流向、委买委卖比、分时量比异常等微观结构指标
"""

import pandas as pd
import numpy as np
from typing import Dict
import logging
from datetime import datetime

from .factor_manager import BaseFactor, FactorValue

logger = logging.getLogger(__name__)


class BigOrderFlowFactor(BaseFactor):
    """大单资金流向因子"""

    def __init__(self):
        super().__init__(
            name="big_order_flow",
            category="microstructure",
            description="大单净流入分析，识别主力资金动向"
        )
        self.dependencies = ["price", "volume"]
        self.lookback_days = 10

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算大单资金流向"""
        price_df = data['price'].tail(self.lookback_days)
        volume_df = data['volume'].tail(self.lookback_days)

        if len(price_df) < 5 or len(volume_df) < 5:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.5)

        # 合并数据
        min_len = min(len(price_df), len(volume_df))
        price_df = price_df.tail(min_len).reset_index(drop=True)
        volume_df = volume_df.tail(min_len).reset_index(drop=True)

        df = price_df.copy()
        df['Volume'] = volume_df['Volume'].values

        # 计算大单阈值（平均成交量的2倍）
        avg_volume = df['Volume'].mean()
        big_order_threshold = avg_volume * 2

        # 识别大单
        df['is_big_order'] = df['Volume'] > big_order_threshold

        # 判断大单方向（价格上涨=买单，下跌=卖单）
        df['price_change'] = df['Close'].pct_change()
        df['order_direction'] = df['price_change'].apply(
            lambda x: 1 if x > 0 else -1 if x < 0 else 0
        )

        # 计算大单净流入
        big_order_flow = 0.0
        for idx, row in df.iterrows():
            if row['is_big_order']:
                # 大单金额 = 成交量 * 收盘价 * 方向
                flow = row['Volume'] * row['Close'] * row['order_direction']
                big_order_flow += flow

        # 标准化（相对于总成交额）
        total_amount = (df['Volume'] * df['Close']).sum()
        if total_amount > 0:
            normalized_flow = big_order_flow / total_amount
        else:
            normalized_flow = 0.0

        # 转换到[-1, 1]
        signal = np.tanh(normalized_flow * 10)

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=signal,
            timestamp=datetime.now(),
            confidence=0.75,
            raw_data={
                'big_order_flow': float(big_order_flow),
                'total_amount': float(total_amount),
                'normalized_flow': float(normalized_flow)
            }
        )


class BidAskRatioFactor(BaseFactor):
    """委买委卖比因子"""

    def __init__(self):
        super().__init__(
            name="bid_ask_ratio",
            category="microstructure",
            description="委买委卖比例分析，反映买卖意愿强度"
        )
        self.dependencies = ["price", "volume"]
        self.lookback_days = 5

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算委买委卖比"""
        price_df = data['price'].tail(self.lookback_days)
        volume_df = data['volume'].tail(self.lookback_days)

        if len(price_df) < 3 or len(volume_df) < 3:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.5)

        # 合并数据
        min_len = min(len(price_df), len(volume_df))
        price_df = price_df.tail(min_len).reset_index(drop=True)
        volume_df = volume_df.tail(min_len).reset_index(drop=True)

        df = price_df.copy()
        df['Volume'] = volume_df['Volume'].values

        # 使用收盘价相对于最高最低价的位置估计买卖盘强度
        # 收盘价接近最高价 -> 买盘强
        # 收盘价接近最低价 -> 卖盘强
        df['buy_pressure'] = (df['Close'] - df['Low']) / (df['High'] - df['Low'] + 1e-8)
        df['sell_pressure'] = (df['High'] - df['Close']) / (df['High'] - df['Low'] + 1e-8)

        # 加权平均（用成交量加权）
        total_volume = df['Volume'].sum()
        if total_volume > 0:
            weighted_buy = (df['buy_pressure'] * df['Volume']).sum() / total_volume
            weighted_sell = (df['sell_pressure'] * df['Volume']).sum() / total_volume
        else:
            weighted_buy = 0.5
            weighted_sell = 0.5

        # 计算比率
        if weighted_sell > 0:
            bid_ask_ratio = weighted_buy / weighted_sell
        else:
            bid_ask_ratio = 2.0  # 默认偏向买方

        # 转换为信号 (比率>1为正，<1为负)
        signal = np.tanh((bid_ask_ratio - 1) * 2)

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=signal,
            timestamp=datetime.now(),
            confidence=0.68,
            raw_data={
                'bid_ask_ratio': float(bid_ask_ratio),
                'weighted_buy': float(weighted_buy),
                'weighted_sell': float(weighted_sell)
            }
        )


class IntradayVolumeRatioFactor(BaseFactor):
    """分时量比异常因子"""

    def __init__(self):
        super().__init__(
            name="intraday_volume_ratio",
            category="microstructure",
            description="分时量比异常检测，识别短期交易活跃度变化"
        )
        self.dependencies = ["volume"]
        self.lookback_days = 20

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算分时量比异常"""
        volume_df = data['volume'].tail(self.lookback_days)

        if len(volume_df) < 10:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.5)

        volumes = volume_df['Volume'].values

        # 计算量比（最近3天平均 vs 之前均值）
        recent_avg = np.mean(volumes[-3:])
        baseline_avg = np.mean(volumes[:-3])

        if baseline_avg > 0:
            volume_ratio = recent_avg / baseline_avg
        else:
            volume_ratio = 1.0

        # 计算波动性（标准差）
        volume_std = np.std(volumes)
        volume_mean = np.mean(volumes)

        if volume_mean > 0:
            cv = volume_std / volume_mean  # 变异系数
        else:
            cv = 1.0

        # 异常检测：量比突然放大且超过2个标准差
        z_score = (recent_avg - volume_mean) / (volume_std + 1e-8)

        # 综合信号
        # 量比>1.5 且 Z分数>2 -> 强烈放量（正信号）
        # 量比<0.7 且 Z分数<-2 -> 严重缩量（负信号）
        if volume_ratio > 1.5 and z_score > 2:
            signal = 0.8  # 强烈放量
        elif volume_ratio > 1.2 and z_score > 1:
            signal = 0.5  # 温和放量
        elif volume_ratio < 0.7 and z_score < -2:
            signal = -0.8  # 严重缩量
        elif volume_ratio < 0.8 and z_score < -1:
            signal = -0.5  # 温和缩量
        else:
            signal = 0.0  # 正常

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=signal,
            timestamp=datetime.now(),
            confidence=0.72,
            raw_data={
                'volume_ratio': float(volume_ratio),
                'z_score': float(z_score),
                'cv': float(cv)
            }
        )


def register_microstructure_factors():
    """注册所有市场微观结构因子"""
    from .factor_manager import get_factor_manager

    factor_manager = get_factor_manager()

    factor_manager.register_factor(BigOrderFlowFactor())
    factor_manager.register_factor(BidAskRatioFactor())
    factor_manager.register_factor(IntradayVolumeRatioFactor())

    logger.info("✅ 市场微观结构因子注册完成 (3个因子)")
