# -*- coding: utf-8 -*-
"""
多时间框架技术指标计算器
支持日线和分钟级别的技术指标计算，并提供时间框架参数转换
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime

try:
    from ..interfaces import TimeFrame, StockInfo
    from .technical_indicators import TechnicalIndicatorCalculator
except ImportError:
    from data.interfaces import TimeFrame, StockInfo
    from data.indicators.technical_indicators import TechnicalIndicatorCalculator

logger = logging.getLogger(__name__)


class MultiTimeframeIndicatorCalculator:
    """多时间框架技术指标计算器"""

    # 时间框架转换比例 (一个交易日 ≈ 48个5分钟K线)
    TIMEFRAME_CONVERSION = {
        TimeFrame.MINUTE_5: 48,  # 1天 = 48个5分钟K线
        TimeFrame.MINUTE_15: 16,  # 1天 = 16个15分钟K线
        TimeFrame.MINUTE_30: 8,   # 1天 = 8个30分钟K线
        TimeFrame.HOUR_1: 4,      # 1天 = 4个1小时K线
    }

    # 参数缩放系数 (经验值，不完全按比例)
    SCALE_FACTOR = 0.15  # 使用15%的比例进行缩放

    def __init__(self):
        self.base_calculator = TechnicalIndicatorCalculator()

    def calculate_indicators_with_timeframes(
        self,
        data_dict: Dict[TimeFrame, pd.DataFrame],
        stock_info: StockInfo = None
    ) -> Dict[str, Dict]:
        """
        计算多时间框架的技术指标

        Args:
            data_dict: 时间框架到数据的映射 {TimeFrame.DAILY: df1, TimeFrame.MINUTE_5: df2}
            stock_info: 股票信息

        Returns:
            多时间框架指标字典 {
                'daily': {'rsi': 55, 'macd': 0.5, ...},
                '5min': {'rsi': 52, 'macd': 0.3, ...}
            }
        """
        result = {}

        for timeframe, data in data_dict.items():
            if data.empty:
                logger.warning(f"时间框架 {timeframe.value} 数据为空，跳过")
                continue

            try:
                # 计算该时间框架的所有指标
                indicators = self._calculate_indicators_for_timeframe(
                    data, timeframe, stock_info
                )

                # 使用时间框架的value作为key (如 "1d", "5min")
                result[timeframe.value] = indicators

                logger.debug(f"时间框架 {timeframe.value} 指标计算完成: {len(indicators)} 个指标")

            except Exception as e:
                logger.error(f"计算时间框架 {timeframe.value} 指标失败: {e}")
                result[timeframe.value] = {}

        return result

    def _calculate_indicators_for_timeframe(
        self,
        data: pd.DataFrame,
        timeframe: TimeFrame,
        stock_info: StockInfo = None
    ) -> Dict:
        """计算单个时间框架的指标"""

        # 使用基础计算器计算标准指标
        indicators = self.base_calculator.calculate_indicators(data, stock_info)

        # 添加多时间框架特定的指标
        if timeframe == TimeFrame.DAILY:
            # 日线指标保持标准参数
            pass
        elif timeframe in self.TIMEFRAME_CONVERSION:
            # 分钟级指标：添加长周期和短周期版本
            indicators.update(self._calculate_multi_period_indicators(data, timeframe))

        return indicators

    def _calculate_multi_period_indicators(
        self,
        data: pd.DataFrame,
        timeframe: TimeFrame
    ) -> Dict:
        """计算分钟级数据的多周期指标"""
        indicators = {}

        try:
            # RSI多周期
            rsi_indicators = self._calculate_rsi_multi_period(data, timeframe)
            indicators.update(rsi_indicators)

            # MACD多周期
            macd_indicators = self._calculate_macd_multi_period(data, timeframe)
            indicators.update(macd_indicators)

        except Exception as e:
            logger.error(f"计算多周期指标失败: {e}")

        return indicators

    def _calculate_rsi_multi_period(
        self,
        data: pd.DataFrame,
        timeframe: TimeFrame
    ) -> Dict:
        """
        计算RSI的多周期版本

        对于5分钟数据:
        - 长周期: 70 (约14天)
        - 短周期: 14 (约3小时)
        """
        indicators = {}

        if len(data) < 20:
            return indicators

        closes = data['Close']

        try:
            # 长周期RSI (约等于日线14天)
            long_period = self._convert_period_to_minutes(14, timeframe)
            if len(closes) >= long_period:
                rsi_long = self._calculate_rsi(closes, long_period)
                indicators['rsi_long'] = rsi_long

            # 短周期RSI (快速反应)
            short_period = 14  # 固定短周期
            if len(closes) >= short_period:
                rsi_short = self._calculate_rsi(closes, short_period)
                indicators['rsi_short'] = rsi_short

        except Exception as e:
            logger.error(f"计算RSI多周期失败: {e}")

        return indicators

    def _calculate_macd_multi_period(
        self,
        data: pd.DataFrame,
        timeframe: TimeFrame
    ) -> Dict:
        """
        计算MACD的多周期版本

        对于5分钟数据:
        - 长周期: (60, 130, 45) - 约对应日线(12, 26, 9)
        - 短周期: (12, 26, 9) - 快速反应
        """
        indicators = {}

        if len(data) < 30:
            return indicators

        closes = data['Close']

        try:
            # 长周期MACD (约等于日线参数)
            long_fast = self._convert_period_to_minutes(12, timeframe)
            long_slow = self._convert_period_to_minutes(26, timeframe)
            long_signal = self._convert_period_to_minutes(9, timeframe)

            if len(closes) >= long_slow:
                macd_long = self._calculate_macd(
                    closes, long_fast, long_slow, long_signal
                )
                indicators['macd_long'] = macd_long['macd']
                indicators['macd_signal_long'] = macd_long['macd_signal']
                indicators['macd_histogram_long'] = macd_long['macd_histogram']

            # 短周期MACD (快速反应)
            if len(closes) >= 26:
                macd_short = self._calculate_macd(closes, 12, 26, 9)
                indicators['macd_short'] = macd_short['macd']
                indicators['macd_signal_short'] = macd_short['macd_signal']
                indicators['macd_histogram_short'] = macd_short['macd_histogram']

        except Exception as e:
            logger.error(f"计算MACD多周期失败: {e}")

        return indicators

    def _convert_period_to_minutes(
        self,
        daily_period: int,
        target_timeframe: TimeFrame
    ) -> int:
        """
        将日线周期参数转换为分钟级周期

        Args:
            daily_period: 日线周期（如14天）
            target_timeframe: 目标时间框架

        Returns:
            转换后的周期
        """
        if target_timeframe not in self.TIMEFRAME_CONVERSION:
            return daily_period

        # 计算理论转换值
        conversion_ratio = self.TIMEFRAME_CONVERSION[target_timeframe]
        theoretical_period = daily_period * conversion_ratio

        # 应用缩放系数
        scaled_period = int(theoretical_period * self.SCALE_FACTOR)

        # 确保最小值
        min_period = max(10, daily_period)

        return max(scaled_period, min_period)

    def _calculate_rsi(self, close_prices: pd.Series, period: int = 14) -> float:
        """计算RSI指标"""
        try:
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            return rsi.iloc[-1] if not rsi.empty else 50.0
        except Exception as e:
            logger.error(f"RSI计算失败: {e}")
            return 50.0

    def _calculate_macd(
        self,
        close_prices: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict:
        """计算MACD指标"""
        try:
            ema_fast = close_prices.ewm(span=fast, adjust=False).mean()
            ema_slow = close_prices.ewm(span=slow, adjust=False).mean()

            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()
            histogram = macd_line - signal_line

            return {
                'macd': macd_line.iloc[-1],
                'macd_signal': signal_line.iloc[-1],
                'macd_histogram': histogram.iloc[-1]
            }
        except Exception as e:
            logger.error(f"MACD计算失败: {e}")
            return {'macd': 0, 'macd_signal': 0, 'macd_histogram': 0}

    def sync_timeframe_parameters(
        self,
        base_params: Dict,
        source_timeframe: TimeFrame,
        target_timeframe: TimeFrame
    ) -> Dict:
        """
        同步时间框架参数

        Args:
            base_params: 基础参数 {'rsi_period': 14, 'macd_fast': 12, ...}
            source_timeframe: 源时间框架 (如 TimeFrame.DAILY)
            target_timeframe: 目标时间框架 (如 TimeFrame.MINUTE_5)

        Returns:
            转换后的参数字典
        """
        if source_timeframe == target_timeframe:
            return base_params.copy()

        converted_params = {}

        for key, value in base_params.items():
            if isinstance(value, int) and 'period' in key.lower():
                # 周期参数需要转换
                converted_params[key] = self._convert_period_to_minutes(
                    value, target_timeframe
                )
            else:
                # 其他参数保持不变
                converted_params[key] = value

        return converted_params

    def get_supported_timeframes(self) -> List[TimeFrame]:
        """获取支持的时间框架列表"""
        return [
            TimeFrame.DAILY,
            TimeFrame.MINUTE_5,
            TimeFrame.MINUTE_15,
            TimeFrame.MINUTE_30,
            TimeFrame.HOUR_1
        ]

    def validate_data_alignment(
        self,
        data_dict: Dict[TimeFrame, pd.DataFrame]
    ) -> Tuple[bool, str]:
        """
        验证多时间框架数据的对齐性

        Returns:
            (是否对齐, 错误消息)
        """
        if not data_dict:
            return False, "数据字典为空"

        for timeframe, data in data_dict.items():
            if data.empty:
                return False, f"时间框架 {timeframe.value} 数据为空"

            # 检查必需列
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing_columns = [col for col in required_columns if col not in data.columns]

            if missing_columns:
                return False, f"时间框架 {timeframe.value} 缺少列: {missing_columns}"

            # 检查数据量
            min_data_points = {
                TimeFrame.DAILY: 30,
                TimeFrame.MINUTE_5: 50,
                TimeFrame.MINUTE_15: 30,
                TimeFrame.MINUTE_30: 20,
                TimeFrame.HOUR_1: 20
            }

            min_required = min_data_points.get(timeframe, 20)
            if len(data) < min_required:
                return False, f"时间框架 {timeframe.value} 数据不足: {len(data)} < {min_required}"

        return True, ""


# 便捷函数
def create_multi_timeframe_calculator() -> MultiTimeframeIndicatorCalculator:
    """创建多时间框架指标计算器实例"""
    return MultiTimeframeIndicatorCalculator()
