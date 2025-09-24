# -*- coding: utf-8 -*-
"""
因子权重优化器
使用多种优化算法为因子分配最优权重
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

from scipy.optimize import minimize
from scipy.stats import rankdata
import cvxpy as cp

from .factor_manager import FactorValue, get_factor_manager
from .auto_factor_selector import FactorPerformance

logger = logging.getLogger(__name__)

class OptimizationMethod(Enum):
    """优化方法枚举"""
    EQUAL_WEIGHT = "equal_weight"
    IC_WEIGHT = "ic_weight"
    RISK_PARITY = "risk_parity"
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    MAX_IC_IR = "max_ic_ir"
    ROBUST_OPTIMIZATION = "robust_optimization"

@dataclass
class OptimizationConstraints:
    """优化约束条件"""
    max_weight: float = 0.5  # 单个因子最大权重
    min_weight: float = 0.0  # 单个因子最小权重
    max_factors: int = 10    # 最大因子数量
    turnover_penalty: float = 0.01  # 换手惩罚系数
    risk_tolerance: float = 0.02     # 风险容忍度
    target_volatility: float = None  # 目标波动率
    leverage_constraint: float = 1.0  # 杠杆约束

@dataclass
class WeightOptimizationResult:
    """权重优化结果"""
    weights: Dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    information_ratio: float
    max_drawdown: float
    optimization_method: str
    optimization_time: datetime
    performance_metrics: Dict[str, Any]
    convergence_info: Dict[str, Any]

class FactorWeightOptimizer:
    """因子权重优化器"""
    
    def __init__(self):
        self.factor_manager = get_factor_manager()
        self.optimization_history = []
        
    def optimize_weights(self, 
                        factor_performances: Dict[str, FactorPerformance],
                        returns_data: Dict[str, pd.Series],
                        method: OptimizationMethod = OptimizationMethod.MAX_IC_IR,
                        constraints: Optional[OptimizationConstraints] = None,
                        lookback_days: int = 252) -> WeightOptimizationResult:
        """
        优化因子权重
        
        Args:
            factor_performances: 因子表现数据
            returns_data: 收益率数据
            method: 优化方法
            constraints: 约束条件
            lookback_days: 回望天数
            
        Returns:
            权重优化结果
        """
        logger.info(f"开始因子权重优化，方法: {method.value}")
        
        if not factor_performances:
            raise ValueError("因子表现数据为空")
        
        constraints = constraints or OptimizationConstraints()
        
        # 构建因子收益矩阵
        factor_returns_matrix = self._build_factor_returns_matrix(
            factor_performances, returns_data, lookback_days
        )
        
        if factor_returns_matrix.empty:
            raise ValueError("无法构建有效的因子收益矩阵")
        
        # 根据不同方法进行优化
        if method == OptimizationMethod.EQUAL_WEIGHT:
            result = self._equal_weight_optimization(factor_performances, constraints)
        elif method == OptimizationMethod.IC_WEIGHT:
            result = self._ic_weight_optimization(factor_performances, constraints)
        elif method == OptimizationMethod.RISK_PARITY:
            result = self._risk_parity_optimization(factor_returns_matrix, constraints)
        elif method == OptimizationMethod.MAX_SHARPE:
            result = self._max_sharpe_optimization(factor_returns_matrix, constraints)
        elif method == OptimizationMethod.MIN_VARIANCE:
            result = self._min_variance_optimization(factor_returns_matrix, constraints)
        elif method == OptimizationMethod.MAX_IC_IR:
            result = self._max_ic_ir_optimization(factor_performances, constraints)
        elif method == OptimizationMethod.ROBUST_OPTIMIZATION:
            result = self._robust_optimization(factor_returns_matrix, constraints)
        else:
            raise ValueError(f"不支持的优化方法: {method}")
        
        # 记录优化历史
        self.optimization_history.append(result)
        
        logger.info(f"因子权重优化完成，预期收益: {result.expected_return:.4f}, "
                   f"预期风险: {result.expected_risk:.4f}")
        
        return result
    
    def _build_factor_returns_matrix(self, 
                                    factor_performances: Dict[str, FactorPerformance],
                                    returns_data: Dict[str, pd.Series],
                                    lookback_days: int) -> pd.DataFrame:
        """构建因子收益矩阵"""
        try:
            factor_returns = {}
            
            for factor_name, performance in factor_performances.items():
                if performance.ic_analysis and 'period_1d' in performance.ic_analysis:
                    # 使用IC值作为因子收益的代理
                    ic_values = performance.ic_analysis['period_1d'].get('ic_values', [])
                    if ic_values and len(ic_values) >= 20:  # 至少需要20个观测值
                        # 取最近的观测值
                        recent_ic = ic_values[-lookback_days:] if len(ic_values) > lookback_days else ic_values
                        factor_returns[factor_name] = recent_ic
            
            if not factor_returns:
                return pd.DataFrame()
            
            # 对齐长度，取最短的序列长度
            min_length = min(len(values) for values in factor_returns.values())
            aligned_returns = {}
            
            for factor_name, values in factor_returns.items():
                aligned_returns[factor_name] = values[-min_length:] if len(values) > min_length else values
            
            return pd.DataFrame(aligned_returns)
            
        except Exception as e:
            logger.error(f"构建因子收益矩阵失败: {e}")
            return pd.DataFrame()
    
    def _equal_weight_optimization(self, 
                                  factor_performances: Dict[str, FactorPerformance],
                                  constraints: OptimizationConstraints) -> WeightOptimizationResult:
        """等权重优化"""
        n_factors = min(len(factor_performances), constraints.max_factors)
        equal_weight = 1.0 / n_factors
        
        # 选择表现最好的因子
        sorted_factors = sorted(
            factor_performances.items(),
            key=lambda x: x[1].overall_score,
            reverse=True
        )[:n_factors]
        
        weights = {factor_name: equal_weight for factor_name, _ in sorted_factors}
        
        # 计算组合指标
        expected_return = np.mean([perf.expected_return for _, perf in sorted_factors])
        expected_risk = np.sqrt(np.mean([perf.volatility ** 2 for _, perf in sorted_factors]))
        sharpe_ratio = expected_return / (expected_risk + 1e-8)
        
        return WeightOptimizationResult(
            weights=weights,
            expected_return=expected_return,
            expected_risk=expected_risk,
            sharpe_ratio=sharpe_ratio,
            information_ratio=np.mean([perf.information_ratio for _, perf in sorted_factors]),
            max_drawdown=np.max([perf.max_drawdown for _, perf in sorted_factors]),
            optimization_method=OptimizationMethod.EQUAL_WEIGHT.value,
            optimization_time=datetime.now(),
            performance_metrics={
                "selected_factors": len(weights),
                "diversification_ratio": 1.0
            },
            convergence_info={"method": "analytical", "success": True}
        )
    
    def _ic_weight_optimization(self, 
                               factor_performances: Dict[str, FactorPerformance],
                               constraints: OptimizationConstraints) -> WeightOptimizationResult:
        """基于IC的权重优化"""
        # 提取IC信息比率
        ic_irs = {}
        for factor_name, performance in factor_performances.items():
            if performance.ic_analysis and 'period_1d' in performance.ic_analysis:
                ic_ir = performance.ic_analysis['period_1d'].get('ic_ir', 0)
                if ic_ir > 0:  # 只选择正IC IR的因子
                    ic_irs[factor_name] = ic_ir
        
        if not ic_irs:
            logger.warning("没有找到有效的IC数据，使用等权重")
            return self._equal_weight_optimization(factor_performances, constraints)
        
        # 选择最好的因子
        sorted_factors = sorted(ic_irs.items(), key=lambda x: x[1], reverse=True)[:constraints.max_factors]
        
        # 根据IC IR分配权重
        total_ic_ir = sum(ic_ir for _, ic_ir in sorted_factors)
        weights = {}
        
        for factor_name, ic_ir in sorted_factors:
            weight = ic_ir / total_ic_ir
            # 应用权重约束
            weight = max(constraints.min_weight, min(constraints.max_weight, weight))
            weights[factor_name] = weight
        
        # 重新标准化权重
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
        
        # 计算组合指标
        selected_performances = [factor_performances[name] for name in weights.keys()]
        expected_return = sum(w * factor_performances[name].expected_return for name, w in weights.items())
        expected_risk = np.sqrt(sum(w**2 * factor_performances[name].volatility**2 for name, w in weights.items()))
        
        return WeightOptimizationResult(
            weights=weights,
            expected_return=expected_return,
            expected_risk=expected_risk,
            sharpe_ratio=expected_return / (expected_risk + 1e-8),
            information_ratio=sum(w * factor_performances[name].information_ratio for name, w in weights.items()),
            max_drawdown=max(factor_performances[name].max_drawdown for name in weights.keys()),
            optimization_method=OptimizationMethod.IC_WEIGHT.value,
            optimization_time=datetime.now(),
            performance_metrics={
                "selected_factors": len(weights),
                "avg_ic_ir": np.mean(list(ic_irs.values()))
            },
            convergence_info={"method": "analytical", "success": True}
        )
    
    def _risk_parity_optimization(self, 
                                 factor_returns_matrix: pd.DataFrame,
                                 constraints: OptimizationConstraints) -> WeightOptimizationResult:
        """风险平价优化"""
        try:
            if factor_returns_matrix.empty:
                raise ValueError("因子收益矩阵为空")
            
            n_factors = len(factor_returns_matrix.columns)
            
            # 计算协方差矩阵
            cov_matrix = factor_returns_matrix.cov().values
            
            # 风险平价目标函数
            def risk_parity_objective(weights):
                portfolio_vol = np.sqrt(weights.T @ cov_matrix @ weights)
                marginal_contrib = cov_matrix @ weights
                contrib = weights * marginal_contrib / portfolio_vol
                
                # 最小化风险贡献的方差
                target_contrib = portfolio_vol / n_factors
                return np.sum((contrib - target_contrib) ** 2)
            
            # 约束条件
            constraints_list = [
                {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # 权重和为1
            ]
            
            # 边界条件
            bounds = [(constraints.min_weight, constraints.max_weight) for _ in range(n_factors)]
            
            # 初始猜测
            x0 = np.array([1.0 / n_factors] * n_factors)
            
            # 优化
            result = minimize(
                risk_parity_objective,
                x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints_list,
                options={'maxiter': 1000, 'ftol': 1e-9}
            )
            
            if not result.success:
                logger.warning("风险平价优化未收敛，使用等权重")
                weights_array = np.array([1.0 / n_factors] * n_factors)
            else:
                weights_array = result.x
            
            # 构建权重字典
            weights = dict(zip(factor_returns_matrix.columns, weights_array))
            
            # 计算组合指标
            expected_return = np.mean(factor_returns_matrix.mean() @ weights_array)
            expected_risk = np.sqrt(weights_array.T @ cov_matrix @ weights_array)
            
            return WeightOptimizationResult(
                weights=weights,
                expected_return=expected_return,
                expected_risk=expected_risk,
                sharpe_ratio=expected_return / (expected_risk + 1e-8),
                information_ratio=expected_return / (expected_risk + 1e-8),
                max_drawdown=0.0,  # 需要历史数据计算
                optimization_method=OptimizationMethod.RISK_PARITY.value,
                optimization_time=datetime.now(),
                performance_metrics={
                    "selected_factors": len(weights),
                    "risk_concentration": np.max(weights_array)
                },
                convergence_info={
                    "success": result.success if 'result' in locals() else False,
                    "iterations": result.nit if 'result' in locals() and hasattr(result, 'nit') else 0
                }
            )
            
        except Exception as e:
            logger.error(f"风险平价优化失败: {e}")
            # 降级到等权重
            n_factors = len(factor_returns_matrix.columns) if not factor_returns_matrix.empty else 1
            equal_weight = 1.0 / n_factors
            weights = {col: equal_weight for col in factor_returns_matrix.columns}
            
            return WeightOptimizationResult(
                weights=weights,
                expected_return=0.0,
                expected_risk=0.0,
                sharpe_ratio=0.0,
                information_ratio=0.0,
                max_drawdown=0.0,
                optimization_method=OptimizationMethod.RISK_PARITY.value,
                optimization_time=datetime.now(),
                performance_metrics={"error": str(e)},
                convergence_info={"success": False, "error": str(e)}
            )
    
    def _max_sharpe_optimization(self, 
                               factor_returns_matrix: pd.DataFrame,
                               constraints: OptimizationConstraints) -> WeightOptimizationResult:
        """最大夏普比率优化"""
        try:
            if factor_returns_matrix.empty:
                raise ValueError("因子收益矩阵为空")
            
            n_factors = len(factor_returns_matrix.columns)
            expected_returns = factor_returns_matrix.mean().values
            cov_matrix = factor_returns_matrix.cov().values
            
            # 目标函数：最大化夏普比率 = 最小化 -预期收益/风险
            def negative_sharpe(weights):
                portfolio_return = weights.T @ expected_returns
                portfolio_vol = np.sqrt(weights.T @ cov_matrix @ weights)
                return -portfolio_return / (portfolio_vol + 1e-8)
            
            # 约束条件
            constraints_list = [
                {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}
            ]
            
            bounds = [(constraints.min_weight, constraints.max_weight) for _ in range(n_factors)]
            x0 = np.array([1.0 / n_factors] * n_factors)
            
            result = minimize(
                negative_sharpe,
                x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints_list,
                options={'maxiter': 1000}
            )
            
            if not result.success:
                logger.warning("最大夏普比率优化未收敛，使用等权重")
                weights_array = np.array([1.0 / n_factors] * n_factors)
            else:
                weights_array = result.x
            
            weights = dict(zip(factor_returns_matrix.columns, weights_array))
            
            expected_return = weights_array.T @ expected_returns
            expected_risk = np.sqrt(weights_array.T @ cov_matrix @ weights_array)
            
            return WeightOptimizationResult(
                weights=weights,
                expected_return=expected_return,
                expected_risk=expected_risk,
                sharpe_ratio=expected_return / (expected_risk + 1e-8),
                information_ratio=expected_return / (expected_risk + 1e-8),
                max_drawdown=0.0,
                optimization_method=OptimizationMethod.MAX_SHARPE.value,
                optimization_time=datetime.now(),
                performance_metrics={
                    "selected_factors": len(weights),
                    "concentration": np.max(weights_array)
                },
                convergence_info={
                    "success": result.success if 'result' in locals() else False,
                    "fun_value": result.fun if 'result' in locals() and hasattr(result, 'fun') else None
                }
            )
            
        except Exception as e:
            logger.error(f"最大夏普比率优化失败: {e}")
            return self._equal_weight_optimization({}, constraints)
    
    def _min_variance_optimization(self, 
                                  factor_returns_matrix: pd.DataFrame,
                                  constraints: OptimizationConstraints) -> WeightOptimizationResult:
        """最小方差优化"""
        try:
            if factor_returns_matrix.empty:
                raise ValueError("因子收益矩阵为空")
                
            n_factors = len(factor_returns_matrix.columns)
            cov_matrix = factor_returns_matrix.cov().values
            
            # 使用cvxpy进行凸优化
            w = cp.Variable(n_factors)
            
            # 目标函数：最小化组合方差
            objective = cp.Minimize(cp.quad_form(w, cov_matrix))
            
            # 约束条件
            constraints_cvx = [
                cp.sum(w) == 1,  # 权重和为1
                w >= constraints.min_weight,  # 权重下界
                w <= constraints.max_weight   # 权重上界
            ]
            
            problem = cp.Problem(objective, constraints_cvx)
            problem.solve(solver=cp.OSQP, verbose=False)
            
            if problem.status not in ["infeasible", "unbounded"]:
                weights_array = w.value
            else:
                logger.warning("最小方差优化不可行，使用等权重")
                weights_array = np.array([1.0 / n_factors] * n_factors)
            
            weights = dict(zip(factor_returns_matrix.columns, weights_array))
            
            expected_return = np.mean(factor_returns_matrix.mean().values @ weights_array)
            expected_risk = np.sqrt(weights_array.T @ cov_matrix @ weights_array)
            
            return WeightOptimizationResult(
                weights=weights,
                expected_return=expected_return,
                expected_risk=expected_risk,
                sharpe_ratio=expected_return / (expected_risk + 1e-8),
                information_ratio=expected_return / (expected_risk + 1e-8),
                max_drawdown=0.0,
                optimization_method=OptimizationMethod.MIN_VARIANCE.value,
                optimization_time=datetime.now(),
                performance_metrics={
                    "selected_factors": len(weights),
                    "portfolio_variance": expected_risk ** 2
                },
                convergence_info={
                    "success": problem.status == "optimal",
                    "solver_status": problem.status
                }
            )
            
        except Exception as e:
            logger.error(f"最小方差优化失败: {e}")
            return self._equal_weight_optimization({}, constraints)
    
    def _max_ic_ir_optimization(self, 
                               factor_performances: Dict[str, FactorPerformance],
                               constraints: OptimizationConstraints) -> WeightOptimizationResult:
        """最大IC信息比率优化"""
        # 提取IC信息比率和稳定性
        factor_metrics = {}
        
        for factor_name, performance in factor_performances.items():
            if performance.ic_analysis and 'period_1d' in performance.ic_analysis:
                ic_analysis = performance.ic_analysis['period_1d']
                ic_ir = ic_analysis.get('ic_ir', 0)
                ic_std = ic_analysis.get('std_ic', 1)
                
                if ic_ir > 0 and ic_std > 0:
                    # 结合IC IR和稳定性
                    stability_score = performance.stability_score if performance.stability_score else 0.5
                    combined_score = ic_ir * stability_score / ic_std
                    factor_metrics[factor_name] = combined_score
        
        if not factor_metrics:
            logger.warning("没有找到有效的IC IR数据，使用等权重")
            return self._equal_weight_optimization(factor_performances, constraints)
        
        # 选择最佳因子
        sorted_factors = sorted(factor_metrics.items(), key=lambda x: x[1], reverse=True)[:constraints.max_factors]
        
        # 基于排序的权重分配（反向排序权重）
        n_selected = len(sorted_factors)
        rank_weights = np.array([n_selected - i for i in range(n_selected)])
        rank_weights = rank_weights / rank_weights.sum()
        
        weights = {}
        for i, (factor_name, _) in enumerate(sorted_factors):
            weight = rank_weights[i]
            weight = max(constraints.min_weight, min(constraints.max_weight, weight))
            weights[factor_name] = weight
        
        # 重新标准化
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
        
        # 计算组合指标
        expected_return = sum(w * factor_performances[name].expected_return for name, w in weights.items())
        expected_risk = np.sqrt(sum(w**2 * factor_performances[name].volatility**2 for name, w in weights.items()))
        avg_ic_ir = np.mean([factor_metrics[name] for name in weights.keys()])
        
        return WeightOptimizationResult(
            weights=weights,
            expected_return=expected_return,
            expected_risk=expected_risk,
            sharpe_ratio=expected_return / (expected_risk + 1e-8),
            information_ratio=avg_ic_ir,
            max_drawdown=max(factor_performances[name].max_drawdown for name in weights.keys()),
            optimization_method=OptimizationMethod.MAX_IC_IR.value,
            optimization_time=datetime.now(),
            performance_metrics={
                "selected_factors": len(weights),
                "avg_ic_ir": avg_ic_ir,
                "factor_scores": {name: factor_metrics[name] for name in weights.keys()}
            },
            convergence_info={"method": "ranking", "success": True}
        )
    
    def _robust_optimization(self, 
                           factor_returns_matrix: pd.DataFrame,
                           constraints: OptimizationConstraints) -> WeightOptimizationResult:
        """鲁棒优化"""
        try:
            if factor_returns_matrix.empty:
                raise ValueError("因子收益矩阵为空")
            
            n_factors = len(factor_returns_matrix.columns)
            
            # 使用滚动窗口估计参数不确定性
            window_size = min(60, len(factor_returns_matrix) // 2)
            
            if len(factor_returns_matrix) < window_size:
                logger.warning("数据不足进行鲁棒优化，使用风险平价")
                return self._risk_parity_optimization(factor_returns_matrix, constraints)
            
            # 估计均值和协方差的不确定性
            returns_data = factor_returns_matrix.values
            n_samples = len(returns_data)
            
            # Bootstrap方法估计参数分布
            n_bootstrap = 100
            mean_estimates = []
            cov_estimates = []
            
            for _ in range(n_bootstrap):
                # 有放回抽样
                bootstrap_indices = np.random.choice(n_samples, n_samples, replace=True)
                bootstrap_data = returns_data[bootstrap_indices]
                
                mean_estimates.append(np.mean(bootstrap_data, axis=0))
                cov_estimates.append(np.cov(bootstrap_data.T))
            
            # 计算不确定性椭球参数
            mean_uncertainty = np.std(mean_estimates, axis=0)
            
            # 使用worst-case优化
            w = cp.Variable(n_factors)
            
            # 最坏情况下的预期收益（考虑均值不确定性）
            base_return = np.mean(mean_estimates, axis=0)
            uncertainty_penalty = cp.norm(cp.multiply(mean_uncertainty, w), 2)
            
            # 目标函数：最大化最坏情况夏普比率
            worst_case_return = base_return.T @ w - uncertainty_penalty
            
            # 使用平均协方差矩阵
            avg_cov = np.mean(cov_estimates, axis=0)
            portfolio_risk = cp.quad_form(w, avg_cov)
            
            # 目标函数：最大化调整后的夏普比率
            objective = cp.Maximize(worst_case_return / cp.sqrt(portfolio_risk + 1e-8))
            
            constraints_cvx = [
                cp.sum(w) == 1,
                w >= constraints.min_weight,
                w <= constraints.max_weight,
                cp.sqrt(portfolio_risk) <= constraints.risk_tolerance  # 风险约束
            ]
            
            problem = cp.Problem(objective, constraints_cvx)
            
            try:
                problem.solve(solver=cp.OSQP, verbose=False)
                
                if problem.status in ["optimal", "optimal_inaccurate"]:
                    weights_array = w.value
                else:
                    raise ValueError(f"优化失败: {problem.status}")
                    
            except:
                logger.warning("鲁棒优化求解失败，使用风险平价")
                return self._risk_parity_optimization(factor_returns_matrix, constraints)
            
            weights = dict(zip(factor_returns_matrix.columns, weights_array))
            
            expected_return = base_return.T @ weights_array
            expected_risk = np.sqrt(weights_array.T @ avg_cov @ weights_array)
            
            return WeightOptimizationResult(
                weights=weights,
                expected_return=expected_return,
                expected_risk=expected_risk,
                sharpe_ratio=expected_return / (expected_risk + 1e-8),
                information_ratio=expected_return / (expected_risk + 1e-8),
                max_drawdown=0.0,
                optimization_method=OptimizationMethod.ROBUST_OPTIMIZATION.value,
                optimization_time=datetime.now(),
                performance_metrics={
                    "selected_factors": len(weights),
                    "uncertainty_penalty": float(uncertainty_penalty.value),
                    "robustness_score": 1.0 - float(uncertainty_penalty.value) / abs(expected_return + 1e-8)
                },
                convergence_info={
                    "success": problem.status in ["optimal", "optimal_inaccurate"],
                    "solver_status": problem.status,
                    "bootstrap_samples": n_bootstrap
                }
            )
            
        except Exception as e:
            logger.error(f"鲁棒优化失败: {e}")
            return self._risk_parity_optimization(factor_returns_matrix, constraints)
    
    def get_optimization_history(self) -> List[WeightOptimizationResult]:
        """获取优化历史记录"""
        return self.optimization_history.copy()
    
    def compare_optimization_methods(self, 
                                   factor_performances: Dict[str, FactorPerformance],
                                   returns_data: Dict[str, pd.Series],
                                   methods: List[OptimizationMethod] = None) -> Dict[str, WeightOptimizationResult]:
        """比较不同优化方法的结果"""
        if methods is None:
            methods = [
                OptimizationMethod.EQUAL_WEIGHT,
                OptimizationMethod.IC_WEIGHT,
                OptimizationMethod.MAX_IC_IR,
                OptimizationMethod.RISK_PARITY
            ]
        
        results = {}
        constraints = OptimizationConstraints()
        
        for method in methods:
            try:
                logger.info(f"测试优化方法: {method.value}")
                result = self.optimize_weights(factor_performances, returns_data, method, constraints)
                results[method.value] = result
            except Exception as e:
                logger.error(f"优化方法 {method.value} 失败: {e}")
                continue
        
        return results

# 便捷函数
def optimize_factor_weights(factor_performances: Dict[str, FactorPerformance],
                          returns_data: Dict[str, pd.Series],
                          method: str = "max_ic_ir") -> WeightOptimizationResult:
    """便捷的因子权重优化函数"""
    optimizer = FactorWeightOptimizer()
    method_enum = OptimizationMethod(method)
    return optimizer.optimize_weights(factor_performances, returns_data, method_enum)