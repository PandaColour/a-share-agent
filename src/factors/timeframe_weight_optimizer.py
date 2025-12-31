# -*- coding: utf-8 -*-
"""
时间框架权重优化器
针对多时间框架因子内部的信号融合权重进行动态优化
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import json
import os
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

from scipy.optimize import minimize
from scipy.stats import rankdata

logger = logging.getLogger(__name__)


@dataclass
class TimeframeSignalPerformance:
    """时间框架信号表现"""
    timeframe_key: str  # 如 'daily', '5min_long', '5min_short'
    ic_mean: float      # IC均值
    ic_std: float       # IC标准差
    ic_ir: float        # IC信息比率
    win_rate: float     # 胜率
    sample_count: int   # 样本数量


@dataclass
class TimeframeWeightResult:
    """时间框架权重优化结果"""
    factor_name: str
    weights: Dict[str, float]  # {timeframe_key: weight}
    expected_ic: float
    expected_ir: float
    optimization_method: str
    optimization_time: datetime
    performance_metrics: Dict[str, TimeframeSignalPerformance]


class TimeframeWeightOptimizer:
    """时间框架权重优化器

    专门优化多时间框架因子内部的信号融合权重
    支持基于IC分析的动态权重调整
    """

    def __init__(self, cache_dir: str = "factor_cache"):
        self.cache_dir = cache_dir
        self.weights_file = os.path.join(cache_dir, "timeframe_weights.json")

        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)

        # 加载已有权重
        self.current_weights = self._load_weights()

        # 优化历史
        self.optimization_history = []

        logger.info(f"时间框架权重优化器初始化，缓存目录: {cache_dir}")

    def evaluate_timeframe_signals(
        self,
        factor_name: str,
        timeframe_signals: Dict[str, pd.Series],
        forward_returns: pd.Series,
        lookback_days: int = 60
    ) -> Dict[str, TimeframeSignalPerformance]:
        """评估各时间框架信号的表现

        Args:
            factor_name: 因子名称（如 'multi_timeframe_rsi'）
            timeframe_signals: 各时间框架的信号序列
                {
                    'daily': pd.Series([...]),
                    '5min_long': pd.Series([...]),
                    '5min_short': pd.Series([...])
                }
            forward_returns: 前向收益率序列
            lookback_days: 回望天数

        Returns:
            各时间框架的表现指标
        """
        logger.info(f"评估因子 {factor_name} 的时间框架信号表现")

        performances = {}

        for tf_key, signal in timeframe_signals.items():
            try:
                # 对齐数据
                aligned_signal, aligned_returns = self._align_data(
                    signal, forward_returns, lookback_days
                )

                if len(aligned_signal) < 20:
                    logger.warning(f"时间框架 {tf_key} 数据不足: {len(aligned_signal)} < 20")
                    continue

                # 计算IC
                ic_values = self._calculate_rolling_ic(aligned_signal, aligned_returns)

                if len(ic_values) == 0:
                    continue

                # 计算表现指标
                ic_mean = np.mean(ic_values)
                ic_std = np.std(ic_values)
                ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0

                # 计算胜率（IC > 0的比例）
                win_rate = np.sum(np.array(ic_values) > 0) / len(ic_values)

                performances[tf_key] = TimeframeSignalPerformance(
                    timeframe_key=tf_key,
                    ic_mean=ic_mean,
                    ic_std=ic_std,
                    ic_ir=ic_ir,
                    win_rate=win_rate,
                    sample_count=len(ic_values)
                )

                logger.debug(f"  {tf_key}: IC={ic_mean:.4f}, IR={ic_ir:.4f}, 胜率={win_rate:.2%}")

            except Exception as e:
                logger.error(f"评估时间框架 {tf_key} 失败: {e}")
                continue

        return performances

    def optimize_weights(
        self,
        factor_name: str,
        performances: Dict[str, TimeframeSignalPerformance],
        method: str = "ic_ir",
        min_weight: float = 0.05,
        max_weight: float = 0.8
    ) -> TimeframeWeightResult:
        """优化时间框架权重

        Args:
            factor_name: 因子名称
            performances: 各时间框架表现
            method: 优化方法 ('ic_ir', 'ic_mean', 'equal', 'risk_parity')
            min_weight: 最小权重
            max_weight: 最大权重

        Returns:
            权重优化结果
        """
        logger.info(f"优化因子 {factor_name} 的时间框架权重，方法: {method}")

        if not performances:
            raise ValueError("时间框架表现数据为空")

        # 根据方法计算权重
        if method == "ic_ir":
            weights = self._ic_ir_weight_optimization(performances)
        elif method == "ic_mean":
            weights = self._ic_mean_weight_optimization(performances)
        elif method == "equal":
            weights = self._equal_weight_optimization(performances)
        elif method == "risk_parity":
            weights = self._risk_parity_weight_optimization(performances)
        else:
            raise ValueError(f"不支持的优化方法: {method}")

        # 应用权重约束
        weights = self._apply_constraints(weights, min_weight, max_weight)

        # 计算预期表现
        expected_ic = sum(
            weights[tf_key] * perf.ic_mean
            for tf_key, perf in performances.items()
            if tf_key in weights
        )

        expected_ir = sum(
            weights[tf_key] * perf.ic_ir
            for tf_key, perf in performances.items()
            if tf_key in weights
        )

        # 构建结果
        result = TimeframeWeightResult(
            factor_name=factor_name,
            weights=weights,
            expected_ic=expected_ic,
            expected_ir=expected_ir,
            optimization_method=method,
            optimization_time=datetime.now(),
            performance_metrics=performances
        )

        # 记录历史
        self.optimization_history.append(result)

        logger.info(f"权重优化完成: {weights}")
        logger.info(f"预期IC={expected_ic:.4f}, 预期IR={expected_ir:.4f}")

        return result

    def _ic_ir_weight_optimization(
        self,
        performances: Dict[str, TimeframeSignalPerformance]
    ) -> Dict[str, float]:
        """基于IC信息比率的权重优化"""

        # 提取IC IR值
        ir_values = {}
        for tf_key, perf in performances.items():
            # 确保IR为正值
            ir_values[tf_key] = max(0.0, perf.ic_ir)

        # 归一化
        total_ir = sum(ir_values.values())
        if total_ir == 0:
            # 如果所有IR都为0或负，使用等权
            return self._equal_weight_optimization(performances)

        weights = {
            tf_key: ir_val / total_ir
            for tf_key, ir_val in ir_values.items()
        }

        return weights

    def _ic_mean_weight_optimization(
        self,
        performances: Dict[str, TimeframeSignalPerformance]
    ) -> Dict[str, float]:
        """基于IC均值的权重优化"""

        # 提取IC均值
        ic_values = {}
        for tf_key, perf in performances.items():
            ic_values[tf_key] = max(0.0, perf.ic_mean)

        # 归一化
        total_ic = sum(ic_values.values())
        if total_ic == 0:
            return self._equal_weight_optimization(performances)

        weights = {
            tf_key: ic_val / total_ic
            for tf_key, ic_val in ic_values.items()
        }

        return weights

    def _equal_weight_optimization(
        self,
        performances: Dict[str, TimeframeSignalPerformance]
    ) -> Dict[str, float]:
        """等权重优化"""
        n = len(performances)
        weights = {tf_key: 1.0 / n for tf_key in performances.keys()}
        return weights

    def _risk_parity_weight_optimization(
        self,
        performances: Dict[str, TimeframeSignalPerformance]
    ) -> Dict[str, float]:
        """风险平价权重优化（基于IC标准差）"""

        # 提取IC标准差（风险度量）
        risk_values = {}
        for tf_key, perf in performances.items():
            # 风险越小，权重越高
            risk_values[tf_key] = 1.0 / (perf.ic_std + 1e-6)

        # 归一化
        total_inv_risk = sum(risk_values.values())
        weights = {
            tf_key: inv_risk / total_inv_risk
            for tf_key, inv_risk in risk_values.items()
        }

        return weights

    def _apply_constraints(
        self,
        weights: Dict[str, float],
        min_weight: float,
        max_weight: float
    ) -> Dict[str, float]:
        """应用权重约束"""

        # 应用最小/最大约束
        constrained_weights = {}
        for tf_key, weight in weights.items():
            constrained_weights[tf_key] = np.clip(weight, min_weight, max_weight)

        # 重新归一化到和为1
        total = sum(constrained_weights.values())
        if total > 0:
            constrained_weights = {
                tf_key: w / total
                for tf_key, w in constrained_weights.items()
            }

        return constrained_weights

    def _align_data(
        self,
        signal: pd.Series,
        returns: pd.Series,
        lookback_days: int
    ) -> Tuple[pd.Series, pd.Series]:
        """对齐信号和收益数据"""

        # 取最近的数据
        signal_recent = signal.tail(lookback_days)
        returns_recent = returns.tail(lookback_days)

        # 对齐索引
        common_index = signal_recent.index.intersection(returns_recent.index)

        aligned_signal = signal_recent.loc[common_index]
        aligned_returns = returns_recent.loc[common_index]

        return aligned_signal, aligned_returns

    def _calculate_rolling_ic(
        self,
        signal: pd.Series,
        returns: pd.Series,
        window: int = 20
    ) -> List[float]:
        """计算滚动IC"""

        ic_values = []

        for i in range(window, len(signal)):
            window_signal = signal.iloc[i-window:i]
            window_returns = returns.iloc[i-window:i]

            # 计算IC（Spearman相关系数）
            try:
                from scipy.stats import spearmanr
                ic, _ = spearmanr(window_signal, window_returns)
                if not np.isnan(ic):
                    ic_values.append(ic)
            except Exception as e:
                logger.debug(f"计算IC失败: {e}")
                continue

        return ic_values

    def save_weights(self, result: TimeframeWeightResult):
        """保存优化后的权重"""

        # 更新当前权重
        if result.factor_name not in self.current_weights:
            self.current_weights[result.factor_name] = {}

        self.current_weights[result.factor_name] = {
            'weights': result.weights,
            'expected_ic': result.expected_ic,
            'expected_ir': result.expected_ir,
            'method': result.optimization_method,
            'last_update': result.optimization_time.isoformat()
        }

        # 保存到文件
        try:
            with open(self.weights_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_weights, f, indent=2, ensure_ascii=False)

            logger.info(f"时间框架权重已保存: {self.weights_file}")

        except Exception as e:
            logger.error(f"保存时间框架权重失败: {e}")

    def _load_weights(self) -> Dict:
        """加载已保存的权重"""

        if not os.path.exists(self.weights_file):
            logger.info("时间框架权重文件不存在，使用默认权重")
            return {}

        try:
            with open(self.weights_file, 'r', encoding='utf-8') as f:
                weights = json.load(f)

            logger.info(f"成功加载时间框架权重: {len(weights)} 个因子")
            return weights

        except Exception as e:
            logger.error(f"加载时间框架权重失败: {e}")
            return {}

    def get_weights(self, factor_name: str, default_weights: Dict[str, float] = None) -> Dict[str, float]:
        """获取因子的时间框架权重

        Args:
            factor_name: 因子名称
            default_weights: 默认权重（如果没有优化权重）

        Returns:
            时间框架权重字典
        """

        if factor_name in self.current_weights:
            return self.current_weights[factor_name]['weights']

        if default_weights:
            logger.debug(f"使用默认权重: {factor_name}")
            return default_weights

        logger.warning(f"未找到因子 {factor_name} 的权重，返回空字典")
        return {}

    def get_optimization_summary(self) -> Dict:
        """获取优化摘要"""

        summary = {
            'total_factors': len(self.current_weights),
            'factors': {}
        }

        for factor_name, data in self.current_weights.items():
            summary['factors'][factor_name] = {
                'weights': data['weights'],
                'expected_ic': data.get('expected_ic', 0.0),
                'expected_ir': data.get('expected_ir', 0.0),
                'method': data.get('method', 'unknown'),
                'last_update': data.get('last_update', 'unknown')
            }

        return summary


# 全局优化器实例
_global_optimizer: Optional[TimeframeWeightOptimizer] = None


def get_timeframe_weight_optimizer(cache_dir: str = "factor_cache") -> TimeframeWeightOptimizer:
    """获取全局时间框架权重优化器实例（单例模式）"""
    global _global_optimizer

    if _global_optimizer is None:
        _global_optimizer = TimeframeWeightOptimizer(cache_dir)

    return _global_optimizer


# 便捷函数
def optimize_timeframe_weights(
    factor_name: str,
    timeframe_signals: Dict[str, pd.Series],
    forward_returns: pd.Series,
    method: str = "ic_ir",
    lookback_days: int = 60
) -> TimeframeWeightResult:
    """优化时间框架权重的便捷函数

    Args:
        factor_name: 因子名称
        timeframe_signals: 各时间框架信号
        forward_returns: 前向收益率
        method: 优化方法
        lookback_days: 回望天数

    Returns:
        优化结果
    """
    optimizer = get_timeframe_weight_optimizer()

    # 评估表现
    performances = optimizer.evaluate_timeframe_signals(
        factor_name, timeframe_signals, forward_returns, lookback_days
    )

    # 优化权重
    result = optimizer.optimize_weights(factor_name, performances, method)

    # 保存权重
    optimizer.save_weights(result)

    return result
