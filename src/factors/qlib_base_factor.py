# -*- coding: utf-8 -*-
"""
Qlib因子基类
为所有拆分后的Qlib表达式因子提供统一的基类实现
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
from datetime import datetime
import re

from .factor_manager import BaseFactor, FactorValue

logger = logging.getLogger(__name__)

# 检查Qlib是否可用
try:
    import qlib
    from qlib.data import D
    QLIB_AVAILABLE = True
except ImportError:
    logger.warning("Qlib未安装，Qlib因子将不可用")
    QLIB_AVAILABLE = False


class QlibBaseFactor(BaseFactor):
    """
    Qlib因子基类

    为所有基于Qlib表达式的因子提供统一实现：
    - 封装Qlib初始化逻辑
    - 标准化表达式计算流程
    - 自动错误处理和降级
    - 输出标准化到[-1, 1]范围
    """

    def __init__(self, name: str, qlib_expression: str, description: str, category: str = "technical"):
        """
        初始化Qlib因子

        Args:
            name: 因子名称（建议格式：qlib_{category}_{descriptor}）
            qlib_expression: Qlib表达式字符串
            description: 因子描述
            category: 因子类别（默认为technical）
        """
        super().__init__(name, category, description)
        self.qlib_expression = qlib_expression
        self.dependencies = ["price"]
        self.lookback_days = 60  # Qlib因子需要60天历史数据

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
                logger.debug(f"Qlib因子 {self.name} 初始化成功")
            else:
                logger.debug(f"Qlib数据源不可用，因子 {self.name} 将返回中性值")
        except Exception as e:
            logger.debug(f"Qlib初始化失败 ({self.name}): {e}")

    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """
        计算Qlib因子

        Args:
            data: 数据字典，必须包含'price'键
            symbol: 股票代码
            **kwargs: 额外参数

        Returns:
            FactorValue（value标准化到[-1, 1]范围）
        """
        # 检查Qlib是否可用
        if not QLIB_AVAILABLE or not self.qlib_initialized:
            return self._create_neutral_result(symbol, "qlib_unavailable")

        try:
            # 获取价格数据
            price_data = data.get('price')
            if price_data is None or price_data.empty:
                return self._create_neutral_result(symbol, "no_data")

            # 确保有足够的历史数据
            if len(price_data) < self.lookback_days:
                return self._create_neutral_result(symbol, "insufficient_data", confidence=0.3)

            # 转换股票代码格式：000001.SZ → SZ000001
            qlib_symbol = self._to_qlib_symbol(symbol)

            # 确定日期范围
            end_date = price_data.index[-1].strftime('%Y-%m-%d')
            start_date = price_data.index[-self.lookback_days].strftime('%Y-%m-%d')

            # 使用Qlib计算单个表达式
            features = D.features(
                instruments=[qlib_symbol],
                fields=[self.qlib_expression],
                start_time=start_date,
                end_time=end_date,
                freq='day'
            )

            if features is None or features.empty:
                return self._create_neutral_result(symbol, "empty_features", confidence=0.3)

            # 提取最新因子值
            if isinstance(features.index, pd.MultiIndex):
                latest_value = features.xs(qlib_symbol, level=0).iloc[-1, 0]
            else:
                latest_value = features.iloc[-1, 0]

            # 处理NaN值
            if pd.isna(latest_value):
                return self._create_neutral_result(symbol, "nan_value", confidence=0.3)

            # 标准化到[-1, 1]范围（使用tanh）
            normalized_value = np.tanh(latest_value)

            # 置信度：基于数据质量
            confidence = self._calculate_confidence(features, qlib_symbol)

            return FactorValue(
                symbol=symbol,
                factor_name=self.name,
                value=float(normalized_value),
                timestamp=datetime.now(),
                confidence=float(confidence),
                raw_data={
                    'qlib_expression': self.qlib_expression,
                    'raw_value': float(latest_value),
                    'normalized_value': float(normalized_value)
                }
            )

        except Exception as e:
            logger.error(f"{symbol}: 计算Qlib因子 {self.name} 失败 - {e}")
            return self._create_neutral_result(symbol, f"error: {str(e)}", confidence=0.1)

    def _calculate_confidence(self, features: pd.DataFrame, qlib_symbol: str) -> float:
        """
        计算因子置信度

        Args:
            features: Qlib返回的特征数据
            qlib_symbol: Qlib格式股票代码

        Returns:
            置信度 [0.1, 0.9]
        """
        try:
            # 提取该股票的数据
            if isinstance(features.index, pd.MultiIndex):
                stock_data = features.xs(qlib_symbol, level=0)
            else:
                stock_data = features

            # 计算非NaN值的比例
            valid_ratio = stock_data.notna().sum().iloc[0] / len(stock_data) if len(stock_data) > 0 else 0

            # 基础置信度：0.5
            # 根据有效数据比例调整：+0.4 * valid_ratio
            confidence = 0.5 + 0.4 * valid_ratio

            return min(0.9, max(0.1, confidence))
        except Exception as e:
            logger.debug(f"计算置信度失败: {e}")
            return 0.5

    def _create_neutral_result(self, symbol: str, status: str, confidence: float = 0.1) -> FactorValue:
        """
        创建中性结果（降级模式）

        Args:
            symbol: 股票代码
            status: 状态描述
            confidence: 置信度

        Returns:
            中性FactorValue
        """
        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            value=0.0,  # 中性值
            timestamp=datetime.now(),
            confidence=confidence,
            raw_data={'status': status}
        )

    def _to_qlib_symbol(self, symbol: str) -> str:
        """
        标准格式转Qlib格式：000001.SZ → SZ000001

        Args:
            symbol: 标准股票代码

        Returns:
            Qlib格式股票代码
        """
        match = re.match(r'(\d{6})\.(SZ|SH)', symbol)
        if not match:
            return symbol
        code, market = match.groups()
        return f"{market}{code}"


# 测试函数
def test_qlib_base_factor():
    """测试QlibBaseFactor基类"""
    print("=" * 60)
    print("QlibBaseFactor Test")
    print("=" * 60)

    # 创建测试因子（1日动量）
    test_factor = QlibBaseFactor(
        name="qlib_test_momentum_1d",
        qlib_expression="Ref($close, 1)/$close - 1",
        description="测试：1日收盘价动量"
    )

    print(f"\nFactor Name: {test_factor.name}")
    print(f"Category: {test_factor.category}")
    print(f"Description: {test_factor.description}")
    print(f"Expression: {test_factor.qlib_expression}")
    print(f"Qlib Initialized: {test_factor.qlib_initialized}")

    # 如果Qlib可用，测试计算
    if test_factor.qlib_initialized:
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

        result = test_factor.calculate(mock_data, '600519.SH')

        print(f"\nCalculation Result:")
        print(f"  Symbol: {result.symbol}")
        print(f"  Value: {result.value:.4f}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Raw Value: {result.raw_data.get('raw_value', 'N/A')}")
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

    test_qlib_base_factor()
