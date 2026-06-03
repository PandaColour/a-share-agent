# -*- coding: utf-8 -*-
"""
技术指标计算器实现
遵循单一职责原则，专门负责技术指标计算
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List

try:
    from ..interfaces import IIndicatorCalculator, StockInfo
except ImportError:
    from data.interfaces import IIndicatorCalculator, StockInfo

logger = logging.getLogger(__name__)


class TechnicalIndicatorCalculator(IIndicatorCalculator):
    """技术指标计算器"""

    def __init__(self):
        self.supported_indicators = [
            'ma5', 'ma20', 'ma50', 'ma200',
            'rsi', 'macd', 'macd_signal', 'macd_histogram',
            'kdj_k', 'kdj_d', 'kdj_j',
            'williams_r', 'cci',
            'volatility', 'price_position',
            'turnover_rate', 'volume_ratio',
            'volume_price_trend', 'volume_price_correlation'
        ]

    def get_supported_indicators(self) -> List[str]:
        """获取支持的指标列表"""
        return self.supported_indicators.copy()

    def calculate_indicators(self, data: pd.DataFrame, stock_info: StockInfo = None) -> Dict:
        """计算技术指标"""
        if data.empty:
            return {}

        indicators = {}

        try:
            # 移动平均线
            indicators.update(self._calculate_moving_averages(data))

            # 动量指标
            indicators.update(self._calculate_momentum_indicators(data))

            # 波动率指标
            indicators.update(self._calculate_volatility_indicators(data))

            # 成交量指标
            indicators.update(self._calculate_volume_indicators(data, stock_info))

            # 价格位置指标
            indicators.update(self._calculate_position_indicators(data))

        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")

        return indicators

    def _calculate_moving_averages(self, data: pd.DataFrame) -> Dict:
        """计算移动平均线"""
        indicators = {}

        periods = [5, 20, 50, 200]
        for period in periods:
            if len(data) >= period:
                ma_value = data['Close'].rolling(window=period).mean().iloc[-1]
                indicators[f'ma{period}'] = ma_value

        return indicators

    def _calculate_momentum_indicators(self, data: pd.DataFrame) -> Dict:
        """计算动量指标"""
        indicators = {}

        # RSI
        if len(data) >= 14:
            indicators.update(self._calculate_rsi(data['Close']))

        # MACD
        if len(data) >= 26:
            indicators.update(self._calculate_macd(data['Close']))

        # KDJ
        if len(data) >= 9:
            indicators.update(self._calculate_kdj(data))

        # Williams %R
        if len(data) >= 14:
            indicators.update(self._calculate_williams_r(data))

        # CCI
        if len(data) >= 14:
            indicators.update(self._calculate_cci(data))

        return indicators

    def _calculate_volatility_indicators(self, data: pd.DataFrame) -> Dict:
        """计算波动率指标"""
        indicators = {}

        if len(data) >= 20:
            returns = data['Close'].pct_change()
            volatility = returns.rolling(window=20).std().iloc[-1] * np.sqrt(252)
            indicators['volatility'] = volatility

        return indicators

    def _calculate_volume_indicators(self, data: pd.DataFrame, stock_info: StockInfo = None) -> Dict:
        """计算成交量指标"""
        indicators = {}

        try:
            # 换手率
            indicators.update(self._calculate_turnover_rate(data, stock_info))

            # 量价关系
            if len(data) >= 5:
                indicators.update(self._calculate_volume_price_relation(data))

        except Exception as e:
            logger.error(f"计算成交量指标失败: {e}")

        return indicators

    def _calculate_position_indicators(self, data: pd.DataFrame) -> Dict:
        """计算价格位置指标"""
        indicators = {}

        try:
            current_price = data['Close'].iloc[-1]
            window = min(252, len(data))  # 最多252个交易日（约1年）

            high_period = data['High'].rolling(window=window).max().iloc[-1]
            low_period = data['Low'].rolling(window=window).min().iloc[-1]

            if high_period != low_period:
                price_position = (current_price - low_period) / (high_period - low_period)
                indicators['price_position'] = price_position
            else:
                indicators['price_position'] = 0.5

        except Exception as e:
            logger.error(f"计算价格位置指标失败: {e}")
            indicators['price_position'] = 0.5

        return indicators

    def _calculate_rsi(self, close_prices: pd.Series, period: int = 14) -> Dict:
        """计算RSI指标"""
        try:
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            return {'rsi': rsi.iloc[-1]}
        except Exception as e:
            logger.error(f"RSI计算失败: {e}")
            return {'rsi': 50.0}

    def _calculate_macd(self, close_prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """计算MACD指标"""
        try:
            ema_fast = close_prices.ewm(span=fast).mean()
            ema_slow = close_prices.ewm(span=slow).mean()

            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal).mean()
            histogram = macd_line - signal_line

            return {
                'macd': macd_line.iloc[-1],
                'macd_signal': signal_line.iloc[-1],
                'macd_histogram': histogram.iloc[-1]
            }
        except Exception as e:
            logger.error(f"MACD计算失败: {e}")
            return {'macd': 0, 'macd_signal': 0, 'macd_histogram': 0}

    def _calculate_kdj(self, data: pd.DataFrame, k_period: int = 9, d_period: int = 3) -> Dict:
        """计算KDJ指标"""
        try:
            low_min = data['Low'].rolling(window=k_period).min()
            high_max = data['High'].rolling(window=k_period).max()

            # RSV
            rsv = ((data['Close'] - low_min) / (high_max - low_min)) * 100

            # K值
            k_values = rsv.rolling(window=d_period).mean()

            # D值
            d_values = k_values.rolling(window=d_period).mean()

            # J值
            j_values = 3 * k_values - 2 * d_values

            return {
                'kdj_k': k_values.iloc[-1] if not k_values.empty else 50,
                'kdj_d': d_values.iloc[-1] if not d_values.empty else 50,
                'kdj_j': j_values.iloc[-1] if not j_values.empty else 50
            }
        except Exception as e:
            logger.error(f"KDJ计算失败: {e}")
            return {'kdj_k': 50, 'kdj_d': 50, 'kdj_j': 50}

    def _calculate_williams_r(self, data: pd.DataFrame, period: int = 14) -> Dict:
        """计算威廉指标"""
        try:
            high_max = data['High'].rolling(window=period).max()
            low_min = data['Low'].rolling(window=period).min()

            williams_r = ((high_max - data['Close']) / (high_max - low_min)) * (-100)

            return {'williams_r': williams_r.iloc[-1] if not williams_r.empty else -50}
        except Exception as e:
            logger.error(f"威廉指标计算失败: {e}")
            return {'williams_r': -50}

    def _calculate_cci(self, data: pd.DataFrame, period: int = 14) -> Dict:
        """计算CCI指标"""
        try:
            # 典型价格
            tp = (data['High'] + data['Low'] + data['Close']) / 3

            # 移动平均
            ma_tp = tp.rolling(window=period).mean()

            # 平均绝对偏差
            md = tp.rolling(window=period).apply(
                lambda x: np.mean(np.abs(x - x.mean())), raw=True
            )

            # CCI
            cci = (tp - ma_tp) / (0.015 * md)

            return {'cci': cci.iloc[-1] if not cci.empty else 0}
        except Exception as e:
            logger.error(f"CCI指标计算失败: {e}")
            return {'cci': 0}

    def _calculate_turnover_rate(self, data: pd.DataFrame, stock_info: StockInfo = None) -> Dict:
        """计算换手率"""
        try:
            if stock_info and stock_info.shares_outstanding > 0:
                # 使用实际流通股本
                turnover_rate = (data['Volume'].iloc[-1] / stock_info.shares_outstanding) * 100
                turnover_rate = min(turnover_rate, 100)  # 限制最大100%
            else:
                # 使用相对换手率
                if len(data) >= 20:
                    avg_volume = data['Volume'].rolling(window=20).mean().iloc[-1]
                else:
                    avg_volume = data['Volume'].mean()

                if avg_volume > 0:
                    turnover_rate = min((data['Volume'].iloc[-1] / avg_volume) * 2, 20)
                else:
                    turnover_rate = 1.0

            return {'turnover_rate': turnover_rate}
        except Exception as e:
            logger.error(f"换手率计算失败: {e}")
            return {'turnover_rate': 1.0}

    def _calculate_volume_price_relation(self, data: pd.DataFrame) -> Dict:
        """计算量价关系"""
        try:
            recent_data = data.tail(5)

            price_change = recent_data['Close'].pct_change().dropna()
            volume_change = recent_data['Volume'].pct_change().dropna()

            if len(price_change) > 2 and len(volume_change) > 2:
                correlation = np.corrcoef(price_change, volume_change)[0, 1]

                # 判断量价关系
                if correlation > 0.3:
                    trend = "量价齐升"
                elif correlation < -0.3:
                    trend = "量价背离"
                else:
                    trend = "量价平衡"

                # 计算量比
                avg_volume = recent_data['Volume'].mean()
                current_volume = recent_data['Volume'].iloc[-1]
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

                return {
                    'volume_price_trend': trend,
                    'volume_price_correlation': round(correlation, 3),
                    'volume_ratio': round(volume_ratio, 2)
                }
            else:
                return {
                    'volume_price_trend': 'neutral',
                    'volume_price_correlation': 0.0,
                    'volume_ratio': 1.0
                }
        except Exception as e:
            logger.error(f"量价关系计算失败: {e}")
            return {
                'volume_price_trend': 'neutral',
                'volume_price_correlation': 0.0,
                'volume_ratio': 1.0
            }