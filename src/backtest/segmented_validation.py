# -*- coding: utf-8 -*-
"""
分段验证回测框架
支持在有数据的时段做充分验证，处理情绪因子数据缺失问题
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class ValidationPeriod:
    """验证时段"""
    start_date: str
    end_date: str
    data_type: str  # 'real' or 'proxy'
    days_count: int


@dataclass
class SegmentedValidationResult:
    """分段验证结果"""
    factor_name: str
    full_period: Tuple[str, str]
    validation_periods: List[ValidationPeriod]

    # IC指标
    mean_ic: float
    ic_ir: float
    positive_ic_ratio: float

    # 收益指标
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float

    # 增量价值
    baseline_sharpe: float
    incremental_sharpe: float

    # 统计显著性
    is_significant: bool
    p_value: float

    # 综合评估
    recommendation: str
    confidence_level: str


class SegmentedBacktestEngine:
    """分段验证回测引擎"""

    def __init__(self):
        self.validation_results = {}

    def validate_factor_with_partial_data(self,
                                         factor_name: str,
                                         factor_calculator: callable,
                                         full_backtest_period: Tuple[str, str],
                                         data_availability_periods: List[Tuple[str, str, str]],
                                         price_data: Dict[str, pd.DataFrame],
                                         **factor_data) -> SegmentedValidationResult:
        """
        分段验证因子（核心方法）

        Args:
            factor_name: 因子名称
            factor_calculator: 因子计算函数
            full_backtest_period: 完整回测期 ('2023-01-01', '2025-01-01')
            data_availability_periods: 数据可用期列表 [('2024-06-01', '2025-01-01', 'real'), ...]
            price_data: 价格数据字典 {symbol: DataFrame}
            **factor_data: 因子特定数据（如龙虎榜、社交媒体数据）

        Returns:
            SegmentedValidationResult
        """

        logger.info(f"="*60)
        logger.info(f"📊 开始分段验证因子: {factor_name}")
        logger.info(f"完整回测期: {full_backtest_period[0]} ~ {full_backtest_period[1]}")
        logger.info(f"数据可用期数量: {len(data_availability_periods)}")

        validation_periods = []
        all_ics = []
        all_returns = []

        # 对每个数据可用期进行验证
        for period_info in data_availability_periods:
            start_date, end_date, data_type = period_info

            logger.info(f"\n🔍 验证时段: {start_date} ~ {end_date} ({data_type})")

            # 筛选该时段的数据
            period_price_data = self._filter_data_by_period(
                price_data, start_date, end_date
            )

            # 计算因子值
            period_factor_values = self._calculate_factor_values(
                factor_calculator,
                period_price_data,
                start_date,
                end_date,
                **factor_data
            )

            # 计算收益率
            period_returns = self._calculate_returns(period_price_data)

            # 计算IC
            ic_series = self._calculate_ic_series(period_factor_values, period_returns)
            all_ics.extend(ic_series)

            # 生成交易信号并回测
            backtest_result = self._run_segment_backtest(
                period_factor_values,
                period_returns
            )
            all_returns.extend(backtest_result['returns'])

            # 记录验证时段
            validation_periods.append(ValidationPeriod(
                start_date=start_date,
                end_date=end_date,
                data_type=data_type,
                days_count=len(period_factor_values)
            ))

            logger.info(f"  ✓ IC均值: {np.mean(ic_series):.4f}")
            logger.info(f"  ✓ 夏普比: {backtest_result['sharpe']:.2f}")

        # 汇总所有时段的结果
        result = self._aggregate_validation_results(
            factor_name,
            full_backtest_period,
            validation_periods,
            all_ics,
            all_returns,
            price_data
        )

        logger.info(f"\n📊 验证汇总:")
        logger.info(f"  平均IC: {result.mean_ic:.4f}")
        logger.info(f"  IC IR: {result.ic_ir:.4f}")
        logger.info(f"  夏普比: {result.sharpe_ratio:.2f}")
        logger.info(f"  增量夏普: {result.incremental_sharpe:.2f}")
        logger.info(f"  推荐: {result.recommendation}")
        logger.info(f"="*60)

        return result

    def _filter_data_by_period(self,
                               price_data: Dict[str, pd.DataFrame],
                               start_date: str,
                               end_date: str) -> Dict[str, pd.DataFrame]:
        """按时段筛选数据"""
        filtered_data = {}

        for symbol, df in price_data.items():
            df_filtered = df.loc[start_date:end_date]
            if not df_filtered.empty:
                filtered_data[symbol] = df_filtered

        return filtered_data

    def _calculate_factor_values(self,
                                 factor_calculator: callable,
                                 price_data: Dict[str, pd.DataFrame],
                                 start_date: str,
                                 end_date: str,
                                 **factor_data) -> pd.DataFrame:
        """计算因子值"""
        factor_values = {}

        for symbol, df in price_data.items():
            try:
                # 调用因子计算函数
                factor_value = factor_calculator(
                    symbol=symbol,
                    price_data=df,
                    **factor_data
                )

                factor_values[symbol] = factor_value

            except Exception as e:
                logger.warning(f"计算因子失败 {symbol}: {e}")
                continue

        # 转换为DataFrame
        if not factor_values:
            return pd.DataFrame(columns=['factor_value'])

        # 创建DataFrame，指定index避免标量值错误
        factor_df = pd.DataFrame.from_dict(
            factor_values,
            orient='index',
            columns=['factor_value']
        )

        return factor_df

    def _calculate_returns(self,
                          price_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """计算收益率"""
        returns_dict = {}

        for symbol, df in price_data.items():
            if 'Close' in df.columns:
                returns = df['Close'].pct_change()
                returns_dict[symbol] = returns

        returns_df = pd.DataFrame(returns_dict)

        return returns_df

    def _calculate_ic_series(self,
                            factor_values: pd.DataFrame,
                            returns: pd.DataFrame) -> List[float]:
        """计算IC序列"""
        ic_series = []

        # 按日期计算IC
        common_dates = factor_values.index.intersection(returns.index)

        for date in common_dates:
            try:
                # 当日因子值
                fv = factor_values.loc[date]
                # 次日收益
                next_date_idx = returns.index.get_loc(date) + 1
                if next_date_idx < len(returns):
                    next_returns = returns.iloc[next_date_idx]

                    # 找到共同的股票
                    common_symbols = fv.index.intersection(next_returns.index)

                    if len(common_symbols) >= 5:
                        fv_values = fv[common_symbols].values
                        ret_values = next_returns[common_symbols].values

                        # 计算相关系数
                        ic, _ = stats.pearsonr(fv_values, ret_values)

                        if not np.isnan(ic):
                            ic_series.append(ic)

            except Exception as e:
                continue

        return ic_series

    def _run_segment_backtest(self,
                             factor_values: pd.DataFrame,
                             returns: pd.DataFrame) -> Dict:
        """运行分段回测"""

        # 生成信号：因子值>0买入，<0卖空
        signals = np.sign(factor_values['factor_value'])

        # 计算策略收益
        strategy_returns = []

        for date_idx in range(len(factor_values)):
            try:
                date = factor_values.index[date_idx]

                # 当日信号
                day_signals = signals.loc[date]

                # 次日收益
                if date_idx + 1 < len(returns):
                    next_returns = returns.iloc[date_idx + 1]

                    # 共同股票
                    common_symbols = day_signals.index.intersection(next_returns.index)

                    if len(common_symbols) > 0:
                        # 策略收益 = 信号 * 实际收益
                        portfolio_return = (
                            day_signals[common_symbols] * next_returns[common_symbols]
                        ).mean()

                        strategy_returns.append(portfolio_return)

            except Exception as e:
                continue

        strategy_returns = pd.Series(strategy_returns)

        # 计算指标
        if len(strategy_returns) > 0:
            sharpe = strategy_returns.mean() / (strategy_returns.std() + 1e-8) * np.sqrt(252)
            win_rate = (strategy_returns > 0).sum() / len(strategy_returns)
        else:
            sharpe = 0.0
            win_rate = 0.5

        return {
            'returns': strategy_returns.tolist(),
            'sharpe': sharpe,
            'win_rate': win_rate
        }

    def _aggregate_validation_results(self,
                                     factor_name: str,
                                     full_period: Tuple[str, str],
                                     validation_periods: List[ValidationPeriod],
                                     all_ics: List[float],
                                     all_returns: List[float],
                                     price_data: Dict[str, pd.DataFrame]) -> SegmentedValidationResult:
        """汇总验证结果"""

        # IC指标
        mean_ic = np.mean(all_ics) if all_ics else 0.0
        std_ic = np.std(all_ics) if len(all_ics) > 1 else 1.0
        ic_ir = mean_ic / (std_ic + 1e-8)
        positive_ic_ratio = sum(1 for ic in all_ics if ic > 0) / max(len(all_ics), 1)

        # 收益指标
        returns_series = pd.Series(all_returns)
        if len(returns_series) > 0:
            annualized_return = returns_series.mean() * 252
            sharpe_ratio = returns_series.mean() / (returns_series.std() + 1e-8) * np.sqrt(252)

            # 最大回撤
            cumulative = (1 + returns_series).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min()

            win_rate = (returns_series > 0).sum() / len(returns_series)
        else:
            annualized_return = 0.0
            sharpe_ratio = 0.0
            max_drawdown = 0.0
            win_rate = 0.5

        # 计算基准（简单动量）和增量价值
        baseline_sharpe, incremental_sharpe = self._calculate_incremental_value(
            returns_series, price_data, validation_periods
        )

        # 统计显著性
        is_significant, p_value = self._test_significance(all_ics)

        # 综合评估
        recommendation, confidence = self._generate_recommendation(
            mean_ic, ic_ir, sharpe_ratio, incremental_sharpe,
            is_significant, len(validation_periods)
        )

        return SegmentedValidationResult(
            factor_name=factor_name,
            full_period=full_period,
            validation_periods=validation_periods,
            mean_ic=mean_ic,
            ic_ir=ic_ir,
            positive_ic_ratio=positive_ic_ratio,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            baseline_sharpe=baseline_sharpe,
            incremental_sharpe=incremental_sharpe,
            is_significant=is_significant,
            p_value=p_value,
            recommendation=recommendation,
            confidence_level=confidence
        )

    def _calculate_incremental_value(self,
                                     strategy_returns: pd.Series,
                                     price_data: Dict[str, pd.DataFrame],
                                     validation_periods: List[ValidationPeriod]) -> Tuple[float, float]:
        """计算相对基准的增量价值"""

        # 简化：使用随机收益作为基准
        if len(strategy_returns) > 20:
            baseline_sharpe = 0.5  # 假设基准夏普比为0.5
            strategy_sharpe = strategy_returns.mean() / (strategy_returns.std() + 1e-8) * np.sqrt(252)
            incremental_sharpe = strategy_sharpe - baseline_sharpe
        else:
            baseline_sharpe = 0.0
            incremental_sharpe = 0.0

        return baseline_sharpe, incremental_sharpe

    def _test_significance(self, ic_series: List[float]) -> Tuple[bool, float]:
        """统计显著性检验"""
        if len(ic_series) < 10:
            return False, 1.0

        # t检验：均值是否显著不为0
        t_stat, p_value = stats.ttest_1samp(ic_series, 0)

        is_significant = p_value < 0.05

        return is_significant, p_value

    def _generate_recommendation(self,
                                 mean_ic: float,
                                 ic_ir: float,
                                 sharpe: float,
                                 incremental_sharpe: float,
                                 is_significant: bool,
                                 n_periods: int) -> Tuple[str, str]:
        """生成推荐"""

        # 数据充分性
        if n_periods < 1:
            return "❌ 数据不足，无法验证", "very_low"

        # 统计显著性
        if not is_significant:
            return "⚠️ 统计不显著，谨慎使用", "low"

        # IC质量
        if mean_ic < 0.02:
            return "❌ IC过低，不推荐使用", "low"

        # 增量价值
        if incremental_sharpe < 0.1:
            return "⚠️ 增量价值有限，可选用", "medium"

        # 综合评估
        if ic_ir > 0.5 and sharpe > 1.0 and incremental_sharpe > 0.3:
            return "✅ 强烈推荐使用", "high"
        elif ic_ir > 0.3 and sharpe > 0.5 and incremental_sharpe > 0.2:
            return "✅ 推荐使用", "medium"
        else:
            return "✅ 可以使用", "medium"


# 便捷函数
def quick_validate_sentiment_factor(factor_name: str,
                                    factor_calculator: callable,
                                    sentiment_data_period: Tuple[str, str],
                                    price_data: Dict[str, pd.DataFrame],
                                    **sentiment_data) -> SegmentedValidationResult:
    """快速验证情绪因子"""

    engine = SegmentedBacktestEngine()

    # 只在有情绪数据的时段验证
    data_periods = [(sentiment_data_period[0], sentiment_data_period[1], 'real')]

    result = engine.validate_factor_with_partial_data(
        factor_name=factor_name,
        factor_calculator=factor_calculator,
        full_backtest_period=('2023-01-01', '2025-01-01'),  # 完整期
        data_availability_periods=data_periods,
        price_data=price_data,
        **sentiment_data
    )

    return result
