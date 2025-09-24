# -*- coding: utf-8 -*-
"""
策略动态调整机制
根据市场状态、因子表现等动态调整策略参数
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

from .factor_manager import FactorValue, get_factor_manager
from .auto_strategy_generator import GeneratedStrategy, StrategySignal, StrategyParameters
from .auto_factor_selector import AutoFactorSelector, FactorPerformance
from .factor_weight_optimizer import FactorWeightOptimizer, OptimizationMethod

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """市场状态"""
    BULL_MARKET = "bull_market"        # 牛市
    BEAR_MARKET = "bear_market"        # 熊市
    SIDEWAYS = "sideways"              # 震荡市
    HIGH_VOLATILITY = "high_volatility"  # 高波动期
    LOW_VOLATILITY = "low_volatility"    # 低波动期
    UNKNOWN = "unknown"                # 未知状态

class AdjustmentTrigger(Enum):
    """调整触发条件"""
    PERIODIC = "periodic"                    # 定期调整
    PERFORMANCE_DEGRADATION = "perf_degrade"  # 表现恶化
    MARKET_REGIME_CHANGE = "market_change"   # 市场状态改变
    FACTOR_DECAY = "factor_decay"            # 因子失效
    VOLATILITY_SPIKE = "vol_spike"           # 波动率突增
    DRAWDOWN_LIMIT = "drawdown_limit"        # 回撤限制

@dataclass
class MarketMetrics:
    """市场指标"""
    market_return: float            # 市场收益率
    market_volatility: float        # 市场波动率
    vix_level: float               # 恐慌指数水平
    trend_strength: float          # 趋势强度
    correlation_breakdown: float   # 相关性崩溃指标
    sector_rotation: float         # 板块轮动强度
    
@dataclass
class StrategyPerformanceMetrics:
    """策略表现指标"""
    realized_return: float         # 实际收益率
    realized_volatility: float     # 实际波动率
    realized_sharpe: float         # 实际夏普比率
    max_drawdown: float           # 最大回撤
    hit_rate: float               # 胜率
    avg_holding_period: float     # 平均持仓周期
    turnover_rate: float          # 换手率
    information_ratio: float      # 信息比率

@dataclass
class AdjustmentDecision:
    """调整决策"""
    trigger: AdjustmentTrigger
    severity: float               # 调整严重程度 [0, 1]
    recommended_actions: List[str]
    parameter_changes: Dict[str, Any]
    confidence: float             # 决策置信度
    rationale: str               # 调整理由

class StrategyDynamicAdjuster:
    """策略动态调整器"""
    
    def __init__(self):
        self.factor_manager = get_factor_manager()
        self.factor_selector = AutoFactorSelector()
        self.weight_optimizer = FactorWeightOptimizer()
        
        # 调整历史
        self.adjustment_history = []
        
        # 市场状态历史
        self.market_regime_history = []
        
        # 表现跟踪
        self.performance_tracking = {}
    
    def monitor_and_adjust(self,
                          strategy: GeneratedStrategy,
                          current_data: Dict[str, Dict[str, Any]],
                          returns_data: Dict[str, pd.Series],
                          strategy_performance: StrategyPerformanceMetrics,
                          market_metrics: MarketMetrics) -> Optional[GeneratedStrategy]:
        """
        监控并调整策略
        
        Args:
            strategy: 当前策略
            current_data: 当前市场数据
            returns_data: 收益率数据
            strategy_performance: 策略表现指标
            market_metrics: 市场指标
            
        Returns:
            调整后的策略（如果需要调整）
        """
        logger.info(f"开始监控策略: {strategy.strategy_name}")
        
        try:
            # 1. 检测市场状态
            current_regime = self._detect_market_regime(market_metrics, returns_data)
            self.market_regime_history.append({
                'timestamp': datetime.now(),
                'regime': current_regime,
                'metrics': market_metrics
            })
            
            # 2. 评估调整需求
            adjustment_decisions = self._evaluate_adjustment_needs(
                strategy, strategy_performance, market_metrics, current_regime
            )
            
            if not adjustment_decisions:
                logger.info("策略表现正常，无需调整")
                return None
            
            # 3. 选择最重要的调整
            primary_decision = max(adjustment_decisions, key=lambda x: x.severity * x.confidence)
            
            logger.info(f"检测到调整需求: {primary_decision.trigger.value}, "
                       f"严重程度: {primary_decision.severity:.2f}")
            
            # 4. 执行策略调整
            adjusted_strategy = self._apply_adjustments(
                strategy, primary_decision, current_data, returns_data, current_regime
            )
            
            if adjusted_strategy:
                # 记录调整历史
                self.adjustment_history.append({
                    'timestamp': datetime.now(),
                    'original_strategy': strategy.strategy_id,
                    'adjusted_strategy': adjusted_strategy.strategy_id,
                    'decision': primary_decision,
                    'market_regime': current_regime
                })
                
                logger.info(f"策略调整完成: {adjusted_strategy.strategy_name}")
                return adjusted_strategy
            
            return None
            
        except Exception as e:
            logger.error(f"策略监控调整失败: {e}")
            return None
    
    def _detect_market_regime(self, 
                            market_metrics: MarketMetrics,
                            returns_data: Dict[str, pd.Series]) -> MarketRegime:
        """检测市场状态"""
        try:
            # 使用多个指标综合判断
            
            # 1. 基于收益率趋势
            if market_metrics.market_return > 0.15:  # 年化收益超过15%
                if market_metrics.market_volatility < 0.15:
                    return MarketRegime.BULL_MARKET
            elif market_metrics.market_return < -0.10:  # 年化收益低于-10%
                return MarketRegime.BEAR_MARKET
            
            # 2. 基于波动率
            if market_metrics.market_volatility > 0.25:  # 波动率超过25%
                return MarketRegime.HIGH_VOLATILITY
            elif market_metrics.market_volatility < 0.10:  # 波动率低于10%
                return MarketRegime.LOW_VOLATILITY
            
            # 3. 基于趋势强度
            if abs(market_metrics.trend_strength) < 0.3:  # 趋势强度弱
                return MarketRegime.SIDEWAYS
            
            # 4. 默认情况
            if len(self.market_regime_history) > 0:
                # 延续前一个状态
                return self.market_regime_history[-1]['regime']
            
            return MarketRegime.UNKNOWN
            
        except Exception as e:
            logger.warning(f"市场状态检测失败: {e}")
            return MarketRegime.UNKNOWN
    
    def _evaluate_adjustment_needs(self,
                                 strategy: GeneratedStrategy,
                                 performance: StrategyPerformanceMetrics,
                                 market_metrics: MarketMetrics,
                                 current_regime: MarketRegime) -> List[AdjustmentDecision]:
        """评估调整需求"""
        decisions = []
        
        try:
            # 1. 表现恶化检测
            perf_decision = self._check_performance_degradation(strategy, performance)
            if perf_decision:
                decisions.append(perf_decision)
            
            # 2. 市场状态变化检测
            regime_decision = self._check_market_regime_change(strategy, current_regime, market_metrics)
            if regime_decision:
                decisions.append(regime_decision)
            
            # 3. 因子失效检测
            factor_decision = self._check_factor_decay(strategy, performance)
            if factor_decision:
                decisions.append(factor_decision)
            
            # 4. 波动率突增检测
            vol_decision = self._check_volatility_spike(strategy, market_metrics, performance)
            if vol_decision:
                decisions.append(vol_decision)
            
            # 5. 回撤限制检测
            drawdown_decision = self._check_drawdown_limit(strategy, performance)
            if drawdown_decision:
                decisions.append(drawdown_decision)
            
            return decisions
            
        except Exception as e:
            logger.error(f"调整需求评估失败: {e}")
            return []
    
    def _check_performance_degradation(self, 
                                     strategy: GeneratedStrategy,
                                     performance: StrategyPerformanceMetrics) -> Optional[AdjustmentDecision]:
        """检查表现恶化"""
        # 比较实际表现与预期表现
        return_gap = strategy.expected_return - performance.realized_return
        sharpe_gap = strategy.expected_sharpe - performance.realized_sharpe
        
        # 设定阈值
        return_threshold = 0.05  # 收益率差距5%
        sharpe_threshold = 0.3   # 夏普比率差距0.3
        
        if return_gap > return_threshold or sharpe_gap > sharpe_threshold:
            severity = min(1.0, (return_gap / return_threshold + sharpe_gap / sharpe_threshold) / 2)
            
            return AdjustmentDecision(
                trigger=AdjustmentTrigger.PERFORMANCE_DEGRADATION,
                severity=severity,
                recommended_actions=[
                    "重新选择因子",
                    "调整因子权重",
                    "降低风险暴露"
                ],
                parameter_changes={
                    "factor_score_threshold": strategy.parameters.factor_score_threshold * 1.1,
                    "max_single_position": strategy.parameters.max_single_position * 0.9
                },
                confidence=0.8,
                rationale=f"实际收益率({performance.realized_return:.4f})与预期({strategy.expected_return:.4f})差距{return_gap:.4f}，"
                         f"实际夏普比率({performance.realized_sharpe:.4f})与预期({strategy.expected_sharpe:.4f})差距{sharpe_gap:.4f}"
            )
        
        return None
    
    def _check_market_regime_change(self,
                                  strategy: GeneratedStrategy,
                                  current_regime: MarketRegime,
                                  market_metrics: MarketMetrics) -> Optional[AdjustmentDecision]:
        """检查市场状态变化"""
        if len(self.market_regime_history) < 3:
            return None
        
        # 获取最近的市场状态
        recent_regimes = [h['regime'] for h in self.market_regime_history[-3:]]
        
        # 检测状态变化
        if len(set(recent_regimes)) > 1 and recent_regimes[-1] != recent_regimes[0]:
            # 根据新的市场状态调整策略参数
            adjustments = self._get_regime_based_adjustments(current_regime)
            
            if adjustments:
                return AdjustmentDecision(
                    trigger=AdjustmentTrigger.MARKET_REGIME_CHANGE,
                    severity=0.7,
                    recommended_actions=adjustments['actions'],
                    parameter_changes=adjustments['parameters'],
                    confidence=0.7,
                    rationale=f"市场状态从 {recent_regimes[0].value} 转变为 {current_regime.value}"
                )
        
        return None
    
    def _check_factor_decay(self,
                          strategy: GeneratedStrategy,
                          performance: StrategyPerformanceMetrics) -> Optional[AdjustmentDecision]:
        """检查因子失效"""
        # 基于信息比率和胜率判断因子是否失效
        ir_threshold = 0.5
        hit_rate_threshold = 0.45
        
        if (performance.information_ratio < ir_threshold and 
            performance.hit_rate < hit_rate_threshold):
            
            severity = 1.0 - min(performance.information_ratio / ir_threshold, 
                               performance.hit_rate / hit_rate_threshold)
            
            return AdjustmentDecision(
                trigger=AdjustmentTrigger.FACTOR_DECAY,
                severity=severity,
                recommended_actions=[
                    "重新选择有效因子",
                    "增加新的因子类型",
                    "调整因子权重分配"
                ],
                parameter_changes={
                    "dynamic_factor_selection": True,
                    "factor_decay_adjustment": True
                },
                confidence=0.8,
                rationale=f"信息比率({performance.information_ratio:.4f})和胜率({performance.hit_rate:.4f})都低于阈值"
            )
        
        return None
    
    def _check_volatility_spike(self,
                              strategy: GeneratedStrategy,
                              market_metrics: MarketMetrics,
                              performance: StrategyPerformanceMetrics) -> Optional[AdjustmentDecision]:
        """检查波动率突增"""
        expected_vol = strategy.expected_volatility
        actual_vol = performance.realized_volatility
        market_vol = market_metrics.market_volatility
        
        # 如果实际波动率显著高于预期，或市场波动率很高
        vol_spike_threshold = 1.5  # 波动率增加50%以上
        market_vol_threshold = 0.3  # 市场波动率30%以上
        
        if (actual_vol > expected_vol * vol_spike_threshold or 
            market_vol > market_vol_threshold):
            
            severity = min(1.0, max(actual_vol / (expected_vol * vol_spike_threshold),
                                  market_vol / market_vol_threshold))
            
            return AdjustmentDecision(
                trigger=AdjustmentTrigger.VOLATILITY_SPIKE,
                severity=severity,
                recommended_actions=[
                    "降低单只股票权重",
                    "增加分散化程度",
                    "启用波动率调整机制"
                ],
                parameter_changes={
                    "max_single_position": strategy.parameters.max_single_position * 0.8,
                    "volatility_adjustment": True,
                    "max_positions": min(strategy.parameters.max_positions + 10, 100)
                },
                confidence=0.9,
                rationale=f"波动率从预期{expected_vol:.4f}上升到{actual_vol:.4f}，市场波动率{market_vol:.4f}"
            )
        
        return None
    
    def _check_drawdown_limit(self,
                            strategy: GeneratedStrategy,
                            performance: StrategyPerformanceMetrics) -> Optional[AdjustmentDecision]:
        """检查回撤限制"""
        max_allowed_drawdown = 0.15  # 最大允许回撤15%
        
        if performance.max_drawdown > max_allowed_drawdown:
            severity = min(1.0, performance.max_drawdown / max_allowed_drawdown)
            
            return AdjustmentDecision(
                trigger=AdjustmentTrigger.DRAWDOWN_LIMIT,
                severity=severity,
                recommended_actions=[
                    "启用止损机制",
                    "降低风险暴露",
                    "增加防守性因子"
                ],
                parameter_changes={
                    "stop_loss_threshold": max(strategy.parameters.stop_loss_threshold, -0.08),
                    "max_single_position": strategy.parameters.max_single_position * 0.7,
                    "risk_tolerance": 0.01
                },
                confidence=0.95,
                rationale=f"最大回撤({performance.max_drawdown:.4f})超过限制({max_allowed_drawdown:.4f})"
            )
        
        return None
    
    def _get_regime_based_adjustments(self, regime: MarketRegime) -> Optional[Dict[str, Any]]:
        """根据市场状态获取调整方案"""
        adjustments = {
            MarketRegime.BULL_MARKET: {
                'actions': ["增加成长性因子权重", "提高仓位上限"],
                'parameters': {
                    'max_single_position': 0.12,
                    'sector_concentration_limit': 0.35,
                    'rebalance_frequency': 'monthly'
                }
            },
            MarketRegime.BEAR_MARKET: {
                'actions': ["增加价值因子权重", "启用止损机制", "降低仓位"],
                'parameters': {
                    'max_single_position': 0.06,
                    'stop_loss_threshold': -0.08,
                    'max_positions': 30
                }
            },
            MarketRegime.HIGH_VOLATILITY: {
                'actions': ["启用波动率调整", "增加分散化", "缩短调仓周期"],
                'parameters': {
                    'volatility_adjustment': True,
                    'max_positions': 60,
                    'rebalance_frequency': 'weekly'
                }
            },
            MarketRegime.LOW_VOLATILITY: {
                'actions': ["适当集中持仓", "延长调仓周期"],
                'parameters': {
                    'max_single_position': 0.15,
                    'max_positions': 25,
                    'rebalance_frequency': 'monthly'
                }
            },
            MarketRegime.SIDEWAYS: {
                'actions': ["增加均值回归因子", "提高换手限制"],
                'parameters': {
                    'turnover_limit': 0.3,
                    'factor_score_threshold': 0.6
                }
            }
        }
        
        return adjustments.get(regime)
    
    def _apply_adjustments(self,
                         original_strategy: GeneratedStrategy,
                         decision: AdjustmentDecision,
                         current_data: Dict[str, Dict[str, Any]],
                         returns_data: Dict[str, pd.Series],
                         current_regime: MarketRegime) -> Optional[GeneratedStrategy]:
        """应用调整决策"""
        try:
            # 1. 更新策略参数
            new_params = self._update_strategy_parameters(original_strategy.parameters, decision)
            
            # 2. 重新选择因子（如果需要）
            if decision.trigger in [AdjustmentTrigger.FACTOR_DECAY, AdjustmentTrigger.PERFORMANCE_DEGRADATION]:
                # 重新进行因子选择
                symbols = list(returns_data.keys())
                factor_data = self._rebuild_factor_data(symbols, current_data)
                
                if factor_data:
                    # 重新生成策略
                    from .auto_strategy_generator import AutoStrategyGenerator
                    generator = AutoStrategyGenerator()
                    
                    adjusted_strategy = generator.generate_strategy(
                        symbols, returns_data, factor_data, new_params
                    )
                    
                    # 更新策略名称以反映调整
                    adjusted_strategy.strategy_name = f"{original_strategy.strategy_name}_adjusted_{decision.trigger.value}"
                    
                    return adjusted_strategy
            
            # 3. 仅更新参数（不重新选择因子）
            else:
                # 复制原策略并更新参数
                adjusted_strategy = self._create_adjusted_strategy(original_strategy, new_params, decision)
                return adjusted_strategy
                
        except Exception as e:
            logger.error(f"应用调整失败: {e}")
            return None
    
    def _update_strategy_parameters(self, 
                                  original_params: StrategyParameters,
                                  decision: AdjustmentDecision) -> StrategyParameters:
        """更新策略参数"""
        # 复制原参数
        new_params = StrategyParameters(
            strategy_type=original_params.strategy_type,
            rebalance_frequency=original_params.rebalance_frequency,
            max_positions=original_params.max_positions,
            min_positions=original_params.min_positions,
            position_size_method=original_params.position_size_method,
            max_single_position=original_params.max_single_position,
            sector_concentration_limit=original_params.sector_concentration_limit,
            turnover_limit=original_params.turnover_limit,
            stop_loss_threshold=original_params.stop_loss_threshold,
            factor_score_threshold=original_params.factor_score_threshold,
            factor_decay_adjustment=original_params.factor_decay_adjustment,
            dynamic_factor_selection=original_params.dynamic_factor_selection,
            market_regime_adjustment=original_params.market_regime_adjustment,
            volatility_adjustment=original_params.volatility_adjustment
        )
        
        # 应用调整参数
        for param_name, param_value in decision.parameter_changes.items():
            if hasattr(new_params, param_name):
                setattr(new_params, param_name, param_value)
        
        return new_params
    
    def _rebuild_factor_data(self, 
                           symbols: List[str],
                           current_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, List[FactorValue]]]:
        """重新构建因子数据"""
        try:
            factor_data = {}
            
            for symbol in symbols:
                if symbol in current_data:
                    symbol_data = current_data[symbol]
                    
                    # 计算所有因子
                    factors = self.factor_manager.calculate_all_factors(symbol, symbol_data)
                    
                    if factors:
                        factor_data[symbol] = {}
                        for factor_name, factor_value in factors.items():
                            factor_data[symbol][factor_name] = [factor_value]
            
            return factor_data
            
        except Exception as e:
            logger.error(f"重建因子数据失败: {e}")
            return {}
    
    def _create_adjusted_strategy(self,
                                original_strategy: GeneratedStrategy,
                                new_params: StrategyParameters,
                                decision: AdjustmentDecision) -> GeneratedStrategy:
        """创建调整后的策略"""
        # 生成新的策略ID
        new_strategy_id = f"{original_strategy.strategy_id}_adj_{datetime.now().strftime('%H%M%S')}"
        new_strategy_name = f"{original_strategy.strategy_name}_adjusted"
        
        # 创建调整后的策略
        adjusted_strategy = GeneratedStrategy(
            strategy_id=new_strategy_id,
            strategy_name=new_strategy_name,
            strategy_type=new_params.strategy_type,
            parameters=new_params,
            selected_factors=original_strategy.selected_factors,
            factor_performances=original_strategy.factor_performances,
            optimization_result=original_strategy.optimization_result,
            expected_return=original_strategy.expected_return,
            expected_volatility=original_strategy.expected_volatility,
            expected_sharpe=original_strategy.expected_sharpe,
            max_drawdown_estimate=original_strategy.max_drawdown_estimate,
            generation_time=datetime.now(),
            model_version=original_strategy.model_version,
            backtest_period=original_strategy.backtest_period,
            signal_generation_logic=original_strategy.signal_generation_logic,
            position_sizing_logic=original_strategy.position_sizing_logic,
            risk_management_rules=original_strategy.risk_management_rules + 
                                [f"调整原因: {decision.rationale}"]
        )
        
        return adjusted_strategy
    
    def get_adjustment_history(self) -> List[Dict[str, Any]]:
        """获取调整历史"""
        return self.adjustment_history.copy()
    
    def get_market_regime_history(self) -> List[Dict[str, Any]]:
        """获取市场状态历史"""
        return self.market_regime_history.copy()
    
    def analyze_adjustment_effectiveness(self, 
                                       original_strategy_id: str,
                                       adjusted_strategy_id: str,
                                       performance_comparison: Dict[str, Any]) -> Dict[str, Any]:
        """分析调整效果"""
        try:
            # 找到相关的调整记录
            adjustment_record = None
            for record in self.adjustment_history:
                if (record['original_strategy'] == original_strategy_id and 
                    record['adjusted_strategy'] == adjusted_strategy_id):
                    adjustment_record = record
                    break
            
            if not adjustment_record:
                return {"error": "未找到调整记录"}
            
            # 计算改进指标
            improvement_metrics = {}
            for metric, values in performance_comparison.items():
                if isinstance(values, dict) and 'before' in values and 'after' in values:
                    before = values['before']
                    after = values['after']
                    
                    if before != 0:
                        improvement = (after - before) / abs(before)
                        improvement_metrics[metric] = {
                            'before': before,
                            'after': after,
                            'improvement': improvement,
                            'improvement_percentage': improvement * 100
                        }
            
            return {
                'adjustment_timestamp': adjustment_record['timestamp'],
                'trigger': adjustment_record['decision'].trigger.value,
                'severity': adjustment_record['decision'].severity,
                'market_regime': adjustment_record['market_regime'].value,
                'improvement_metrics': improvement_metrics,
                'overall_effectiveness': np.mean([m['improvement'] for m in improvement_metrics.values()])
            }
            
        except Exception as e:
            logger.error(f"调整效果分析失败: {e}")
            return {"error": str(e)}

# 便捷函数
def create_market_metrics(market_data: Dict[str, Any]) -> MarketMetrics:
    """创建市场指标对象的便捷函数"""
    return MarketMetrics(
        market_return=market_data.get('market_return', 0.0),
        market_volatility=market_data.get('market_volatility', 0.15),
        vix_level=market_data.get('vix_level', 20.0),
        trend_strength=market_data.get('trend_strength', 0.0),
        correlation_breakdown=market_data.get('correlation_breakdown', 0.0),
        sector_rotation=market_data.get('sector_rotation', 0.0)
    )

def create_performance_metrics(performance_data: Dict[str, Any]) -> StrategyPerformanceMetrics:
    """创建策略表现指标对象的便捷函数"""
    return StrategyPerformanceMetrics(
        realized_return=performance_data.get('realized_return', 0.0),
        realized_volatility=performance_data.get('realized_volatility', 0.0),
        realized_sharpe=performance_data.get('realized_sharpe', 0.0),
        max_drawdown=performance_data.get('max_drawdown', 0.0),
        hit_rate=performance_data.get('hit_rate', 0.5),
        avg_holding_period=performance_data.get('avg_holding_period', 7.0),
        turnover_rate=performance_data.get('turnover_rate', 0.0),
        information_ratio=performance_data.get('information_ratio', 0.0)
    )