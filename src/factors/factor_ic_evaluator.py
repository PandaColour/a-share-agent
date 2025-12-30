# -*- coding: utf-8 -*-
"""
因子IC评估模块
用于评估因子的预测能力（Information Coefficient）
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
from scipy import stats
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class FactorICEvaluator:
    """因子IC评估器"""

    def __init__(self, cache_dir: str = "factor_cache/ic_evaluation"):
        """
        初始化IC评估器

        Args:
            cache_dir: IC数据缓存目录
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        # IC历史记录
        self.ic_history = {}  # {factor_name: {date: ic_value}}
        self.factor_stats = {}  # {factor_name: stats_dict}

        # 加载历史IC数据
        self._load_ic_history()

        logger.info(f"IC评估器初始化完成，缓存目录: {cache_dir}")

    def calculate_daily_ic(self,
                          factor_values: Dict[str, float],
                          next_day_returns: Dict[str, float],
                          date: str = None) -> float:
        """
        计算单日IC值

        IC = Correlation(因子值, 次日收益率)

        Args:
            factor_values: 当日所有股票的因子值 {symbol: factor_value}
            next_day_returns: 次日所有股票的收益率 {symbol: return}
            date: 日期（可选）

        Returns:
            IC值（-1到1之间）
        """
        # 提取共同的股票代码
        common_symbols = set(factor_values.keys()) & set(next_day_returns.keys())

        if len(common_symbols) < 5:
            logger.warning(f"共同股票数量不足5只，IC计算可能不准确")
            return 0.0

        # 提取对应的值
        factor_array = [factor_values[symbol] for symbol in common_symbols]
        return_array = [next_day_returns[symbol] for symbol in common_symbols]

        # 计算皮尔逊相关系数
        try:
            ic_value, p_value = stats.pearsonr(factor_array, return_array)

            # 如果p值大于0.05，认为相关性不显著
            if p_value > 0.05:
                logger.debug(f"IC不显著 (p={p_value:.4f}), IC={ic_value:.4f}")

            return ic_value if not np.isnan(ic_value) else 0.0

        except Exception as e:
            logger.error(f"计算IC失败: {e}")
            return 0.0

    def calculate_rank_ic(self,
                         factor_values: Dict[str, float],
                         next_day_returns: Dict[str, float]) -> float:
        """
        计算Rank IC (使用Spearman相关系数)

        Rank IC对异常值更鲁棒

        Args:
            factor_values: 因子值字典
            next_day_returns: 收益率字典

        Returns:
            Rank IC值
        """
        common_symbols = set(factor_values.keys()) & set(next_day_returns.keys())

        if len(common_symbols) < 5:
            return 0.0

        factor_array = [factor_values[symbol] for symbol in common_symbols]
        return_array = [next_day_returns[symbol] for symbol in common_symbols]

        try:
            rank_ic, p_value = stats.spearmanr(factor_array, return_array)
            return rank_ic if not np.isnan(rank_ic) else 0.0
        except Exception as e:
            logger.error(f"计算Rank IC失败: {e}")
            return 0.0

    def update_ic_history(self,
                         factor_name: str,
                         date: str,
                         ic_value: float,
                         rank_ic: float = None):
        """
        更新因子IC历史记录

        Args:
            factor_name: 因子名称
            date: 日期
            ic_value: IC值
            rank_ic: Rank IC值（可选）
        """
        if factor_name not in self.ic_history:
            self.ic_history[factor_name] = {}

        self.ic_history[factor_name][date] = {
            'ic': ic_value,
            'rank_ic': rank_ic if rank_ic is not None else ic_value
        }

        # 自动保存
        self._save_ic_history()

    def calculate_rolling_ic(self,
                            factor_name: str,
                            window: int = 20) -> Dict:
        """
        计算滚动IC统计指标

        Args:
            factor_name: 因子名称
            window: 滚动窗口大小（天数）

        Returns:
            统计指标字典
        """
        if factor_name not in self.ic_history:
            logger.warning(f"因子 {factor_name} 没有IC历史数据")
            return {}

        # 提取IC时间序列
        ic_data = self.ic_history[factor_name]
        dates = sorted(ic_data.keys())

        if len(dates) < window:
            logger.warning(f"IC历史数据不足{window}天")
            return {}

        # 取最近window天的数据
        recent_dates = dates[-window:]
        ic_values = [ic_data[date]['ic'] for date in recent_dates]

        # 计算统计指标
        ic_mean = np.mean(ic_values)
        ic_std = np.std(ic_values)
        ic_median = np.median(ic_values)

        # ICIR (Information Coefficient Information Ratio)
        icir = ic_mean / ic_std if ic_std > 0 else 0.0

        # IC胜率（IC>0的比例）
        ic_win_rate = sum(1 for ic in ic_values if ic > 0) / len(ic_values)

        # IC绝对值均值（预测能力强度）
        ic_abs_mean = np.mean([abs(ic) for ic in ic_values])

        stats_dict = {
            'ic_mean': ic_mean,
            'ic_std': ic_std,
            'ic_median': ic_median,
            'icir': icir,
            'ic_win_rate': ic_win_rate,
            'ic_abs_mean': ic_abs_mean,
            'sample_size': len(ic_values),
            'window': window
        }

        return stats_dict

    def calculate_ic_by_market_state(self,
                                     factor_name: str,
                                     market_states: Dict[str, str]) -> Dict:
        """
        计算不同市场状态下的IC

        Args:
            factor_name: 因子名称
            market_states: 市场状态字典 {date: 'bull'/'bear'/'ranging'}

        Returns:
            不同状态下的IC统计
        """
        if factor_name not in self.ic_history:
            return {}

        ic_data = self.ic_history[factor_name]

        # 按市场状态分组
        ic_by_state = {
            'bull': [],
            'bear': [],
            'ranging': []
        }

        for date, ic_record in ic_data.items():
            if date in market_states:
                state = market_states[date]
                if state in ic_by_state:
                    ic_by_state[state].append(ic_record['ic'])

        # 计算各状态的统计
        results = {}
        for state, ic_values in ic_by_state.items():
            if len(ic_values) >= 5:  # 至少5个样本
                results[state] = {
                    'ic_mean': np.mean(ic_values),
                    'ic_std': np.std(ic_values),
                    'sample_size': len(ic_values),
                    'ic_win_rate': sum(1 for ic in ic_values if ic > 0) / len(ic_values)
                }
            else:
                results[state] = {
                    'ic_mean': 0.0,
                    'ic_std': 0.0,
                    'sample_size': len(ic_values),
                    'ic_win_rate': 0.0
                }

        return results

    def evaluate_factor(self, factor_name: str, window: int = 60) -> Dict:
        """
        综合评估因子（主要评估方法）

        Args:
            factor_name: 因子名称
            window: 评估窗口（天数）

        Returns:
            综合评估结果
        """
        # 1. 滚动IC统计
        rolling_stats = self.calculate_rolling_ic(factor_name, window)

        if not rolling_stats:
            return {
                'factor_name': factor_name,
                'status': 'insufficient_data',
                'recommendation': 'collect_more_data'
            }

        # 2. 评级
        ic_mean = rolling_stats['ic_mean']
        icir = rolling_stats['icir']
        ic_win_rate = rolling_stats['ic_win_rate']

        # 评级逻辑
        if ic_mean < 0:
            rating = 'F'
            recommendation = 'eliminate_immediately'
            reason = '负向IC，信号相反'
        elif ic_mean < 0.02:
            if icir < 0.5:
                rating = 'D'
                recommendation = 'eliminate'
                reason = 'IC弱且不稳定'
            else:
                rating = 'C'
                recommendation = 'downweight'
                reason = 'IC弱但稳定，降权观察'
        elif ic_mean < 0.05:
            if ic_win_rate < 0.50:
                rating = 'C'
                recommendation = 'downweight'
                reason = 'IC一般，胜率低'
            else:
                rating = 'B'
                recommendation = 'keep'
                reason = 'IC一般，胜率尚可'
        elif ic_mean < 0.08:
            rating = 'B'
            recommendation = 'keep'
            reason = 'IC良好'
        elif ic_mean < 0.10:
            rating = 'A'
            recommendation = 'upweight'
            reason = 'IC优秀'
        else:
            rating = 'A+'
            recommendation = 'upweight'
            reason = 'IC卓越'

        # 综合评估结果
        result = {
            'factor_name': factor_name,
            'rating': rating,
            'recommendation': recommendation,
            'reason': reason,
            'statistics': rolling_stats,
            'evaluation_date': datetime.now().strftime('%Y-%m-%d')
        }

        # 缓存评估结果
        self.factor_stats[factor_name] = result

        return result

    def batch_evaluate_all_factors(self,
                                   factor_names: List[str],
                                   window: int = 60) -> Dict[str, Dict]:
        """
        批量评估所有因子

        Args:
            factor_names: 因子名称列表
            window: 评估窗口

        Returns:
            所有因子的评估结果
        """
        logger.info(f"开始批量评估 {len(factor_names)} 个因子...")

        results = {}
        for factor_name in factor_names:
            try:
                result = self.evaluate_factor(factor_name, window)
                results[factor_name] = result
                logger.info(f"  ✓ {factor_name}: {result['rating']} ({result['recommendation']})")
            except Exception as e:
                logger.error(f"  ✗ {factor_name}: 评估失败 - {e}")
                results[factor_name] = {
                    'factor_name': factor_name,
                    'status': 'error',
                    'error': str(e)
                }

        logger.info(f"批量评估完成")
        return results

    def get_factor_stats(self, factor_name: str) -> Dict:
        """
        获取因子统计信息（供其他模块使用）

        Args:
            factor_name: 因子名称

        Returns:
            因子统计字典
        """
        if factor_name in self.factor_stats:
            return self.factor_stats[factor_name]

        # 如果没有缓存，重新计算
        return self.evaluate_factor(factor_name)

    def generate_evaluation_report(self,
                                   evaluation_results: Dict[str, Dict],
                                   output_format: str = 'markdown') -> str:
        """
        生成评估报告

        Args:
            evaluation_results: 评估结果字典
            output_format: 输出格式 ('markdown' 或 'json')

        Returns:
            报告文本
        """
        if output_format == 'json':
            return json.dumps(evaluation_results, indent=2, ensure_ascii=False)

        # Markdown格式报告
        report = []
        report.append("# 因子IC评估报告\n")
        report.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.append(f"**评估因子数**: {len(evaluation_results)}\n\n")

        # 统计概览
        ratings = {'A+': 0, 'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        recommendations = {
            'upweight': [],
            'keep': [],
            'downweight': [],
            'eliminate': [],
            'eliminate_immediately': []
        }

        for result in evaluation_results.values():
            if 'rating' in result:
                rating = result['rating']
                if rating in ratings:
                    ratings[rating] += 1

                rec = result['recommendation']
                if rec in recommendations:
                    recommendations[rec].append(result['factor_name'])

        report.append("## 📊 总体统计\n")
        report.append(f"- 卓越因子 (A+): {ratings['A+']}个\n")
        report.append(f"- 优秀因子 (A): {ratings['A']}个\n")
        report.append(f"- 良好因子 (B): {ratings['B']}个\n")
        report.append(f"- 一般因子 (C): {ratings['C']}个\n")
        report.append(f"- 较差因子 (D): {ratings['D']}个\n")
        report.append(f"- 失效因子 (F): {ratings['F']}个\n\n")

        # 建议汇总
        report.append("## 💡 优化建议\n\n")

        if recommendations['eliminate_immediately']:
            report.append("### ❌ 立即淘汰（负向IC）\n")
            for name in recommendations['eliminate_immediately']:
                report.append(f"- {name}\n")
            report.append("\n")

        if recommendations['eliminate']:
            report.append("### ⚠️ 建议淘汰（IC弱且不稳定）\n")
            for name in recommendations['eliminate']:
                report.append(f"- {name}\n")
            report.append("\n")

        if recommendations['downweight']:
            report.append("### 📉 降权观察\n")
            for name in recommendations['downweight']:
                report.append(f"- {name}\n")
            report.append("\n")

        if recommendations['upweight']:
            report.append("### 📈 提高权重\n")
            for name in recommendations['upweight']:
                report.append(f"- {name}\n")
            report.append("\n")

        # 详细评估
        report.append("## 📋 详细评估\n\n")

        # 按评级排序
        sorted_results = sorted(
            evaluation_results.values(),
            key=lambda x: {'A+': 6, 'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}.get(x.get('rating', 'F'), 0),
            reverse=True
        )

        for result in sorted_results:
            if 'rating' not in result:
                continue

            name = result['factor_name']
            rating = result['rating']
            recommendation = result['recommendation']
            reason = result['reason']
            stats = result.get('statistics', {})

            # 评级emoji
            rating_emoji = {
                'A+': '⭐⭐⭐⭐⭐',
                'A': '⭐⭐⭐⭐',
                'B': '⭐⭐⭐',
                'C': '⭐⭐',
                'D': '⭐',
                'F': '❌'
            }.get(rating, '')

            report.append(f"### {name}\n")
            report.append(f"- **评级**: {rating} {rating_emoji}\n")
            report.append(f"- **建议**: {recommendation}\n")
            report.append(f"- **原因**: {reason}\n")

            if stats:
                report.append(f"- **IC均值**: {stats.get('ic_mean', 0):.4f}\n")
                report.append(f"- **IC标准差**: {stats.get('ic_std', 0):.4f}\n")
                report.append(f"- **ICIR**: {stats.get('icir', 0):.2f}\n")
                report.append(f"- **IC胜率**: {stats.get('ic_win_rate', 0):.1%}\n")
                report.append(f"- **样本数**: {stats.get('sample_size', 0)}天\n")

            report.append("\n")

        return "".join(report)

    def _save_ic_history(self):
        """保存IC历史到文件"""
        try:
            filepath = os.path.join(self.cache_dir, "ic_history.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.ic_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存IC历史失败: {e}")

    def _load_ic_history(self):
        """从文件加载IC历史"""
        try:
            filepath = os.path.join(self.cache_dir, "ic_history.json")
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.ic_history = json.load(f)
                logger.info(f"加载IC历史: {len(self.ic_history)}个因子")
        except Exception as e:
            logger.error(f"加载IC历史失败: {e}")
            self.ic_history = {}

    def clear_old_data(self, days_to_keep: int = 90):
        """
        清理旧数据（保留最近N天）

        Args:
            days_to_keep: 保留天数
        """
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')

        for factor_name in self.ic_history:
            old_dates = [
                date for date in self.ic_history[factor_name].keys()
                if date < cutoff_date
            ]

            for date in old_dates:
                del self.ic_history[factor_name][date]

        self._save_ic_history()
        logger.info(f"清理{cutoff_date}之前的IC数据")
