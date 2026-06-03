# -*- coding: utf-8 -*-
"""
情绪因子
基于龙虎榜、社交媒体热度、板块联动性的市场情绪分析因子
支持数据缺失场景的分段验证
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
from datetime import datetime, timedelta

from .factor_manager import BaseFactor, FactorValue

logger = logging.getLogger(__name__)


class LonghuBangSentimentFactor(BaseFactor):
    """龙虎榜热度因子 - 基于龙虎榜数据的市场情绪"""

    def __init__(self):
        super().__init__(
            name="longhu_sentiment",
            category="sentiment",
            description="龙虎榜热度因子，反映市场资金关注度和情绪"
        )
        self.dependencies = ["price", "volume"]
        self.lookback_days = 10
        self.data_available = False  # 标记数据是否可用

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算龙虎榜情绪因子"""

        # 检查是否有龙虎榜数据
        longhu_data = kwargs.get('longhu_data')

        if longhu_data is None or longhu_data.empty:
            # 使用代理：成交量异常作为关注度代理
            return self._calculate_proxy_sentiment(data, symbol)

        # 标记数据可用（用于后续分段验证）
        self.data_available = True

        # 计算基于龙虎榜的真实情绪
        return self._calculate_longhu_sentiment(data, symbol, longhu_data)

    def _calculate_proxy_sentiment(self, data: Dict[str, pd.DataFrame],
                                   symbol: str) -> FactorValue:
        """代理情绪：基于成交量异常"""
        volume_df = data['volume'].tail(self.lookback_days)

        if len(volume_df) < 5:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3,
                             metadata={'data_type': 'proxy', 'reason': 'no_longhu_data'})

        volumes = volume_df['Volume'].values

        # 量比
        recent_volume = np.mean(volumes[-3:])
        baseline_volume = np.mean(volumes[:-3])

        if baseline_volume > 0:
            volume_ratio = recent_volume / baseline_volume
        else:
            volume_ratio = 1.0

        # 转换为情绪信号
        sentiment = np.tanh((volume_ratio - 1) * 2)

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=sentiment,
            timestamp=datetime.now(),
            confidence=0.4,  # 代理数据置信度较低
            metadata={
                'data_type': 'proxy',
                'volume_ratio': float(volume_ratio)
            }
        )

    def _calculate_longhu_sentiment(self, data: Dict[str, pd.DataFrame],
                                    symbol: str, longhu_data: pd.DataFrame) -> FactorValue:
        """基于龙虎榜的真实情绪"""

        # 筛选最近的龙虎榜记录
        recent_date = datetime.now() - timedelta(days=self.lookback_days)
        recent_longhu = longhu_data[
            pd.to_datetime(longhu_data['date']) >= recent_date
        ]

        if len(recent_longhu) == 0:
            # 最近无龙虎榜记录，使用代理
            return self._calculate_proxy_sentiment(data, symbol)

        # 特征1: 上榜频率
        appearance_count = len(recent_longhu)
        freq_score = min(appearance_count / 3, 1.0)  # 3次以上为最高

        # 特征2: 净买入强度
        if 'net_amount' in recent_longhu.columns:
            net_amount = recent_longhu['net_amount'].mean()
            # 标准化（假设亿元为单位）
            amount_score = np.tanh(net_amount / 10000)  # 1000万为中等
        else:
            amount_score = 0.0

        # 特征3: 买入集中度
        if 'buy_amount' in recent_longhu.columns and 'sell_amount' in recent_longhu.columns:
            total_buy = recent_longhu['buy_amount'].sum()
            total_sell = recent_longhu['sell_amount'].sum()
            if total_sell > 0:
                buy_sell_ratio = total_buy / total_sell
                concentration_score = np.tanh((buy_sell_ratio - 1) * 2)
            else:
                concentration_score = 0.5
        else:
            concentration_score = 0.0

        # 综合情绪得分
        sentiment = (
            freq_score * 0.4 +
            amount_score * 0.4 +
            concentration_score * 0.2
        )

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=sentiment,
            timestamp=datetime.now(),
            confidence=0.80,  # 真实数据置信度高
            raw_data={
                'appearance_count': appearance_count,
                'freq_score': float(freq_score),
                'amount_score': float(amount_score),
                'concentration_score': float(concentration_score)
            },
            metadata={'data_type': 'real'}
        )


class SocialMediaBuzzFactor(BaseFactor):
    """社交媒体热度因子"""

    def __init__(self):
        super().__init__(
            name="social_media_buzz",
            category="sentiment",
            description="社交媒体热度因子，捕捉股票在社交平台的讨论热度"
        )
        self.dependencies = ["price", "volume"]
        self.lookback_days = 5

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算社交媒体热度因子"""

        # 检查是否有社交媒体数据
        social_data = kwargs.get('social_data')

        if social_data is None or social_data.empty:
            # 使用代理：价格波动+成交量作为关注度代理
            return self._calculate_attention_proxy(data, symbol)

        # 计算真实社交媒体热度
        return self._calculate_social_buzz(data, symbol, social_data)

    def _calculate_attention_proxy(self, data: Dict[str, pd.DataFrame],
                                   symbol: str) -> FactorValue:
        """代理指标：价格波动+成交量"""
        price_df = data['price'].tail(self.lookback_days)
        volume_df = data['volume'].tail(self.lookback_days)

        if len(price_df) < 3 or len(volume_df) < 3:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3,
                             metadata={'data_type': 'proxy'})

        # 价格波动度
        returns = price_df['Close'].pct_change().abs()
        volatility_score = returns.mean() * 100  # 百分比

        # 成交量异常
        volumes = volume_df['Volume'].values
        volume_ratio = volumes[-1] / (np.mean(volumes[:-1]) + 1)

        # 综合关注度
        attention = (
            np.tanh(volatility_score - 2) * 0.6 +  # 波动>2%为高
            np.tanh((volume_ratio - 1) * 2) * 0.4
        )

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=attention,
            timestamp=datetime.now(),
            confidence=0.35,
            metadata={
                'data_type': 'proxy',
                'volatility_score': float(volatility_score),
                'volume_ratio': float(volume_ratio)
            }
        )

    def _calculate_social_buzz(self, data: Dict[str, pd.DataFrame],
                               symbol: str, social_data: pd.DataFrame) -> FactorValue:
        """真实社交媒体热度"""

        # 筛选最近数据
        recent_date = datetime.now() - timedelta(days=self.lookback_days)
        recent_social = social_data[
            pd.to_datetime(social_data['timestamp']) >= recent_date
        ]

        if len(recent_social) == 0:
            return self._calculate_attention_proxy(data, symbol)

        # 特征1: 讨论热度（帖子/评论数量）
        if 'count' in recent_social.columns:
            buzz_count = recent_social['count'].sum()
            count_score = np.tanh(buzz_count / 100)  # 100条为中等热度
        else:
            count_score = 0.5

        # 特征2: 情绪倾向（正面/负面）
        if 'sentiment' in recent_social.columns:
            avg_sentiment = recent_social['sentiment'].mean()
            sentiment_score = avg_sentiment  # 假设已标准化到[-1,1]
        else:
            sentiment_score = 0.0

        # 特征3: 热度增长率
        if len(recent_social) >= 3:
            recent_count = len(recent_social[-2:])
            earlier_count = len(recent_social[:-2])
            if earlier_count > 0:
                growth_rate = (recent_count - earlier_count) / earlier_count
                growth_score = np.tanh(growth_rate)
            else:
                growth_score = 0.5
        else:
            growth_score = 0.0

        # 综合得分
        buzz = (
            count_score * 0.4 +
            sentiment_score * 0.3 +
            growth_score * 0.3
        )

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=buzz,
            timestamp=datetime.now(),
            confidence=0.75,
            raw_data={
                'count_score': float(count_score),
                'sentiment_score': float(sentiment_score),
                'growth_score': float(growth_score)
            },
            metadata={'data_type': 'real'}
        )


class SectorMomentumFactor(BaseFactor):
    """板块联动性因子"""

    def __init__(self):
        super().__init__(
            name="sector_momentum",
            category="sentiment",
            description="板块联动性因子，捕捉板块轮动效应"
        )
        self.dependencies = ["price"]
        self.lookback_days = 10

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算板块联动性因子"""

        # 获取板块数据
        sector_data = kwargs.get('sector_data')

        price_df = data['price'].tail(self.lookback_days)

        if len(price_df) < 5:
            return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.5)

        # 计算个股收益
        stock_returns = price_df['Close'].pct_change()

        if sector_data is None or sector_data.empty:
            # 使用简化版：基于个股动量
            momentum = stock_returns.mean()
            signal = np.tanh(momentum * 50)

            return FactorValue(
                symbol=symbol,
                factor_name=self.name,
                value=signal,
                timestamp=datetime.now(),
                confidence=0.45,
                metadata={'data_type': 'simplified'}
            )

        # 计算板块收益
        sector_returns = sector_data['Close'].pct_change()

        # 对齐长度
        min_len = min(len(stock_returns), len(sector_returns))
        stock_returns = stock_returns.tail(min_len)
        sector_returns = sector_returns.tail(min_len)

        # 计算相关性
        correlation = stock_returns.corr(sector_returns)

        # 板块动量
        sector_momentum = sector_returns.mean()

        # 综合信号
        # 如果板块动量为正且个股与板块高度相关，给正信号
        if correlation > 0.5 and sector_momentum > 0:
            signal = min(1.0, correlation * sector_momentum * 50)
        elif correlation > 0.5 and sector_momentum < 0:
            signal = max(-1.0, correlation * sector_momentum * 50)
        else:
            # 相关性低，使用个股自身动量
            signal = np.tanh(stock_returns.mean() * 50)

        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=signal,
            timestamp=datetime.now(),
            confidence=0.70,
            raw_data={
                'correlation': float(correlation) if not np.isnan(correlation) else 0.0,
                'sector_momentum': float(sector_momentum),
                'stock_momentum': float(stock_returns.mean())
            }
        )


def register_sentiment_factors():
    """注册所有情绪因子"""
    from .factor_manager import get_factor_manager

    factor_manager = get_factor_manager()

    factor_manager.register_factor(LonghuBangSentimentFactor())
    factor_manager.register_factor(SocialMediaBuzzFactor())
    factor_manager.register_factor(SectorMomentumFactor())

    logger.info("✅ 情绪因子注册完成 (3个因子，支持代理数据)")
