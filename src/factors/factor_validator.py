# -*- coding: utf-8 -*-
"""
因子有效性验证工具
用于验证AI因子的预测能力和稳定性
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

from .factor_manager import get_factor_manager, FactorValue

logger = logging.getLogger(__name__)

class FactorValidator:
    """因子验证器"""
    
    def __init__(self):
        self.factor_manager = get_factor_manager()
        
    def validate_factor_ic(self, factor_name: str, symbols: List[str], 
                          returns_data: Dict[str, pd.Series], 
                          factor_data: Dict[str, List[FactorValue]],
                          periods: List[int] = [1, 5, 10]) -> Dict:
        """
        计算因子的信息系数(IC)
        
        Args:
            factor_name: 因子名称
            symbols: 股票代码列表
            returns_data: {symbol: 收益率序列}
            factor_data: {symbol: 因子值列表}
            periods: 预测周期（天）
            
        Returns:
            IC分析结果
        """
        ic_results = {}
        
        for period in periods:
            ic_values = []
            
            for symbol in symbols:
                if symbol not in returns_data or symbol not in factor_data:
                    continue
                
                returns = returns_data[symbol]
                factors = factor_data[symbol]
                
                # 对齐因子值和未来收益率
                factor_values = []
                future_returns = []
                
                for factor_value in factors:
                    # 获取因子对应日期后period天的收益率
                    factor_date = factor_value.timestamp
                    future_date = factor_date + timedelta(days=period)
                    
                    # 查找最接近的收益率数据
                    available_dates = returns.index
                    closest_date = min(available_dates, 
                                     key=lambda x: abs((x - future_date).days))
                    
                    if abs((closest_date - future_date).days) <= 2:  # 容许2天误差
                        factor_values.append(factor_value.value)
                        future_returns.append(returns[closest_date])
                
                # 计算相关系数
                if len(factor_values) >= 10:  # 至少需要10个样本
                    correlation, p_value = stats.pearsonr(factor_values, future_returns)
                    if not np.isnan(correlation):
                        ic_values.append(correlation)
            
            # 汇总IC统计
            if ic_values:
                ic_results[f"period_{period}d"] = {
                    "mean_ic": np.mean(ic_values),
                    "std_ic": np.std(ic_values),
                    "ic_ir": np.mean(ic_values) / (np.std(ic_values) + 1e-8),  # IC信息比率
                    "positive_ic_ratio": np.mean(np.array(ic_values) > 0),
                    "ic_values": ic_values,
                    "t_stat": stats.ttest_1samp(ic_values, 0)[0] if len(ic_values) > 1 else 0
                }
        
        return ic_results
    
    def factor_decay_analysis(self, factor_name: str, symbols: List[str],
                            factor_data: Dict[str, List[FactorValue]],
                            max_periods: int = 20) -> Dict:
        """
        分析因子衰减性
        """
        decay_results = {}
        
        for symbol in symbols:
            if symbol not in factor_data:
                continue
                
            factors = factor_data[symbol]
            if len(factors) < max_periods + 5:
                continue
            
            # 计算不同滞后期的自相关
            factor_values = [f.value for f in factors]
            autocorrs = []
            
            for lag in range(1, min(max_periods, len(factor_values) - 1)):
                correlation = np.corrcoef(
                    factor_values[:-lag], 
                    factor_values[lag:]
                )[0, 1]
                
                if not np.isnan(correlation):
                    autocorrs.append(correlation)
                else:
                    autocorrs.append(0)
            
            if autocorrs:
                decay_results[symbol] = {
                    "autocorrelations": autocorrs,
                    "half_life": self._calculate_half_life(autocorrs)
                }
        
        # 汇总统计
        if decay_results:
            all_autocorrs = []
            half_lives = []
            
            for result in decay_results.values():
                all_autocorrs.extend(result["autocorrelations"])
                if result["half_life"] is not None:
                    half_lives.append(result["half_life"])
            
            summary = {
                "avg_autocorr": np.mean(all_autocorrs) if all_autocorrs else 0,
                "avg_half_life": np.mean(half_lives) if half_lives else None,
                "median_half_life": np.median(half_lives) if half_lives else None,
                "detail_results": decay_results
            }
            
            return summary
        
        return {}
    
    def factor_stability_test(self, factor_name: str, symbols: List[str],
                            factor_data: Dict[str, List[FactorValue]],
                            window_size: int = 60) -> Dict:
        """
        因子稳定性测试：滚动窗口分析因子分布的稳定性
        """
        stability_results = {}
        
        for symbol in symbols:
            if symbol not in factor_data:
                continue
                
            factors = factor_data[symbol]
            if len(factors) < window_size * 2:
                continue
            
            factor_values = [f.value for f in factors]
            
            # 滚动窗口分析
            window_means = []
            window_stds = []
            
            for i in range(len(factor_values) - window_size + 1):
                window_data = factor_values[i:i + window_size]
                window_means.append(np.mean(window_data))
                window_stds.append(np.std(window_data))
            
            if window_means:
                stability_results[symbol] = {
                    "mean_stability": np.std(window_means),  # 均值稳定性
                    "std_stability": np.std(window_stds),    # 波动率稳定性
                    "mean_trend": np.polyfit(range(len(window_means)), window_means, 1)[0],
                    "window_means": window_means,
                    "window_stds": window_stds
                }
        
        # 汇总统计
        if stability_results:
            mean_stabilities = [r["mean_stability"] for r in stability_results.values()]
            std_stabilities = [r["std_stability"] for r in stability_results.values()]
            
            summary = {
                "avg_mean_stability": np.mean(mean_stabilities),
                "avg_std_stability": np.mean(std_stabilities),
                "stability_score": 1 / (1 + np.mean(mean_stabilities) + np.mean(std_stabilities)),
                "detail_results": stability_results
            }
            
            return summary
        
        return {}
    
    def factor_coverage_analysis(self, factor_name: str, symbols: List[str],
                                factor_data: Dict[str, List[FactorValue]]) -> Dict:
        """
        分析因子覆盖率
        """
        total_symbols = len(symbols)
        covered_symbols = len([s for s in symbols if s in factor_data and factor_data[s]])
        
        # 计算每个股票的因子数量
        factor_counts = {}
        for symbol in symbols:
            if symbol in factor_data:
                factor_counts[symbol] = len(factor_data[symbol])
            else:
                factor_counts[symbol] = 0
        
        # 计算时间覆盖率
        if factor_data:
            all_dates = set()
            for factors in factor_data.values():
                for factor in factors:
                    all_dates.add(factor.timestamp.date())
            
            date_coverage = len(all_dates)
        else:
            date_coverage = 0
        
        return {
            "symbol_coverage_rate": covered_symbols / total_symbols,
            "covered_symbols": covered_symbols,
            "total_symbols": total_symbols,
            "avg_factor_count_per_symbol": np.mean(list(factor_counts.values())),
            "date_coverage": date_coverage,
            "factor_counts": factor_counts
        }
    
    def generate_factor_report(self, factor_name: str, symbols: List[str],
                             returns_data: Dict[str, pd.Series],
                             factor_data: Dict[str, List[FactorValue]]) -> Dict:
        """
        生成完整的因子验证报告
        """
        logger.info(f"开始生成因子验证报告: {factor_name}")
        
        report = {
            "factor_name": factor_name,
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_symbols": len(symbols)
        }
        
        try:
            # IC分析
            logger.info("进行IC分析...")
            ic_results = self.validate_factor_ic(factor_name, symbols, returns_data, factor_data)
            report["ic_analysis"] = ic_results
            
            # 衰减分析
            logger.info("进行衰减分析...")
            decay_results = self.factor_decay_analysis(factor_name, symbols, factor_data)
            report["decay_analysis"] = decay_results
            
            # 稳定性分析
            logger.info("进行稳定性分析...")
            stability_results = self.factor_stability_test(factor_name, symbols, factor_data)
            report["stability_analysis"] = stability_results
            
            # 覆盖率分析
            logger.info("进行覆盖率分析...")
            coverage_results = self.factor_coverage_analysis(factor_name, symbols, factor_data)
            report["coverage_analysis"] = coverage_results
            
            # 综合评分
            report["overall_score"] = self._calculate_overall_score(report)
            
            logger.info(f"因子验证报告生成完成: {factor_name}")
            
        except Exception as e:
            logger.error(f"因子验证报告生成失败: {e}")
            report["error"] = str(e)
        
        return report
    
    def _calculate_half_life(self, autocorrs: List[float]) -> Optional[int]:
        """计算因子半衰期"""
        try:
            # 寻找自相关系数降到0.5以下的位置
            for i, corr in enumerate(autocorrs):
                if corr <= 0.5:
                    return i + 1
            return None
        except:
            return None
    
    def _calculate_overall_score(self, report: Dict) -> float:
        """计算综合评分"""
        score = 0.0
        weights = {
            "ic_quality": 0.4,    # IC质量权重
            "stability": 0.3,     # 稳定性权重  
            "coverage": 0.2,      # 覆盖率权重
            "decay": 0.1          # 衰减性权重
        }
        
        try:
            # IC质量评分 (0-1)
            ic_analysis = report.get("ic_analysis", {})
            ic_score = 0.0
            if ic_analysis:
                # 取多期IC的平均信息比率
                irs = [result.get("ic_ir", 0) for result in ic_analysis.values()]
                if irs:
                    avg_ir = np.mean(irs)
                    ic_score = min(1.0, max(0.0, (avg_ir + 1) / 2))  # 标准化到[0,1]
            
            # 稳定性评分 (0-1)
            stability_score = 0.0
            stability_analysis = report.get("stability_analysis", {})
            if stability_analysis:
                stability_metric = stability_analysis.get("stability_score", 0)
                stability_score = min(1.0, max(0.0, stability_metric))
            
            # 覆盖率评分 (0-1)
            coverage_analysis = report.get("coverage_analysis", {})
            coverage_score = coverage_analysis.get("symbol_coverage_rate", 0)
            
            # 衰减性评分 (0-1，半衰期越长越好，但不要太长)
            decay_score = 0.5  # 默认中性
            decay_analysis = report.get("decay_analysis", {})
            if decay_analysis:
                half_life = decay_analysis.get("avg_half_life")
                if half_life:
                    if 3 <= half_life <= 10:  # 理想的半衰期范围
                        decay_score = 1.0
                    elif half_life < 3:
                        decay_score = half_life / 3
                    else:
                        decay_score = max(0.1, 10 / half_life)
            
            # 加权汇总
            score = (ic_score * weights["ic_quality"] +
                    stability_score * weights["stability"] +
                    coverage_score * weights["coverage"] +
                    decay_score * weights["decay"])
            
        except Exception as e:
            logger.error(f"综合评分计算失败: {e}")
            score = 0.0
        
        return round(score, 4)
    
    def plot_factor_analysis(self, report: Dict, save_path: str = None):
        """绘制因子分析图表"""
        try:
            import matplotlib.pyplot as plt
            plt.style.use('default')
            
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle(f'因子分析报告: {report["factor_name"]}', fontsize=16)
            
            # IC分析图
            ic_data = report.get("ic_analysis", {})
            if ic_data:
                periods = list(ic_data.keys())
                mean_ics = [ic_data[p].get("mean_ic", 0) for p in periods]
                
                axes[0, 0].bar(periods, mean_ics)
                axes[0, 0].set_title('IC Analysis')
                axes[0, 0].set_ylabel('Mean IC')
                axes[0, 0].tick_params(axis='x', rotation=45)
            
            # 稳定性分析图
            stability_data = report.get("stability_analysis", {})
            if stability_data and "detail_results" in stability_data:
                # 取第一个股票的数据作为示例
                first_symbol = list(stability_data["detail_results"].keys())[0]
                window_means = stability_data["detail_results"][first_symbol]["window_means"]
                
                axes[0, 1].plot(window_means)
                axes[0, 1].set_title('Factor Stability (Sample)')
                axes[0, 1].set_ylabel('Rolling Mean')
                axes[0, 1].set_xlabel('Window')
            
            # 覆盖率分析图
            coverage_data = report.get("coverage_analysis", {})
            if coverage_data:
                coverage_rate = coverage_data.get("symbol_coverage_rate", 0)
                axes[1, 0].pie([coverage_rate, 1 - coverage_rate], 
                              labels=['Covered', 'Not Covered'],
                              autopct='%1.1f%%')
                axes[1, 0].set_title('Coverage Analysis')
            
            # 综合评分
            overall_score = report.get("overall_score", 0)
            axes[1, 1].bar(['Overall Score'], [overall_score])
            axes[1, 1].set_title('Overall Factor Score')
            axes[1, 1].set_ylabel('Score')
            axes[1, 1].set_ylim([0, 1])
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"因子分析图表已保存: {save_path}")
            
            plt.show()
            
        except ImportError:
            logger.warning("matplotlib不可用，跳过图表生成")
        except Exception as e:
            logger.error(f"绘制因子分析图表失败: {e}")


# 便捷函数
def validate_factor_simple(factor_name: str, test_symbols: List[str], 
                          days_back: int = 30) -> Dict:
    """
    简化的因子验证函数，用于快速测试
    
    Args:
        factor_name: 要验证的因子名称
        test_symbols: 测试用的股票代码列表
        days_back: 回溯天数
        
    Returns:
        验证结果摘要
    """
    validator = FactorValidator()
    
    try:
        # 这里需要根据实际情况获取历史数据和因子数据
        # 简化版本只返回基本信息
        
        factor_manager = get_factor_manager()
        
        # 获取因子覆盖情况
        coverage_info = {
            "factor_registered": factor_name in factor_manager.factors,
            "total_test_symbols": len(test_symbols),
            "validation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if factor_name in factor_manager.factors:
            factor_info = factor_manager.factors[factor_name]
            coverage_info.update({
                "factor_category": factor_info.category,
                "factor_description": factor_info.description
            })
        
        return coverage_info
        
    except Exception as e:
        logger.error(f"因子验证失败: {e}")
        return {"error": str(e)}