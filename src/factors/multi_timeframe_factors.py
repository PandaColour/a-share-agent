# -*- coding: utf-8 -*-
"""
多时间框架因子
结合日线和5分钟粒度的MACD/RSI指标，生成多时间框架融合因子
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta

try:
    from .factor_manager import BaseFactor, FactorValue
    from ..data.interfaces import TimeFrame, StockInfo, DataRequest
    from ..data.indicators.multi_timeframe_indicators import MultiTimeframeIndicatorCalculator
    from ..data.multi_timeframe_cache import get_cache
    from .timeframe_weight_optimizer import get_timeframe_weight_optimizer
except ImportError:
    from factor_manager import BaseFactor, FactorValue
    from data.interfaces import TimeFrame, StockInfo, DataRequest
    from data.indicators.multi_timeframe_indicators import MultiTimeframeIndicatorCalculator
    from data.multi_timeframe_cache import get_cache
    from timeframe_weight_optimizer import get_timeframe_weight_optimizer

logger = logging.getLogger(__name__)


class MultiTimeframeRSIFactor(BaseFactor):
    """多时间框架RSI因子

    结合日线RSI(14)、5分钟长周期RSI(70)和5分钟短周期RSI(14)
    通过加权融合生成综合RSI信号
    """

    def __init__(self, config: Dict = None):
        super().__init__(
            name="multi_timeframe_rsi",
            category="technical",
            description="多时间框架RSI因子：融合日线和5分钟RSI信号"
        )
        self.config = config or {}
        self.dependencies = ["price_daily", "price_5min"]
        self.lookback_days = 30

        # 获取配置参数
        rsi_settings = self.config.get('rsi_settings', {})
        self.daily_period = rsi_settings.get('daily_period', 14)
        self.minute_5_long_period = rsi_settings.get('minute_5_long_period', 70)
        self.minute_5_short_period = rsi_settings.get('minute_5_short_period', 14)

        # 信号权重（默认值，从配置文件读取）
        signal_weights = rsi_settings.get('signal_weights', {})
        self.default_weight_daily = signal_weights.get('daily', 0.5)
        self.default_weight_minute_long = signal_weights.get('minute_long', 0.3)
        self.default_weight_minute_short = signal_weights.get('minute_short', 0.2)

        # 初始化计算器和缓存
        self.calculator = MultiTimeframeIndicatorCalculator()
        self.cache = get_cache(self.config.get('cache_settings'))

        # 初始化权重优化器
        self.weight_optimizer = get_timeframe_weight_optimizer()

        # 加载动态权重（如果存在）
        self._load_dynamic_weights()

        logger.info(f"初始化多时间框架RSI因子: 日线周期={self.daily_period}, "
                   f"5分钟长周期={self.minute_5_long_period}, 5分钟短周期={self.minute_5_short_period}")
        logger.info(f"  当前权重: 日线={self.weight_daily:.3f}, "
                   f"5分钟长={self.weight_minute_long:.3f}, 5分钟短={self.weight_minute_short:.3f}")

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算多时间框架RSI因子值

        Args:
            data: 数据字典，包含 'price_daily' 和 'price_5min'
            symbol: 股票代码
            **kwargs: 额外参数

        Returns:
            FactorValue对象，包含融合后的RSI因子值
        """
        try:
            # 1. 验证数据完整性
            if not self.validate_data(data):
                logger.warning(f"{symbol}: 数据验证失败")
                return self._create_default_value(symbol, reason="数据验证失败")

            # 2. 准备多时间框架数据
            timeframe_data = self._prepare_timeframe_data(data, symbol)
            if not timeframe_data:
                return self._create_default_value(symbol, reason="时间框架数据准备失败")

            # 3. 计算各时间框架的RSI指标
            indicators = self.calculator.calculate_indicators_with_timeframes(timeframe_data)

            # 4. 提取RSI值
            rsi_signals = self._extract_rsi_signals(indicators)
            if not rsi_signals:
                return self._create_default_value(symbol, reason="RSI信号提取失败")

            # 5. 融合多时间框架信号
            fused_value, confidence = self._fuse_rsi_signals(rsi_signals)

            # 6. 计算因子值（标准化到[-1, 1]）
            factor_value = self._normalize_rsi_to_factor(fused_value)

            # 7. 构建返回结果
            return FactorValue(
                symbol=symbol,
                factor_name=self.name,
                value=factor_value,
                timestamp=datetime.now(),
                confidence=confidence,
                raw_data={
                    'rsi_daily': rsi_signals.get('daily'),
                    'rsi_5min_long': rsi_signals.get('5min_long'),
                    'rsi_5min_short': rsi_signals.get('5min_short'),
                    'fused_rsi': fused_value,
                    'weights': {
                        'daily': self.weight_daily,
                        'minute_long': self.weight_minute_long,
                        'minute_short': self.weight_minute_short
                    }
                },
                metadata={
                    'timeframes': list(timeframe_data.keys()),
                    'signal_consistency': self._calculate_signal_consistency(rsi_signals)
                }
            )

        except Exception as e:
            logger.error(f"{symbol}: 多时间框架RSI因子计算失败: {e}", exc_info=True)
            return self._create_default_value(symbol, reason=f"计算异常: {str(e)}")

    def _prepare_timeframe_data(self, data: Dict[str, pd.DataFrame], symbol: str) -> Dict[TimeFrame, pd.DataFrame]:
        """准备多时间框架数据"""
        timeframe_data = {}

        try:
            # 日线数据
            if 'price_daily' in data and not data['price_daily'].empty:
                daily_data = data['price_daily'].tail(self.lookback_days * 2)  # 确保足够数据
                timeframe_data[TimeFrame.DAILY] = daily_data

            # 5分钟数据
            if 'price_5min' in data and not data['price_5min'].empty:
                # 5分钟数据需要更多条数（约3天数据）
                lookback_minutes = self.lookback_days * 48  # 1天约48个5分钟K线
                minute_5_data = data['price_5min'].tail(lookback_minutes)
                timeframe_data[TimeFrame.MINUTE_5] = minute_5_data

            # 验证数据对齐
            is_valid, error_msg = self.calculator.validate_data_alignment(timeframe_data)
            if not is_valid:
                logger.warning(f"{symbol}: 时间框架数据对齐失败: {error_msg}")
                return {}

            return timeframe_data

        except Exception as e:
            logger.error(f"{symbol}: 准备时间框架数据失败: {e}")
            return {}

    def _extract_rsi_signals(self, indicators: Dict[str, Dict]) -> Dict[str, float]:
        """从指标中提取RSI信号"""
        rsi_signals = {}

        try:
            # 日线RSI
            if '1d' in indicators and 'rsi' in indicators['1d']:
                rsi_signals['daily'] = indicators['1d']['rsi']

            # 5分钟长周期RSI
            if '5min' in indicators and 'rsi_long' in indicators['5min']:
                rsi_signals['5min_long'] = indicators['5min']['rsi_long']

            # 5分钟短周期RSI
            if '5min' in indicators and 'rsi_short' in indicators['5min']:
                rsi_signals['5min_short'] = indicators['5min']['rsi_short']

            return rsi_signals

        except Exception as e:
            logger.error(f"提取RSI信号失败: {e}")
            return {}

    def _fuse_rsi_signals(self, rsi_signals: Dict[str, float]) -> Tuple[float, float]:
        """融合多时间框架RSI信号

        Returns:
            (融合后的RSI值, 置信度)
        """
        # 检查信号完整性
        required_signals = ['daily', '5min_long', '5min_short']
        available_signals = [s for s in required_signals if s in rsi_signals]

        if len(available_signals) == 0:
            return 50.0, 0.0  # 无信号，返回中性值

        # 根据可用信号调整权重
        weights = {
            'daily': self.weight_daily,
            '5min_long': self.weight_minute_long,
            '5min_short': self.weight_minute_short
        }

        # 重新标准化权重
        total_weight = sum(weights[s] for s in available_signals)
        if total_weight == 0:
            return 50.0, 0.0

        normalized_weights = {s: weights[s] / total_weight for s in available_signals}

        # 加权融合
        fused_rsi = sum(rsi_signals[s] * normalized_weights[s] for s in available_signals)

        # 计算置信度（基于信号完整性和一致性）
        completeness = len(available_signals) / len(required_signals)
        consistency = self._calculate_signal_consistency(rsi_signals)
        confidence = (completeness + consistency) / 2.0

        return fused_rsi, confidence

    def _calculate_signal_consistency(self, rsi_signals: Dict[str, float]) -> float:
        """计算信号一致性

        一致性度量：所有RSI信号是否指向同一方向（超买/超卖/中性）
        """
        if len(rsi_signals) < 2:
            return 0.5

        values = list(rsi_signals.values())

        # 定义区间：超卖(<30)、中性(30-70)、超买(>70)
        def classify_rsi(rsi):
            if rsi < 30:
                return -1  # 超卖
            elif rsi > 70:
                return 1   # 超买
            else:
                return 0   # 中性

        classifications = [classify_rsi(v) for v in values]

        # 计算一致性：所有分类相同得1分，完全不同得0分
        if len(set(classifications)) == 1:
            consistency = 1.0
        else:
            # 部分一致：使用标准差来衡量
            std = np.std(values)
            consistency = max(0.0, 1.0 - std / 50.0)  # RSI标准差越小，一致性越高

        return consistency

    def _normalize_rsi_to_factor(self, rsi_value: float) -> float:
        """将RSI值标准化到因子值[-1, 1]

        RSI超买(>70) -> 正因子值（看跌信号）
        RSI超卖(<30) -> 负因子值（看涨信号）
        RSI中性(50) -> 0
        """
        # RSI从50开始偏离越多，因子值越强
        deviation = (rsi_value - 50.0) / 50.0  # 标准化到[-1, 1]

        # 使用tanh进一步压缩到[-1, 1]，避免极端值
        factor_value = np.tanh(deviation * 2.0)

        return factor_value

    def _create_default_value(self, symbol: str, reason: str = "") -> FactorValue:
        """创建默认因子值（中性）"""
        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=0.0,
            timestamp=datetime.now(),
            confidence=0.0,
            raw_data={'reason': reason},
            metadata={'status': 'default'}
        )

    def _load_dynamic_weights(self):
        """从优化器加载动态权重"""
        default_weights = {
            'daily': self.default_weight_daily,
            '5min_long': self.default_weight_minute_long,
            '5min_short': self.default_weight_minute_short
        }

        # 从优化器获取权重
        weights = self.weight_optimizer.get_weights(self.name, default_weights)

        # 更新当前权重
        self.weight_daily = weights.get('daily', self.default_weight_daily)
        self.weight_minute_long = weights.get('5min_long', self.default_weight_minute_long)
        self.weight_minute_short = weights.get('5min_short', self.default_weight_minute_short)


class MultiTimeframeMACDFactor(BaseFactor):
    """多时间框架MACD因子

    结合日线MACD(12,26,9)和5分钟MACD(60,130,45)
    通过加权融合生成综合MACD信号
    """

    def __init__(self, config: Dict = None):
        super().__init__(
            name="multi_timeframe_macd",
            category="technical",
            description="多时间框架MACD因子：融合日线和5分钟MACD信号"
        )
        self.config = config or {}
        self.dependencies = ["price_daily", "price_5min"]
        self.lookback_days = 30

        # 获取配置参数
        macd_settings = self.config.get('macd_settings', {})
        self.daily_params = macd_settings.get('daily', {'fast': 12, 'slow': 26, 'signal': 9})
        self.minute_5_params = macd_settings.get('minute_5', {'fast': 60, 'slow': 130, 'signal': 45})

        # 信号权重（默认值，从配置文件读取）
        signal_weights = macd_settings.get('signal_weights', {})
        self.default_weight_daily = signal_weights.get('daily', 0.6)
        self.default_weight_minute = signal_weights.get('minute', 0.4)

        # 是否启用背离检测
        self.enable_divergence = macd_settings.get('divergence_detection', True)

        # 初始化计算器和缓存
        self.calculator = MultiTimeframeIndicatorCalculator()
        self.cache = get_cache(self.config.get('cache_settings'))

        # 初始化权重优化器
        self.weight_optimizer = get_timeframe_weight_optimizer()

        # 加载动态权重（如果存在）
        self._load_dynamic_weights()

        logger.info(f"初始化多时间框架MACD因子: 日线参数={self.daily_params}, "
                   f"5分钟参数={self.minute_5_params}, 背离检测={self.enable_divergence}")
        logger.info(f"  当前权重: 日线={self.weight_daily:.3f}, 5分钟={self.weight_minute:.3f}")

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算多时间框架MACD因子值

        Args:
            data: 数据字典，包含 'price_daily' 和 'price_5min'
            symbol: 股票代码
            **kwargs: 额外参数

        Returns:
            FactorValue对象，包含融合后的MACD因子值
        """
        try:
            # 1. 验证数据完整性
            if not self.validate_data(data):
                logger.warning(f"{symbol}: 数据验证失败")
                return self._create_default_value(symbol, reason="数据验证失败")

            # 2. 准备多时间框架数据
            timeframe_data = self._prepare_timeframe_data(data, symbol)
            if not timeframe_data:
                return self._create_default_value(symbol, reason="时间框架数据准备失败")

            # 3. 计算各时间框架的MACD指标
            indicators = self.calculator.calculate_indicators_with_timeframes(timeframe_data)

            # 4. 提取MACD信号
            macd_signals = self._extract_macd_signals(indicators)
            if not macd_signals:
                return self._create_default_value(symbol, reason="MACD信号提取失败")

            # 5. 检测背离（可选）
            divergence_signal = 0.0
            if self.enable_divergence:
                divergence_signal = self._detect_divergence(timeframe_data, macd_signals)

            # 6. 融合多时间框架信号
            fused_value, confidence = self._fuse_macd_signals(macd_signals, divergence_signal)

            # 7. 计算因子值（标准化到[-1, 1]）
            factor_value = self._normalize_macd_to_factor(fused_value)

            # 8. 构建返回结果
            return FactorValue(
                symbol=symbol,
                factor_name=self.name,
                value=factor_value,
                timestamp=datetime.now(),
                confidence=confidence,
                raw_data={
                    'macd_daily': macd_signals.get('daily'),
                    'macd_5min': macd_signals.get('5min'),
                    'fused_macd': fused_value,
                    'divergence_signal': divergence_signal,
                    'weights': {
                        'daily': self.weight_daily,
                        'minute': self.weight_minute
                    }
                },
                metadata={
                    'timeframes': list(timeframe_data.keys()),
                    'signal_consistency': self._calculate_signal_consistency(macd_signals),
                    'has_divergence': divergence_signal != 0.0
                }
            )

        except Exception as e:
            logger.error(f"{symbol}: 多时间框架MACD因子计算失败: {e}", exc_info=True)
            return self._create_default_value(symbol, reason=f"计算异常: {str(e)}")

    def _prepare_timeframe_data(self, data: Dict[str, pd.DataFrame], symbol: str) -> Dict[TimeFrame, pd.DataFrame]:
        """准备多时间框架数据（同RSI因子）"""
        timeframe_data = {}

        try:
            # 日线数据
            if 'price_daily' in data and not data['price_daily'].empty:
                daily_data = data['price_daily'].tail(self.lookback_days * 2)
                timeframe_data[TimeFrame.DAILY] = daily_data

            # 5分钟数据
            if 'price_5min' in data and not data['price_5min'].empty:
                lookback_minutes = self.lookback_days * 48
                minute_5_data = data['price_5min'].tail(lookback_minutes)
                timeframe_data[TimeFrame.MINUTE_5] = minute_5_data

            # 验证数据对齐
            is_valid, error_msg = self.calculator.validate_data_alignment(timeframe_data)
            if not is_valid:
                logger.warning(f"{symbol}: 时间框架数据对齐失败: {error_msg}")
                return {}

            return timeframe_data

        except Exception as e:
            logger.error(f"{symbol}: 准备时间框架数据失败: {e}")
            return {}

    def _extract_macd_signals(self, indicators: Dict[str, Dict]) -> Dict[str, Dict]:
        """从指标中提取MACD信号"""
        macd_signals = {}

        try:
            # 日线MACD
            if '1d' in indicators:
                daily_ind = indicators['1d']
                if 'macd' in daily_ind and 'macd_signal' in daily_ind and 'macd_histogram' in daily_ind:
                    macd_signals['daily'] = {
                        'macd': daily_ind['macd'],
                        'signal': daily_ind['macd_signal'],
                        'histogram': daily_ind['macd_histogram']
                    }

            # 5分钟MACD（使用长周期版本）
            if '5min' in indicators:
                minute_ind = indicators['5min']
                if 'macd_long' in minute_ind:
                    macd_signals['5min'] = {
                        'macd': minute_ind.get('macd_long', 0),
                        'signal': minute_ind.get('macd_signal_long', 0),
                        'histogram': minute_ind.get('macd_histogram_long', 0)
                    }
                elif 'macd' in minute_ind:  # 回退到标准MACD
                    macd_signals['5min'] = {
                        'macd': minute_ind['macd'],
                        'signal': minute_ind.get('macd_signal', 0),
                        'histogram': minute_ind.get('macd_histogram', 0)
                    }

            return macd_signals

        except Exception as e:
            logger.error(f"提取MACD信号失败: {e}")
            return {}

    def _fuse_macd_signals(self, macd_signals: Dict[str, Dict], divergence_signal: float) -> Tuple[float, float]:
        """融合多时间框架MACD信号

        Returns:
            (融合后的MACD柱状图值, 置信度)
        """
        # 检查信号完整性
        available_signals = [tf for tf in ['daily', '5min'] if tf in macd_signals]

        if len(available_signals) == 0:
            return 0.0, 0.0

        # 根据可用信号调整权重
        weights = {
            'daily': self.weight_daily,
            '5min': self.weight_minute
        }

        # 重新标准化权重
        total_weight = sum(weights[tf] for tf in available_signals)
        if total_weight == 0:
            return 0.0, 0.0

        normalized_weights = {tf: weights[tf] / total_weight for tf in available_signals}

        # 加权融合MACD柱状图（主要信号）
        fused_histogram = sum(
            macd_signals[tf]['histogram'] * normalized_weights[tf]
            for tf in available_signals
        )

        # 考虑背离信号（如果存在）
        if divergence_signal != 0.0:
            # 背离信号可以增强或减弱MACD信号
            fused_histogram = fused_histogram * (1.0 + divergence_signal * 0.3)

        # 计算置信度
        completeness = len(available_signals) / 2.0  # 最多2个时间框架
        consistency = self._calculate_signal_consistency(macd_signals)
        divergence_confidence = abs(divergence_signal) * 0.2 if self.enable_divergence else 0.0

        confidence = min(1.0, (completeness + consistency + divergence_confidence) / 2.0)

        return fused_histogram, confidence

    def _calculate_signal_consistency(self, macd_signals: Dict[str, Dict]) -> float:
        """计算MACD信号一致性

        一致性度量：所有时间框架的MACD柱状图是否同向
        """
        if len(macd_signals) < 2:
            return 0.5

        histograms = [macd_signals[tf]['histogram'] for tf in macd_signals]

        # 检查符号是否一致
        signs = [1 if h > 0 else -1 if h < 0 else 0 for h in histograms]

        if len(set(signs)) == 1 and signs[0] != 0:
            # 完全一致且有明确方向
            consistency = 1.0
        else:
            # 部分一致或方向不明
            consistency = 0.3

        return consistency

    def _detect_divergence(self, timeframe_data: Dict[TimeFrame, pd.DataFrame], macd_signals: Dict[str, Dict]) -> float:
        """检测MACD背离信号

        背离类型：
        - 底背离（看涨）：价格创新低，MACD不创新低
        - 顶背离（看跌）：价格创新高，MACD不创新高

        Returns:
            背离信号强度：-1到1，负值为底背离（看涨），正值为顶背离（看跌）
        """
        try:
            # 仅使用日线数据检测背离
            if TimeFrame.DAILY not in timeframe_data or 'daily' not in macd_signals:
                return 0.0

            daily_data = timeframe_data[TimeFrame.DAILY].tail(20)  # 使用最近20天数据
            if len(daily_data) < 10:
                return 0.0

            closes = daily_data['Close'].values
            macd_hist = []

            # 需要历史MACD柱状图数据，这里简化处理
            # 实际应该从完整的MACD计算中获取历史序列
            current_hist = macd_signals['daily']['histogram']

            # 简化的背离检测：比较最近价格和MACD的趋势
            recent_price_trend = (closes[-1] - closes[-5]) / closes[-5] if len(closes) >= 5 else 0

            # MACD趋势：当前柱状图的符号
            macd_trend = 1.0 if current_hist > 0 else -1.0 if current_hist < 0 else 0.0

            # 背离检测：价格和MACD趋势相反
            if recent_price_trend > 0.02 and macd_trend < 0:
                # 价格上涨但MACD下降 -> 顶背离（看跌）
                divergence = 0.5
            elif recent_price_trend < -0.02 and macd_trend > 0:
                # 价格下跌但MACD上升 -> 底背离（看涨）
                divergence = -0.5
            else:
                divergence = 0.0

            return divergence

        except Exception as e:
            logger.error(f"背离检测失败: {e}")
            return 0.0

    def _normalize_macd_to_factor(self, macd_histogram: float) -> float:
        """将MACD柱状图值标准化到因子值[-1, 1]

        MACD柱状图为正 -> 正因子值（看涨）
        MACD柱状图为负 -> 负因子值（看跌）
        """
        # 使用tanh压缩到[-1, 1]，避免极端值
        # 根据经验，MACD柱状图通常在-1到1之间，所以放大10倍后压缩
        factor_value = np.tanh(macd_histogram * 10.0)

        return factor_value

    def _create_default_value(self, symbol: str, reason: str = "") -> FactorValue:
        """创建默认因子值（中性）"""
        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=0.0,
            timestamp=datetime.now(),
            confidence=0.0,
            raw_data={'reason': reason},
            metadata={'status': 'default'}
        )

    def _load_dynamic_weights(self):
        """从优化器加载动态权重"""
        default_weights = {
            'daily': self.default_weight_daily,
            '5min': self.default_weight_minute
        }

        # 从优化器获取权重
        weights = self.weight_optimizer.get_weights(self.name, default_weights)

        # 更新当前权重
        self.weight_daily = weights.get('daily', self.default_weight_daily)
        self.weight_minute = weights.get('5min', self.default_weight_minute)


# 便捷函数
def create_multi_timeframe_rsi_factor(config: Dict = None) -> MultiTimeframeRSIFactor:
    """创建多时间框架RSI因子实例"""
    return MultiTimeframeRSIFactor(config)


def create_multi_timeframe_macd_factor(config: Dict = None) -> MultiTimeframeMACDFactor:
    """创建多时间框架MACD因子实例"""
    return MultiTimeframeMACDFactor(config)
