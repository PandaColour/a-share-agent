# -*- coding: utf-8 -*-
"""
自动策略生成器
基于因子分析和权重优化自动生成交易策略
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json

from .factor_manager import FactorValue, get_factor_manager
from .auto_factor_selector import AutoFactorSelector, FactorPerformance, SelectionCriteria
from .factor_weight_optimizer import FactorWeightOptimizer, OptimizationMethod, OptimizationConstraints, WeightOptimizationResult

logger = logging.getLogger(__name__)

class StrategyType(Enum):
    """策略类型"""
    LONG_ONLY = "long_only"
    LONG_SHORT = "long_short"
    MARKET_NEUTRAL = "market_neutral"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    MULTI_FACTOR = "multi_factor"

class RebalanceFrequency(Enum):
    """调仓频率"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"

@dataclass
class StrategyParameters:
    """策略参数"""
    strategy_type: StrategyType = StrategyType.MULTI_FACTOR
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.WEEKLY
    max_positions: int = 50
    min_positions: int = 10
    position_size_method: str = "equal_weight"  # equal_weight, factor_weight, volatility_adjusted
    
    # 风险控制参数
    max_single_position: float = 0.1  # 单只股票最大权重
    sector_concentration_limit: float = 0.3  # 单个行业最大权重
    turnover_limit: float = 0.5  # 换手率限制
    stop_loss_threshold: float = -0.1  # 止损阈值
    
    # 因子相关参数
    factor_score_threshold: float = 0.5  # 因子评分阈值
    factor_decay_adjustment: bool = True  # 是否进行因子衰减调整
    dynamic_factor_selection: bool = True  # 是否动态选择因子
    
    # 市场状态参数
    market_regime_adjustment: bool = True  # 是否根据市场状态调整
    volatility_adjustment: bool = True  # 是否根据波动率调整
    
@dataclass
class StrategySignal:
    """策略信号"""
    symbol: str
    signal_strength: float  # 信号强度 [-1, 1]
    confidence: float  # 信号置信度 [0, 1]
    factors_contribution: Dict[str, float]  # 各因子贡献度
    risk_score: float  # 风险评分
    position_size: float  # 建议仓位大小
    signal_timestamp: datetime
    
@dataclass
class GeneratedStrategy:
    """生成的策略"""
    strategy_id: str
    strategy_name: str
    strategy_type: StrategyType
    parameters: StrategyParameters
    selected_factors: Dict[str, float]  # 因子名称和权重
    factor_performances: Dict[str, FactorPerformance]
    optimization_result: WeightOptimizationResult
    
    # 策略统计
    expected_return: float
    expected_volatility: float
    expected_sharpe: float
    max_drawdown_estimate: float
    
    # 生成信息
    generation_time: datetime
    model_version: str
    backtest_period: Tuple[str, str]
    
    # 策略逻辑
    signal_generation_logic: str
    position_sizing_logic: str
    risk_management_rules: List[str]

class AutoStrategyGenerator:
    """自动策略生成器"""
    
    def __init__(self):
        self.factor_manager = get_factor_manager()
        self.factor_selector = AutoFactorSelector()
        self.weight_optimizer = FactorWeightOptimizer()
        self.generated_strategies = []
        
    def generate_strategy(self,
                         symbols: List[str],
                         returns_data: Dict[str, pd.Series],
                         factor_data: Dict[str, Dict[str, List[FactorValue]]],
                         strategy_params: Optional[StrategyParameters] = None,
                         selection_criteria: Optional[SelectionCriteria] = None) -> GeneratedStrategy:
        """
        生成自动交易策略
        
        Args:
            symbols: 股票代码列表
            returns_data: 收益率数据
            factor_data: 因子数据
            strategy_params: 策略参数
            selection_criteria: 因子选择标准
            
        Returns:
            生成的策略
        """
        logger.info("开始生成自动交易策略")
        
        strategy_params = strategy_params or StrategyParameters()
        selection_criteria = selection_criteria or SelectionCriteria()
        
        try:
            # 1. 因子选择
            logger.info("开始因子选择...")
            factor_performances = self.factor_selector.select_effective_factors(
                symbols, returns_data, factor_data, selection_criteria
            )
            
            if not factor_performances:
                raise ValueError("没有找到有效的因子")
            
            logger.info(f"选择了 {len(factor_performances)} 个有效因子")
            
            # 2. 因子权重优化
            logger.info("开始因子权重优化...")
            optimization_method = self._determine_optimization_method(strategy_params)
            optimization_constraints = self._create_optimization_constraints(strategy_params)
            
            optimization_result = self.weight_optimizer.optimize_weights(
                factor_performances,
                returns_data,
                optimization_method,
                optimization_constraints
            )
            
            # 3. 生成策略信息
            strategy_id = f"auto_strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            strategy_name = self._generate_strategy_name(strategy_params, factor_performances)
            
            # 4. 构建策略逻辑
            signal_logic = self._generate_signal_logic(strategy_params, optimization_result.weights)
            position_logic = self._generate_position_sizing_logic(strategy_params)
            risk_rules = self._generate_risk_management_rules(strategy_params)
            
            # 5. 计算策略统计
            strategy_stats = self._calculate_strategy_statistics(
                optimization_result, factor_performances, strategy_params
            )
            
            # 6. 创建策略对象
            generated_strategy = GeneratedStrategy(
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                strategy_type=strategy_params.strategy_type,
                parameters=strategy_params,
                selected_factors=optimization_result.weights,
                factor_performances=factor_performances,
                optimization_result=optimization_result,
                expected_return=strategy_stats["expected_return"],
                expected_volatility=strategy_stats["expected_volatility"],
                expected_sharpe=strategy_stats["expected_sharpe"],
                max_drawdown_estimate=strategy_stats["max_drawdown"],
                generation_time=datetime.now(),
                model_version="1.0.0",
                backtest_period=self._get_backtest_period(returns_data),
                signal_generation_logic=signal_logic,
                position_sizing_logic=position_logic,
                risk_management_rules=risk_rules
            )
            
            # 7. 保存策略
            self.generated_strategies.append(generated_strategy)
            
            logger.info(f"策略生成完成: {strategy_name}")
            logger.info(f"预期收益: {strategy_stats['expected_return']:.4f}, "
                       f"预期波动: {strategy_stats['expected_volatility']:.4f}, "
                       f"预期夏普: {strategy_stats['expected_sharpe']:.4f}")
            
            return generated_strategy
            
        except Exception as e:
            logger.error(f"策略生成失败: {e}")
            raise
    
    def generate_trading_signals(self,
                               strategy: GeneratedStrategy,
                               current_data: Dict[str, Dict[str, Any]],
                               symbols: List[str]) -> List[StrategySignal]:
        """
        根据策略生成交易信号
        
        Args:
            strategy: 生成的策略
            current_data: 当前市场数据
            symbols: 股票代码列表
            
        Returns:
            交易信号列表
        """
        logger.info(f"使用策略 {strategy.strategy_name} 生成交易信号")
        
        signals = []
        
        try:
            for symbol in symbols:
                if symbol not in current_data:
                    continue
                
                # 1. 计算当前因子值
                symbol_data = current_data[symbol]
                current_factors = self.factor_manager.calculate_all_factors(
                    symbol, symbol_data, list(strategy.selected_factors.keys())
                )
                
                if not current_factors:
                    continue
                
                # 2. 计算综合信号强度
                signal_strength = 0.0
                factors_contribution = {}
                
                for factor_name, factor_weight in strategy.selected_factors.items():
                    if factor_name in current_factors:
                        factor_value = current_factors[factor_name].value
                        # 标准化因子值到[-1, 1]区间
                        normalized_value = self._normalize_factor_value(
                            factor_value, factor_name, strategy.factor_performances
                        )
                        contribution = normalized_value * factor_weight
                        signal_strength += contribution
                        factors_contribution[factor_name] = contribution
                
                # 3. 计算信号置信度
                confidence = self._calculate_signal_confidence(
                    factors_contribution, strategy.factor_performances
                )
                
                # 4. 计算风险评分
                risk_score = self._calculate_risk_score(symbol, symbol_data, strategy)
                
                # 5. 计算建议仓位
                position_size = self._calculate_position_size(
                    signal_strength, confidence, risk_score, strategy
                )
                
                # 6. 应用策略过滤器
                if abs(signal_strength) >= strategy.parameters.factor_score_threshold:
                    signal = StrategySignal(
                        symbol=symbol,
                        signal_strength=signal_strength,
                        confidence=confidence,
                        factors_contribution=factors_contribution,
                        risk_score=risk_score,
                        position_size=position_size,
                        signal_timestamp=datetime.now()
                    )
                    signals.append(signal)
            
            # 7. 对信号进行排序和筛选
            signals = self._filter_and_rank_signals(signals, strategy)
            
            logger.info(f"生成了 {len(signals)} 个交易信号")
            
            return signals
            
        except Exception as e:
            logger.error(f"信号生成失败: {e}")
            return []
    
    def _determine_optimization_method(self, params: StrategyParameters) -> OptimizationMethod:
        """确定优化方法"""
        if params.strategy_type == StrategyType.LONG_ONLY:
            return OptimizationMethod.MAX_SHARPE
        elif params.strategy_type == StrategyType.MARKET_NEUTRAL:
            return OptimizationMethod.MIN_VARIANCE
        elif params.strategy_type == StrategyType.MULTI_FACTOR:
            return OptimizationMethod.MAX_IC_IR
        else:
            return OptimizationMethod.RISK_PARITY
    
    def _create_optimization_constraints(self, params: StrategyParameters) -> OptimizationConstraints:
        """创建优化约束"""
        return OptimizationConstraints(
            max_weight=params.max_single_position,
            min_weight=0.0,
            max_factors=min(params.max_positions // 2, 15),
            turnover_penalty=params.turnover_limit * 0.1,
            risk_tolerance=0.02 if params.volatility_adjustment else 0.05
        )
    
    def _generate_strategy_name(self, params: StrategyParameters, 
                               factor_performances: Dict[str, FactorPerformance]) -> str:
        """生成策略名称"""
        # 获取主要因子类型
        main_factors = sorted(factor_performances.keys())[:3]
        factor_desc = "_".join(main_factors)
        
        strategy_desc = params.strategy_type.value
        freq_desc = params.rebalance_frequency.value
        
        return f"AutoStrategy_{strategy_desc}_{freq_desc}_{factor_desc}_{datetime.now().strftime('%Y%m%d')}"
    
    def _generate_signal_logic(self, params: StrategyParameters, weights: Dict[str, float]) -> str:
        """生成信号逻辑描述"""
        logic_parts = []
        
        # 基本逻辑
        logic_parts.append("信号生成逻辑:")
        logic_parts.append(f"1. 策略类型: {params.strategy_type.value}")
        logic_parts.append(f"2. 调仓频率: {params.rebalance_frequency.value}")
        
        # 因子权重
        logic_parts.append("3. 因子权重:")
        for factor, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            logic_parts.append(f"   - {factor}: {weight:.4f}")
        
        # 信号计算
        logic_parts.append("4. 信号计算:")
        logic_parts.append("   综合信号 = Σ(标准化因子值 × 因子权重)")
        logic_parts.append(f"   信号阈值: ±{params.factor_score_threshold}")
        
        return "\n".join(logic_parts)
    
    def _generate_position_sizing_logic(self, params: StrategyParameters) -> str:
        """生成仓位大小逻辑"""
        logic_parts = []
        
        logic_parts.append("仓位大小逻辑:")
        logic_parts.append(f"1. 仓位分配方法: {params.position_size_method}")
        logic_parts.append(f"2. 最大持仓数量: {params.max_positions}")
        logic_parts.append(f"3. 最小持仓数量: {params.min_positions}")
        logic_parts.append(f"4. 单只股票最大权重: {params.max_single_position}")
        
        if params.volatility_adjustment:
            logic_parts.append("5. 波动率调整: 启用")
            logic_parts.append("   仓位 = 基础仓位 × (目标波动率 / 股票波动率)")
        
        return "\n".join(logic_parts)
    
    def _generate_risk_management_rules(self, params: StrategyParameters) -> List[str]:
        """生成风险管理规则"""
        rules = []
        
        rules.append(f"单只股票最大权重不超过 {params.max_single_position}")
        rules.append(f"单个行业权重不超过 {params.sector_concentration_limit}")
        rules.append(f"单日换手率不超过 {params.turnover_limit}")
        
        if params.stop_loss_threshold < 0:
            rules.append(f"个股止损线: {params.stop_loss_threshold}")
        
        if params.market_regime_adjustment:
            rules.append("根据市场状态动态调整仓位")
        
        if params.volatility_adjustment:
            rules.append("根据波动率调整仓位大小")
        
        return rules
    
    def _calculate_strategy_statistics(self, 
                                     optimization_result: WeightOptimizationResult,
                                     factor_performances: Dict[str, FactorPerformance],
                                     params: StrategyParameters) -> Dict[str, float]:
        """计算策略统计信息"""
        # 基础统计来自优化结果
        expected_return = optimization_result.expected_return
        expected_volatility = optimization_result.expected_risk
        expected_sharpe = optimization_result.sharpe_ratio
        
        # 估算最大回撤
        max_drawdown = 0.0
        if factor_performances:
            individual_drawdowns = [perf.max_drawdown for perf in factor_performances.values() if perf.max_drawdown]
            if individual_drawdowns:
                # 组合的最大回撤通常小于个股最大回撤的最大值
                max_individual_dd = max(individual_drawdowns)
                diversification_benefit = 0.7  # 分散化效益
                max_drawdown = max_individual_dd * diversification_benefit
        
        # 调整预期收益率（考虑交易成本和滑点）
        trading_cost_adjustment = 0.002  # 0.2% 交易成本
        frequency_multiplier = {
            RebalanceFrequency.DAILY: 252,
            RebalanceFrequency.WEEKLY: 52,
            RebalanceFrequency.MONTHLY: 12,
            RebalanceFrequency.QUARTERLY: 4
        }.get(params.rebalance_frequency, 52)
        
        adjusted_return = expected_return - (trading_cost_adjustment * frequency_multiplier * params.turnover_limit)
        adjusted_sharpe = adjusted_return / (expected_volatility + 1e-8)
        
        return {
            "expected_return": adjusted_return,
            "expected_volatility": expected_volatility,
            "expected_sharpe": adjusted_sharpe,
            "max_drawdown": max_drawdown
        }
    
    def _get_backtest_period(self, returns_data: Dict[str, pd.Series]) -> Tuple[str, str]:
        """获取回测期间"""
        if not returns_data:
            today = datetime.now()
            return (
                (today - timedelta(days=365)).strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d")
            )
        
        # 找到数据的时间范围
        all_dates = []
        for series in returns_data.values():
            all_dates.extend(series.index.tolist())
        
        if all_dates:
            start_date = min(all_dates).strftime("%Y-%m-%d")
            end_date = max(all_dates).strftime("%Y-%m-%d")
            return (start_date, end_date)
        else:
            today = datetime.now()
            return (
                (today - timedelta(days=365)).strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d")
            )
    
    def _normalize_factor_value(self, factor_value: float, factor_name: str,
                               factor_performances: Dict[str, FactorPerformance]) -> float:
        """标准化因子值到[-1, 1]区间"""
        try:
            if factor_name in factor_performances:
                performance = factor_performances[factor_name]
                # 使用因子的历史分布进行标准化
                if hasattr(performance, 'factor_statistics'):
                    stats = performance.factor_statistics
                    mean = stats.get('mean', 0)
                    std = stats.get('std', 1)
                    
                    # Z-score标准化，然后使用tanh函数映射到[-1,1]
                    z_score = (factor_value - mean) / (std + 1e-8)
                    normalized = np.tanh(z_score * 0.5)  # 缩放因子0.5使分布更平滑
                    return normalized
            
            # 默认使用简单的tanh标准化
            return np.tanh(factor_value * 0.1)
            
        except Exception as e:
            logger.warning(f"因子值标准化失败 {factor_name}: {e}")
            return np.tanh(factor_value * 0.1)
    
    def _calculate_signal_confidence(self, 
                                   factors_contribution: Dict[str, float],
                                   factor_performances: Dict[str, FactorPerformance]) -> float:
        """计算信号置信度"""
        if not factors_contribution:
            return 0.0
        
        # 基于因子表现计算置信度
        confidence_scores = []
        
        for factor_name, contribution in factors_contribution.items():
            if factor_name in factor_performances:
                performance = factor_performances[factor_name]
                
                # 因子质量得分
                factor_quality = performance.overall_score
                
                # IC信息比率
                ic_ir = 0.0
                if performance.ic_analysis and 'period_1d' in performance.ic_analysis:
                    ic_ir = performance.ic_analysis['period_1d'].get('ic_ir', 0)
                
                # 稳定性得分
                stability = performance.stability_score if performance.stability_score else 0.5
                
                # 综合置信度 = 因子质量 × IC信息比率 × 稳定性 × 贡献度权重
                factor_confidence = factor_quality * (1 + max(0, ic_ir)) * stability
                confidence_scores.append(factor_confidence * abs(contribution))
        
        if confidence_scores:
            # 加权平均置信度
            total_contribution = sum(abs(c) for c in factors_contribution.values())
            if total_contribution > 0:
                weighted_confidence = sum(confidence_scores) / total_contribution
                return min(1.0, max(0.0, weighted_confidence))
        
        return 0.5  # 默认置信度
    
    def _calculate_risk_score(self, symbol: str, symbol_data: Dict[str, Any], 
                            strategy: GeneratedStrategy) -> float:
        """计算风险评分"""
        risk_score = 0.5  # 基础风险评分
        
        try:
            # 波动率风险
            if 'Close' in symbol_data:
                close_data = symbol_data['Close']
                if hasattr(close_data, 'pct_change'):
                    returns = close_data.pct_change().dropna()
                    if len(returns) > 10:
                        volatility = returns.std()
                        # 标准化波动率风险 (假设日波动率3%为高风险)
                        vol_risk = min(1.0, volatility / 0.03)
                        risk_score += vol_risk * 0.3
            
            # 流动性风险
            if 'Volume' in symbol_data:
                volume_data = symbol_data['Volume']
                if hasattr(volume_data, 'mean'):
                    avg_volume = volume_data.mean()
                    # 成交量越小，流动性风险越高
                    liquidity_risk = max(0, 1.0 - np.log10(avg_volume + 1) / 10)
                    risk_score += liquidity_risk * 0.2
            
            # 价格风险（价格过高或过低）
            if 'Close' in symbol_data:
                current_price = symbol_data['Close'].iloc[-1] if len(symbol_data['Close']) > 0 else 0
                if current_price > 100:  # 高价股
                    risk_score += 0.1
                elif current_price < 5:  # 低价股
                    risk_score += 0.2
        
        except Exception as e:
            logger.warning(f"风险评分计算失败 {symbol}: {e}")
        
        return min(1.0, max(0.0, risk_score))
    
    def _calculate_position_size(self, signal_strength: float, confidence: float, 
                               risk_score: float, strategy: GeneratedStrategy) -> float:
        """计算仓位大小"""
        base_position = 1.0 / strategy.parameters.max_positions
        
        # 信号强度调整
        strength_adjustment = abs(signal_strength)
        
        # 置信度调整
        confidence_adjustment = confidence
        
        # 风险调整
        risk_adjustment = 1.0 - risk_score
        
        # 综合仓位
        position_size = base_position * strength_adjustment * confidence_adjustment * risk_adjustment
        
        # 应用仓位限制
        max_position = strategy.parameters.max_single_position
        position_size = min(position_size, max_position)
        
        return position_size
    
    def _filter_and_rank_signals(self, signals: List[StrategySignal], 
                                strategy: GeneratedStrategy) -> List[StrategySignal]:
        """过滤和排序信号"""
        if not signals:
            return signals
        
        # 按信号强度×置信度排序
        signals.sort(key=lambda x: abs(x.signal_strength) * x.confidence, reverse=True)
        
        # 限制信号数量
        max_positions = strategy.parameters.max_positions
        signals = signals[:max_positions]
        
        # 确保最小持仓数量
        min_positions = strategy.parameters.min_positions
        if len(signals) < min_positions:
            logger.warning(f"生成的信号数量 {len(signals)} 少于最小持仓要求 {min_positions}")
        
        return signals
    
    def get_strategy_summary(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """获取策略摘要"""
        strategy = next((s for s in self.generated_strategies if s.strategy_id == strategy_id), None)
        if not strategy:
            return None
        
        return {
            "strategy_id": strategy.strategy_id,
            "strategy_name": strategy.strategy_name,
            "strategy_type": strategy.strategy_type.value,
            "generation_time": strategy.generation_time.isoformat(),
            "expected_return": strategy.expected_return,
            "expected_volatility": strategy.expected_volatility,
            "expected_sharpe": strategy.expected_sharpe,
            "selected_factors": strategy.selected_factors,
            "factor_count": len(strategy.selected_factors),
            "rebalance_frequency": strategy.parameters.rebalance_frequency.value,
            "max_positions": strategy.parameters.max_positions
        }
    
    def export_strategy(self, strategy_id: str, file_path: str) -> bool:
        """导出策略到文件"""
        try:
            strategy = next((s for s in self.generated_strategies if s.strategy_id == strategy_id), None)
            if not strategy:
                logger.error(f"未找到策略: {strategy_id}")
                return False
            
            # 构建可序列化的策略数据
            strategy_data = {
                "strategy_id": strategy.strategy_id,
                "strategy_name": strategy.strategy_name,
                "strategy_type": strategy.strategy_type.value,
                "parameters": {
                    "strategy_type": strategy.parameters.strategy_type.value,
                    "rebalance_frequency": strategy.parameters.rebalance_frequency.value,
                    "max_positions": strategy.parameters.max_positions,
                    "min_positions": strategy.parameters.min_positions,
                    "position_size_method": strategy.parameters.position_size_method,
                    "max_single_position": strategy.parameters.max_single_position,
                    "sector_concentration_limit": strategy.parameters.sector_concentration_limit,
                    "turnover_limit": strategy.parameters.turnover_limit,
                    "stop_loss_threshold": strategy.parameters.stop_loss_threshold,
                    "factor_score_threshold": strategy.parameters.factor_score_threshold,
                    "factor_decay_adjustment": strategy.parameters.factor_decay_adjustment,
                    "dynamic_factor_selection": strategy.parameters.dynamic_factor_selection,
                    "market_regime_adjustment": strategy.parameters.market_regime_adjustment,
                    "volatility_adjustment": strategy.parameters.volatility_adjustment
                },
                "selected_factors": strategy.selected_factors,
                "expected_return": strategy.expected_return,
                "expected_volatility": strategy.expected_volatility,
                "expected_sharpe": strategy.expected_sharpe,
                "max_drawdown_estimate": strategy.max_drawdown_estimate,
                "generation_time": strategy.generation_time.isoformat(),
                "model_version": strategy.model_version,
                "backtest_period": strategy.backtest_period,
                "signal_generation_logic": strategy.signal_generation_logic,
                "position_sizing_logic": strategy.position_sizing_logic,
                "risk_management_rules": strategy.risk_management_rules
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(strategy_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"策略已导出到: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"策略导出失败: {e}")
            return False

# 便捷函数
def generate_auto_strategy(symbols: List[str],
                         returns_data: Dict[str, pd.Series],
                         factor_data: Dict[str, Dict[str, List[FactorValue]]],
                         strategy_type: str = "multi_factor") -> GeneratedStrategy:
    """便捷的自动策略生成函数"""
    generator = AutoStrategyGenerator()
    
    # 设置策略参数
    strategy_params = StrategyParameters(
        strategy_type=StrategyType(strategy_type),
        rebalance_frequency=RebalanceFrequency.WEEKLY,
        max_positions=30,
        min_positions=10
    )
    
    return generator.generate_strategy(symbols, returns_data, factor_data, strategy_params)