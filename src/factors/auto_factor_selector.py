# -*- coding: utf-8 -*-
"""
自动因子筛选器
基于多维度指标自动筛选有效因子，优化投资策略
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

from .factor_manager import get_factor_manager, FactorValue
from .factor_validator import FactorValidator

logger = logging.getLogger(__name__)

@dataclass
class FactorPerformance:
    """因子表现评估结果"""
    factor_name: str
    ic_metrics: Dict[str, float]       # IC相关指标
    stability_metrics: Dict[str, float] # 稳定性指标
    coverage_metrics: Dict[str, float]  # 覆盖率指标
    risk_metrics: Dict[str, float]     # 风险指标
    overall_score: float               # 综合评分
    rank: int = 0                      # 排名
    recommendation: str = "hold"       # 推荐等级: excellent/good/fair/poor

@dataclass
class SelectionCriteria:
    """因子筛选标准"""
    min_ic_mean: float = 0.02          # 最小平均IC
    max_ic_std: float = 0.5            # 最大IC波动
    min_ic_ir: float = 0.1             # 最小IC信息比率
    min_positive_ic_ratio: float = 0.55 # 最小正IC比例
    min_stability_score: float = 0.4   # 最小稳定性评分
    min_coverage_rate: float = 0.7     # 最小覆盖率
    max_decay_rate: float = 0.3        # 最大衰减率
    min_sample_size: int = 30          # 最小样本量
    
    # 动态调整参数
    market_regime_adjustment: bool = True
    volatility_adjustment: bool = True

class AutoFactorSelector:
    """自动因子筛选器"""
    
    def __init__(self, lookback_days: int = 120):
        self.factor_manager = get_factor_manager()
        self.validator = FactorValidator()
        self.lookback_days = lookback_days
        self.selection_history = []  # 选择历史记录
        
    def select_effective_factors(self, symbols: List[str], 
                               returns_data: Dict[str, pd.Series],
                               factor_data: Dict[str, Dict[str, List[FactorValue]]],
                               criteria: Optional[SelectionCriteria] = None) -> Dict[str, FactorPerformance]:
        """
        自动选择有效因子
        
        Args:
            symbols: 股票代码列表
            returns_data: {symbol: 收益率序列}  
            factor_data: {symbol: {factor_name: [FactorValue]}}
            criteria: 筛选标准
            
        Returns:
            筛选出的有效因子及其表现评估
        """
        if criteria is None:
            criteria = SelectionCriteria()
            
        logger.info(f"开始自动因子筛选，股票数量: {len(symbols)}")
        
        # 获取所有可用因子
        all_factors = self._get_available_factors(factor_data)
        logger.info(f"待筛选因子数量: {len(all_factors)}")
        
        # 并发评估因子表现
        factor_performances = self._evaluate_factors_parallel(
            all_factors, symbols, returns_data, factor_data
        )
        
        # 应用筛选标准
        selected_factors = self._apply_selection_criteria(factor_performances, criteria)
        
        # 市场环境调整
        if criteria.market_regime_adjustment:
            selected_factors = self._adjust_for_market_regime(selected_factors, returns_data)
        
        # 排序和分级
        final_factors = self._rank_and_categorize(selected_factors)
        
        # 记录筛选历史
        self._record_selection_history(final_factors, criteria)
        
        logger.info(f"因子筛选完成，有效因子数量: {len(final_factors)}")
        
        return final_factors
    
    def get_top_factors(self, selection_results: Dict[str, FactorPerformance], 
                       count: int = 5, 
                       min_grade: str = "fair") -> Dict[str, FactorPerformance]:
        """获取表现最佳的前N个因子"""
        grade_scores = {"excellent": 4, "good": 3, "fair": 2, "poor": 1}
        min_score = grade_scores.get(min_grade, 2)
        
        # 筛选满足最小等级的因子
        qualified_factors = {
            name: perf for name, perf in selection_results.items()
            if grade_scores.get(perf.recommendation, 1) >= min_score
        }
        
        # 按综合评分排序
        sorted_factors = dict(sorted(
            qualified_factors.items(),
            key=lambda x: x[1].overall_score,
            reverse=True
        ))
        
        # 返回前N个
        return dict(list(sorted_factors.items())[:count])
    
    def update_selection_criteria(self, historical_performance: Dict[str, Any]) -> SelectionCriteria:
        """根据历史表现动态更新筛选标准"""
        criteria = SelectionCriteria()
        
        try:
            # 分析历史IC表现
            historical_ics = historical_performance.get('ic_history', [])
            if historical_ics:
                # 动态调整IC阈值
                ic_median = np.median(historical_ics)
                criteria.min_ic_mean = max(0.01, ic_median * 0.5)
                
            # 分析市场波动率
            market_volatility = historical_performance.get('market_volatility', 0.02)
            if market_volatility > 0.05:  # 高波动环境
                criteria.min_stability_score *= 1.2  # 提高稳定性要求
                criteria.min_ic_ir *= 0.8  # 降低IR要求
            
            # 分析因子衰减情况
            avg_decay = historical_performance.get('avg_factor_decay', 0.2)
            if avg_decay > 0.25:
                criteria.max_decay_rate = avg_decay * 0.8  # 更严格的衰减要求
            
            logger.info("筛选标准已根据历史表现动态调整")
            
        except Exception as e:
            logger.warning(f"动态调整筛选标准失败: {e}")
            
        return criteria
    
    def _get_available_factors(self, factor_data: Dict[str, Dict[str, List[FactorValue]]]) -> List[str]:
        """获取所有可用因子名称"""
        all_factors = set()
        for symbol_data in factor_data.values():
            all_factors.update(symbol_data.keys())
        return list(all_factors)
    
    def _evaluate_factors_parallel(self, factor_names: List[str], symbols: List[str],
                                 returns_data: Dict[str, pd.Series],
                                 factor_data: Dict[str, Dict[str, List[FactorValue]]]) -> Dict[str, FactorPerformance]:
        """并发评估多个因子的表现"""
        performances = {}
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            # 提交评估任务
            future_to_factor = {
                executor.submit(
                    self._evaluate_single_factor, 
                    factor_name, symbols, returns_data, factor_data
                ): factor_name
                for factor_name in factor_names
            }
            
            # 收集结果
            for future in as_completed(future_to_factor):
                factor_name = future_to_factor[future]
                try:
                    performance = future.result(timeout=60)
                    if performance:
                        performances[factor_name] = performance
                except Exception as e:
                    logger.error(f"评估因子失败 {factor_name}: {e}")
        
        return performances
    
    def _evaluate_single_factor(self, factor_name: str, symbols: List[str],
                               returns_data: Dict[str, pd.Series],
                               factor_data: Dict[str, Dict[str, List[FactorValue]]]) -> Optional[FactorPerformance]:
        """评估单个因子的表现"""
        try:
            # 整理因子数据
            factor_values_by_symbol = {}
            for symbol in symbols:
                if symbol in factor_data and factor_name in factor_data[symbol]:
                    factor_values_by_symbol[symbol] = factor_data[symbol][factor_name]
            
            if len(factor_values_by_symbol) < 5:  # 至少需要5个股票的数据
                return None
            
            # IC分析
            ic_results = self.validator.validate_factor_ic(
                factor_name, list(factor_values_by_symbol.keys()),
                returns_data, factor_values_by_symbol
            )
            
            # 稳定性分析
            stability_results = self.validator.factor_stability_test(
                factor_name, list(factor_values_by_symbol.keys()), 
                factor_values_by_symbol
            )
            
            # 覆盖率分析
            coverage_results = self.validator.factor_coverage_analysis(
                factor_name, symbols, factor_values_by_symbol
            )
            
            # 衰减分析
            decay_results = self.validator.factor_decay_analysis(
                factor_name, list(factor_values_by_symbol.keys()),
                factor_values_by_symbol
            )
            
            # 风险指标
            risk_metrics = self._calculate_risk_metrics(factor_values_by_symbol)
            
            # 综合评分
            overall_score = self._calculate_comprehensive_score(
                ic_results, stability_results, coverage_results, 
                decay_results, risk_metrics
            )
            
            return FactorPerformance(
                factor_name=factor_name,
                ic_metrics=self._extract_ic_metrics(ic_results),
                stability_metrics=self._extract_stability_metrics(stability_results),
                coverage_metrics=coverage_results,
                risk_metrics=risk_metrics,
                overall_score=overall_score
            )
            
        except Exception as e:
            logger.error(f"评估因子失败 {factor_name}: {e}")
            return None
    
    def _calculate_risk_metrics(self, factor_values: Dict[str, List[FactorValue]]) -> Dict[str, float]:
        """计算因子风险指标"""
        all_values = []
        for values in factor_values.values():
            all_values.extend([v.value for v in values])
        
        if not all_values:
            return {"volatility": 1.0, "max_drawdown": 1.0, "skewness": 0.0}
        
        values_array = np.array(all_values)
        
        # 因子波动率
        volatility = np.std(values_array)
        
        # 最大回撤（累积因子值的最大回撤）
        cumulative = np.cumsum(values_array)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (running_max - cumulative) / (running_max + 1e-8)
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
        
        # 偏度
        skewness = self._calculate_skewness(values_array)
        
        return {
            "volatility": volatility,
            "max_drawdown": max_drawdown,
            "skewness": skewness
        }
    
    def _calculate_skewness(self, values: np.ndarray) -> float:
        """计算偏度"""
        if len(values) < 3:
            return 0.0
        
        mean_val = np.mean(values)
        std_val = np.std(values)
        
        if std_val == 0:
            return 0.0
        
        skew = np.mean(((values - mean_val) / std_val) ** 3)
        return skew
    
    def _extract_ic_metrics(self, ic_results: Dict) -> Dict[str, float]:
        """提取IC相关指标"""
        if not ic_results:
            return {"mean_ic": 0, "ic_ir": 0, "positive_ratio": 0.5}
        
        # 计算多期IC的平均值
        all_mean_ics = [result.get("mean_ic", 0) for result in ic_results.values()]
        all_ic_irs = [result.get("ic_ir", 0) for result in ic_results.values()]
        all_pos_ratios = [result.get("positive_ic_ratio", 0.5) for result in ic_results.values()]
        
        return {
            "mean_ic": np.mean(all_mean_ics) if all_mean_ics else 0,
            "ic_ir": np.mean(all_ic_irs) if all_ic_irs else 0,
            "positive_ratio": np.mean(all_pos_ratios) if all_pos_ratios else 0.5,
            "ic_stability": np.std(all_mean_ics) if len(all_mean_ics) > 1 else 1.0
        }
    
    def _extract_stability_metrics(self, stability_results: Dict) -> Dict[str, float]:
        """提取稳定性指标"""
        if not stability_results:
            return {"stability_score": 0, "mean_stability": 1.0}
        
        return {
            "stability_score": stability_results.get("stability_score", 0),
            "mean_stability": stability_results.get("avg_mean_stability", 1.0)
        }
    
    def _calculate_comprehensive_score(self, ic_results: Dict, stability_results: Dict,
                                     coverage_results: Dict, decay_results: Dict,
                                     risk_metrics: Dict) -> float:
        """计算综合评分"""
        score = 0.0
        weights = {
            "ic_quality": 0.35,
            "stability": 0.25, 
            "coverage": 0.15,
            "decay": 0.15,
            "risk": 0.10
        }
        
        try:
            # IC质量评分
            ic_metrics = self._extract_ic_metrics(ic_results)
            ic_score = min(1.0, max(0.0, (ic_metrics["ic_ir"] + 1) / 2))
            
            # 稳定性评分
            stability_score = stability_results.get("stability_score", 0) if stability_results else 0
            stability_score = min(1.0, max(0.0, stability_score))
            
            # 覆盖率评分
            coverage_score = coverage_results.get("symbol_coverage_rate", 0) if coverage_results else 0
            
            # 衰减评分
            decay_score = 0.5  # 默认中性
            if decay_results:
                half_life = decay_results.get("avg_half_life")
                if half_life:
                    if 3 <= half_life <= 10:
                        decay_score = 1.0
                    elif half_life < 3:
                        decay_score = half_life / 3
                    else:
                        decay_score = max(0.1, 10 / half_life)
            
            # 风险评分（风险越小得分越高）
            volatility = risk_metrics.get("volatility", 1.0)
            max_dd = risk_metrics.get("max_drawdown", 1.0)
            risk_score = 1.0 / (1.0 + volatility + max_dd)
            
            # 加权汇总
            score = (ic_score * weights["ic_quality"] +
                    stability_score * weights["stability"] +
                    coverage_score * weights["coverage"] +
                    decay_score * weights["decay"] +
                    risk_score * weights["risk"])
            
        except Exception as e:
            logger.error(f"综合评分计算失败: {e}")
            score = 0.0
        
        return round(score, 4)
    
    def _apply_selection_criteria(self, performances: Dict[str, FactorPerformance],
                                criteria: SelectionCriteria) -> Dict[str, FactorPerformance]:
        """应用筛选标准"""
        selected = {}
        
        for name, perf in performances.items():
            # 检查各项标准
            checks = {
                "ic_mean": perf.ic_metrics.get("mean_ic", 0) >= criteria.min_ic_mean,
                "ic_ir": perf.ic_metrics.get("ic_ir", 0) >= criteria.min_ic_ir,
                "positive_ratio": perf.ic_metrics.get("positive_ratio", 0) >= criteria.min_positive_ic_ratio,
                "stability": perf.stability_metrics.get("stability_score", 0) >= criteria.min_stability_score,
                "coverage": perf.coverage_metrics.get("symbol_coverage_rate", 0) >= criteria.min_coverage_rate
            }
            
            # 记录通过的检查项
            passed_checks = sum(checks.values())
            total_checks = len(checks)
            
            # 如果通过了大部分检查，则入选
            if passed_checks >= total_checks * 0.6:  # 至少通过60%的检查
                selected[name] = perf
                logger.debug(f"因子 {name} 通过筛选: {passed_checks}/{total_checks} 项检查")
            else:
                logger.debug(f"因子 {name} 未通过筛选: {passed_checks}/{total_checks} 项检查")
        
        return selected
    
    def _adjust_for_market_regime(self, factors: Dict[str, FactorPerformance],
                                returns_data: Dict[str, pd.Series]) -> Dict[str, FactorPerformance]:
        """根据市场环境调整因子选择"""
        try:
            # 计算市场整体波动率
            all_returns = []
            for returns in returns_data.values():
                all_returns.extend(returns.values[-20:])  # 最近20天
            
            if not all_returns:
                return factors
            
            market_vol = np.std(all_returns)
            
            adjusted_factors = {}
            for name, perf in factors.items():
                adjusted_perf = perf
                
                # 高波动环境下偏好稳定因子
                if market_vol > 0.03:  # 高波动阈值
                    stability_bonus = perf.stability_metrics.get("stability_score", 0) * 0.1
                    adjusted_perf.overall_score += stability_bonus
                
                # 低波动环境下偏好高IC因子
                elif market_vol < 0.015:  # 低波动阈值
                    ic_bonus = perf.ic_metrics.get("mean_ic", 0) * 2  
                    adjusted_perf.overall_score += ic_bonus
                
                adjusted_factors[name] = adjusted_perf
            
            logger.info(f"已根据市场波动率 {market_vol:.4f} 调整因子评分")
            
        except Exception as e:
            logger.warning(f"市场环境调整失败: {e}")
            return factors
        
        return adjusted_factors
    
    def _rank_and_categorize(self, factors: Dict[str, FactorPerformance]) -> Dict[str, FactorPerformance]:
        """对因子进行排序和分级"""
        # 按综合评分排序
        sorted_factors = sorted(factors.items(), key=lambda x: x[1].overall_score, reverse=True)
        
        # 分级
        total_count = len(sorted_factors)
        for i, (name, perf) in enumerate(sorted_factors):
            perf.rank = i + 1
            
            # 根据排名和评分分级
            if perf.overall_score >= 0.7:
                perf.recommendation = "excellent"
            elif perf.overall_score >= 0.5:
                perf.recommendation = "good" 
            elif perf.overall_score >= 0.3:
                perf.recommendation = "fair"
            else:
                perf.recommendation = "poor"
        
        return {name: perf for name, perf in sorted_factors}
    
    def _record_selection_history(self, selected_factors: Dict[str, FactorPerformance],
                                criteria: SelectionCriteria):
        """记录筛选历史"""
        history_record = {
            "timestamp": datetime.now(),
            "selected_count": len(selected_factors),
            "criteria": criteria,
            "top_factors": list(selected_factors.keys())[:5],
            "avg_score": np.mean([f.overall_score for f in selected_factors.values()]) if selected_factors else 0
        }
        
        self.selection_history.append(history_record)
        
        # 保留最近10次记录
        if len(self.selection_history) > 10:
            self.selection_history = self.selection_history[-10:]
    
    def get_selection_summary(self, selected_factors: Dict[str, FactorPerformance]) -> Dict:
        """生成筛选结果摘要"""
        if not selected_factors:
            return {"message": "未筛选出有效因子"}
        
        # 统计信息
        scores = [f.overall_score for f in selected_factors.values()]
        recommendations = [f.recommendation for f in selected_factors.values()]
        
        grade_counts = {}
        for rec in recommendations:
            grade_counts[rec] = grade_counts.get(rec, 0) + 1
        
        return {
            "total_selected": len(selected_factors),
            "avg_score": round(np.mean(scores), 4),
            "score_range": [round(min(scores), 4), round(max(scores), 4)],
            "grade_distribution": grade_counts,
            "top_3_factors": list(selected_factors.keys())[:3],
            "recommendation": self._generate_recommendation(selected_factors)
        }
    
    def _generate_recommendation(self, factors: Dict[str, FactorPerformance]) -> str:
        """生成使用建议"""
        excellent_count = sum(1 for f in factors.values() if f.recommendation == "excellent")
        good_count = sum(1 for f in factors.values() if f.recommendation == "good")
        
        if excellent_count >= 3:
            return "发现多个优秀因子，建议重点使用并适当分散"
        elif excellent_count + good_count >= 3:
            return "因子质量良好，建议组合使用以提高稳定性"
        elif len(factors) >= 2:
            return "因子数量有限，建议谨慎使用并密切监控表现"
        else:
            return "有效因子较少，建议增加数据样本或调整筛选标准"


# 便捷函数
def quick_factor_selection(symbols: List[str], 
                         factor_data: Dict[str, Dict[str, List[FactorValue]]],
                         returns_data: Dict[str, pd.Series] = None,
                         top_n: int = 3) -> Dict[str, FactorPerformance]:
    """
    快速因子筛选（简化版）
    
    Args:
        symbols: 股票列表
        factor_data: 因子数据
        returns_data: 收益率数据（如果为None，将基于覆盖率等基础指标筛选）
        top_n: 返回前N个因子
    
    Returns:
        筛选出的top因子
    """
    selector = AutoFactorSelector()
    
    # 如果没有收益率数据，使用简化筛选
    if returns_data is None:
        logger.warning("无收益率数据，使用基础覆盖率筛选")
        # 基于覆盖率的简单筛选
        factor_coverage = {}
        all_factors = selector._get_available_factors(factor_data)
        
        for factor_name in all_factors:
            covered_symbols = 0
            total_values = 0
            
            for symbol in symbols:
                if (symbol in factor_data and 
                    factor_name in factor_data[symbol] and 
                    factor_data[symbol][factor_name]):
                    covered_symbols += 1
                    total_values += len(factor_data[symbol][factor_name])
            
            coverage_rate = covered_symbols / len(symbols)
            avg_values = total_values / max(covered_symbols, 1)
            
            # 简单评分：覆盖率 * 数据丰富度
            simple_score = coverage_rate * min(1.0, avg_values / 10)
            
            factor_coverage[factor_name] = FactorPerformance(
                factor_name=factor_name,
                ic_metrics={"mean_ic": 0},
                stability_metrics={"stability_score": coverage_rate},
                coverage_metrics={"symbol_coverage_rate": coverage_rate},
                risk_metrics={"volatility": 0.1},
                overall_score=simple_score,
                recommendation="fair" if simple_score > 0.5 else "poor"
            )
        
        # 按评分排序
        sorted_factors = dict(sorted(
            factor_coverage.items(),
            key=lambda x: x[1].overall_score,
            reverse=True
        ))
        
        return dict(list(sorted_factors.items())[:top_n])
    
    else:
        # 完整筛选
        criteria = SelectionCriteria()
        criteria.min_ic_mean = 0.01  # 降低要求以便快速测试
        
        selected = selector.select_effective_factors(symbols, returns_data, factor_data, criteria)
        return selector.get_top_factors(selected, top_n)