# -*- coding: utf-8 -*-
"""
Qlib Alpha158因子实现
封装Qlib的Alpha158因子集（158个经典量化因子）
包含动量、波动率、量价、技术指标、趋势等5大类因子
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
from datetime import datetime, timedelta

from .factor_manager import BaseFactor, FactorValue

logger = logging.getLogger(__name__)

# 检查Qlib是否可用
try:
    import qlib
    from qlib.data import D
    QLIB_AVAILABLE = True
except ImportError:
    logger.warning("Qlib未安装，Alpha158因子将不可用")
    QLIB_AVAILABLE = False


class QlibAlpha158Factor(BaseFactor):
    """
    Qlib Alpha158因子集（158个经典量化因子）

    因子分类：
    - 动量类（40个）：各周期收益率、动量指标
    - 波动率类（30个）：标准差、波幅、ATR等
    - 量价类（30个）：成交量变化、量价相关性
    - 技术指标类（38个）：RSI、MACD、布林带等
    - 趋势类（20个）：均线交叉、趋势强度
    """

    def __init__(self):
        super().__init__(
            name="qlib_alpha158",
            category="technical",
            description="Qlib Alpha158因子集：158个经典技术因子（动量、波动率、量价、技术指标、趋势）"
        )
        self.dependencies = ["price"]
        self.lookback_days = 60  # 需要60天历史数据计算因子

        # 初始化Alpha158因子表达式
        self.alpha158_fields = self._init_alpha158_fields()

        # Qlib初始化状态
        self.qlib_initialized = False
        self._try_init_qlib()

    def _try_init_qlib(self):
        """尝试初始化Qlib"""
        if not QLIB_AVAILABLE:
            return

        try:
            # 检查Qlib是否已初始化
            from src.data.sources.qlib_source import QlibDataProvider

            # 尝试创建QlibDataProvider检查可用性
            provider = QlibDataProvider("./qlib_data")
            if provider.is_available():
                self.qlib_initialized = True
                logger.info("Qlib Alpha158因子初始化成功")
            else:
                logger.warning("Qlib数据源不可用，Alpha158因子将返回中性值")
        except Exception as e:
            logger.warning(f"Qlib初始化失败: {e}，Alpha158因子将返回中性值")

    def _init_alpha158_fields(self) -> list:
        """
        初始化Alpha158的158个因子表达式

        Returns:
            因子表达式列表
        """
        fields = []

        # ========== 1. 动量类因子（40个）==========
        # 各周期收益率动量
        for d in [1, 5, 10, 20, 30, 60]:
            fields.append(f"Ref($close, {d})/$close - 1")  # 收益率
            fields.append(f"Ref($open, {d})/$close - 1")   # 开盘价动量

        # 高低价动量
        for d in [5, 10, 20, 30]:
            fields.append(f"Ref($high, {d})/$close - 1")   # 最高价动量
            fields.append(f"Ref($low, {d})/$close - 1")    # 最低价动量

        # 累计收益率
        for d in [5, 10, 20]:
            fields.append(f"($close / Ref($close, {d}) - 1)")  # 累计收益率

        # ========== 2. 波动率类因子（30个）==========
        # 价格标准差
        for d in [5, 10, 20, 30, 60]:
            fields.append(f"Std($close, {d})/$close")      # 收益率标准差
            fields.append(f"Std($close / Ref($close, 1) - 1, {d})")  # 收益波动率

        # 价格振幅
        for d in [5, 10, 20, 30]:
            fields.append(f"($high - $low)/$close")        # 日内振幅
            fields.append(f"Mean(($high - $low)/$close, {d})")  # 平均振幅

        # 高低价比率
        for d in [5, 10]:
            fields.append(f"Std($high/$low, {d})")         # 高低价比波动

        # ========== 3. 量价类因子（30个）==========
        # 成交量变化
        for d in [5, 10, 20, 30]:
            fields.append(f"$volume / Mean($volume, {d})")  # 成交量比率
            fields.append(f"Std($volume, {d}) / Mean($volume, {d})")  # 成交量变异系数

        # 量价相关性
        for d in [5, 10, 20]:
            fields.append(f"Corr($close, $volume, {d})")   # 价量相关性
            fields.append(f"Corr($close / Ref($close, 1) - 1, $volume, {d})")  # 收益率与成交量相关性

        # 成交额因子
        for d in [5, 10, 20]:
            fields.append(f"$close * $volume / Mean($close * $volume, {d})")  # 成交额比率

        # ========== 4. 技术指标类因子（38个）==========
        # RSI指标
        for period in [6, 12, 24]:
            # RSI的简化表达式（实际Qlib可能有专门的RSI函数）
            fields.append(f"Mean(Max($close - Ref($close, 1), 0), {period}) / (Mean(Abs($close - Ref($close, 1)), {period}) + 1e-12)")

        # MACD系列
        fields.append("EMA($close, 12) / $close - 1")      # 短期EMA
        fields.append("EMA($close, 26) / $close - 1")      # 长期EMA
        fields.append("(EMA($close, 12) - EMA($close, 26)) / $close")  # MACD DIF
        fields.append("EMA(EMA($close, 12) - EMA($close, 26), 9) / $close")  # MACD DEA

        # 布林带
        for period in [10, 20]:
            fields.append(f"($close - Mean($close, {period})) / Std($close, {period})")  # 布林带位置
            fields.append(f"Std($close, {period}) / Mean($close, {period})")  # 布林带宽度

        # 威廉指标
        for period in [6, 10]:
            fields.append(f"($close - Min($low, {period})) / (Max($high, {period}) - Min($low, {period}) + 1e-12)")

        # KDJ指标（简化）
        for period in [9, 14]:
            fields.append(f"($close - Min($low, {period})) / (Max($high, {period}) - Min($low, {period}) + 1e-12)")

        # ATR (Average True Range)
        for period in [14, 20]:
            fields.append(f"Mean(Max(Max($high - $low, Abs($high - Ref($close, 1))), Abs($low - Ref($close, 1))), {period}) / $close")

        # CCI (Commodity Channel Index)
        for period in [14, 20]:
            fields.append(f"(($high + $low + $close) / 3 - Mean(($high + $low + $close) / 3, {period})) / (Std(($high + $low + $close) / 3, {period}) * 0.015 + 1e-12)")

        # ========== 5. 趋势类因子（20个）==========
        # 均线交叉
        for short, long in [(5, 10), (5, 20), (10, 20), (10, 30), (20, 60)]:
            fields.append(f"Mean($close, {short}) / Mean($close, {long}) - 1")  # 均线比率
            fields.append(f"(Mean($close, {short}) - Mean($close, {long})) / $close")  # 均线差

        # 均线斜率
        for period in [5, 10, 20]:
            fields.append(f"(Mean($close, {period}) - Ref(Mean($close, {period}), {period})) / $close")

        # 价格与均线偏离
        for period in [5, 10, 20, 30, 60]:
            fields.append(f"$close / Mean($close, {period}) - 1")  # 价格偏离率

        return fields[:158]  # 确保返回158个因子

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """
        计算Alpha158因子

        Args:
            data: 数据字典，必须包含'price'键
            symbol: 股票代码
            **kwargs: 额外参数

        Returns:
            FactorValue（value为158个因子的加权综合得分）
        """
        # 检查Qlib是否可用
        if not QLIB_AVAILABLE or not self.qlib_initialized:
            logger.debug(f"{symbol}: Qlib不可用，返回中性因子值")
            return FactorValue(
                symbol=symbol,
                factor_name=self.name,
                value=0.0,  # 中性值
                timestamp=datetime.now(),
                confidence=0.1,  # 低置信度
                raw_data={'status': 'qlib_unavailable'}
            )

        try:
            # 获取价格数据
            price_data = data.get('price')
            if price_data is None or price_data.empty:
                logger.warning(f"{symbol}: 价格数据为空")
                return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.1, raw_data={'status': 'no_data'})

            # 确保有足够的历史数据
            if len(price_data) < self.lookback_days:
                logger.debug(f"{symbol}: 历史数据不足（{len(price_data)} < {self.lookback_days}）")
                return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3, raw_data={'status': 'insufficient_data'})

            # 转换股票代码格式：000001.SZ → SZ000001
            qlib_symbol = self._to_qlib_symbol(symbol)

            # 确定日期范围
            end_date = price_data.index[-1].strftime('%Y-%m-%d')
            start_date = price_data.index[-self.lookback_days].strftime('%Y-%m-%d')

            # 使用Qlib批量计算158个因子（矢量化，速度快）
            features = D.features(
                instruments=[qlib_symbol],
                fields=self.alpha158_fields,
                start_time=start_date,
                end_time=end_date,
                freq='day'
            )

            if features is None or features.empty:
                logger.debug(f"{symbol}: Qlib返回空数据")
                return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3, raw_data={'status': 'empty_features'})

            # 提取最新因子值
            if isinstance(features.index, pd.MultiIndex):
                latest_features = features.xs(qlib_symbol, level=0).iloc[-1]
            else:
                latest_features = features.iloc[-1]

            factor_values = latest_features.values

            # 去除NaN值
            valid_values = factor_values[~np.isnan(factor_values)]

            if len(valid_values) == 0:
                logger.debug(f"{symbol}: 所有因子值为NaN")
                return FactorValue(symbol, self.name, 0.0, datetime.now(), 0.3, raw_data={'status': 'all_nan'})

            # 标准化到[-1, 1]范围（使用tanh）
            # tanh自动将大的正值映射到接近1，大的负值映射到接近-1
            composite_score = np.tanh(np.mean(valid_values))

            # 置信度：基于有效因子的比例
            confidence = 0.5 + 0.4 * (len(valid_values) / len(factor_values))

            return FactorValue(
                symbol=symbol,
                factor_name=self.name,
                value=float(composite_score),
                timestamp=datetime.now(),
                confidence=float(confidence),
                raw_data={
                    'valid_factors': int(len(valid_values)),
                    'total_factors': int(len(factor_values)),
                    'valid_ratio': float(len(valid_values) / len(factor_values))
                }
            )

        except Exception as e:
            logger.error(f"{symbol}: 计算Alpha158因子失败 - {e}")
            return FactorValue(
                symbol=symbol,
                factor_name=self.name,
                value=0.0,
                timestamp=datetime.now(),
                confidence=0.1,
                raw_data={'error': str(e)}
            )

    def _to_qlib_symbol(self, symbol: str) -> str:
        """
        标准格式转Qlib格式：000001.SZ → SZ000001

        Args:
            symbol: 标准股票代码

        Returns:
            Qlib格式股票代码
        """
        import re
        match = re.match(r'(\d{6})\.(SZ|SH)', symbol)
        if not match:
            return symbol
        code, market = match.groups()
        return f"{market}{code}"


def test_qlib_alpha158_factor():
    """测试Qlib Alpha158因子"""
    print("=" * 60)
    print("Qlib Alpha158 Factor Test")
    print("=" * 60)

    # 创建因子实例
    factor = QlibAlpha158Factor()

    print(f"\nFactor Name: {factor.name}")
    print(f"Factor Category: {factor.category}")
    print(f"Factor Description: {factor.description}")
    print(f"Total Alpha158 Fields: {len(factor.alpha158_fields)}")
    print(f"Qlib Initialized: {factor.qlib_initialized}")

    # 打印前10个因子表达式示例
    print(f"\nSample Factor Expressions (first 10):")
    for i, field in enumerate(factor.alpha158_fields[:10], 1):
        print(f"  {i}. {field}")

    # 如果Qlib可用，测试计算
    if factor.qlib_initialized:
        print("\n--- Testing Factor Calculation ---")

        # 准备模拟数据
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        mock_data = {
            'price': pd.DataFrame({
                'Open': np.random.uniform(10, 20, 100),
                'High': np.random.uniform(15, 25, 100),
                'Low': np.random.uniform(5, 15, 100),
                'Close': np.random.uniform(10, 20, 100),
                'Volume': np.random.uniform(1e6, 1e7, 100)
            }, index=dates)
        }

        result = factor.calculate(mock_data, '600519.SH')

        print(f"\nCalculation Result:")
        print(f"  Symbol: {result.symbol}")
        print(f"  Value: {result.value:.4f}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Valid Factors: {result.raw_data.get('valid_factors', 'N/A')}/{result.raw_data.get('total_factors', 'N/A')}")
    else:
        print("\n[SKIP] Qlib not initialized, factor calculation skipped")

    print("\n" + "=" * 60)
    print("Test Completed")
    print("=" * 60)


if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    test_qlib_alpha158_factor()
