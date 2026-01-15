# -*- coding: utf-8 -*-
"""
因子管理模块
统一管理所有AI增强因子的计算、存储、更新和验证
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Callable
import logging
from datetime import datetime, timedelta
import json
import pickle
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)

@dataclass
class FactorValue:
    """因子值数据结构"""
    symbol: str
    factor_name: str
    value: float
    timestamp: datetime
    confidence: float = 1.0  # 因子置信度
    raw_data: Optional[Dict] = None  # 原始计算数据
    metadata: Optional[Dict] = None  # 元数据

@dataclass
class FactorDefinition:
    """因子定义"""
    name: str
    category: str  # 'technical', 'fundamental', 'sentiment', 'alternative'
    description: str
    calculation_func: Callable
    dependencies: List[str] = None  # 依赖的数据字段
    update_frequency: str = 'daily'  # 'realtime', 'daily', 'weekly'
    lookback_days: int = 20  # 回望天数
    is_ai_enhanced: bool = True
    normalization: str = 'zscore'  # 'zscore', 'minmax', 'rank', 'none'

class BaseFactor(ABC):
    """因子基类"""
    
    def __init__(self, name: str, category: str, description: str):
        self.name = name
        self.category = category
        self.description = description
        self.dependencies = []
        self.lookback_days = 20
        
    @abstractmethod
    def calculate(self, data: Dict[str, pd.DataFrame], symbol: str, **kwargs) -> FactorValue:
        """计算因子值"""
        pass
    
    def validate_data(self, data: Dict[str, pd.DataFrame]) -> bool:
        """验证输入数据"""
        for dep in self.dependencies:
            if dep not in data:
                logger.warning(f"因子{self.name}缺少依赖数据: {dep}")
                return False
            if data[dep] is None:
                logger.debug(f"因子{self.name}的依赖数据{dep}为None，将使用降级模式")
                return False
            if hasattr(data[dep], 'empty') and data[dep].empty:
                logger.warning(f"因子{self.name}的依赖数据{dep}为空")
                return False
        return True

class FactorManager:
    """因子管理器（集成IC评估和自动优化）"""

    def __init__(self, cache_dir: str = "factor_cache", enable_auto_evaluation: bool = True):
        self.factors = {}  # 注册的因子
        self.cache_dir = cache_dir
        self.factor_values = {}  # 因子值缓存
        self.factor_history = {}  # 因子历史数据
        self.lock = threading.Lock()

        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)

        # 【新增】IC评估和自动优化
        self.enable_auto_evaluation = enable_auto_evaluation
        self.factor_weights = {}  # 因子权重 {factor_name: weight}
        self.disabled_factors = set()  # 已禁用的因子

        # 【新增】集成IC评估组件
        if enable_auto_evaluation:
            try:
                from src.factors.factor_ic_evaluator import FactorICEvaluator
                from src.factors.factor_data_collector import FactorDataCollector

                self.ic_evaluator = FactorICEvaluator(
                    cache_dir=os.path.join(cache_dir, "ic_evaluation")
                )
                self.data_collector = FactorDataCollector(
                    cache_dir=os.path.join(cache_dir, "factor_history")
                )

                # 尝试加载已有数据
                self.data_collector.load_from_disk()

                # 加载因子权重配置
                self._load_factor_weights()

                logger.info("✓ IC评估系统已启用（自动优化）")
            except ImportError as e:
                logger.warning(f"IC评估系统不可用: {e}")
                self.enable_auto_evaluation = False

        # 统计计数器
        self.analysis_count = 0  # 分析次数
        self.last_evaluation_date = None  # 上次评估日期

        logger.info(f"因子管理器初始化，缓存目录: {cache_dir}")
    
    def register_factor(self, factor: BaseFactor):
        """注册因子"""
        self.factors[factor.name] = factor
        logger.info(f"注册因子: {factor.name} ({factor.category})")
    
    def calculate_factor(self, factor_name: str, symbol: str, 
                        data: Dict[str, pd.DataFrame], **kwargs) -> Optional[FactorValue]:
        """计算单个因子"""
        if factor_name not in self.factors:
            logger.error(f"未找到因子: {factor_name}")
            return None
        
        factor = self.factors[factor_name]
        
        try:
            # 验证数据
            if not factor.validate_data(data):
                return None
            
            # 计算因子
            factor_value = factor.calculate(data, symbol, **kwargs)
            
            # 缓存结果
            with self.lock:
                cache_key = f"{symbol}_{factor_name}"
                self.factor_values[cache_key] = factor_value
                
                # 更新历史数据
                if cache_key not in self.factor_history:
                    self.factor_history[cache_key] = []
                self.factor_history[cache_key].append(factor_value)
                
                # 限制历史数据长度
                if len(self.factor_history[cache_key]) > 1000:
                    self.factor_history[cache_key] = self.factor_history[cache_key][-1000:]
            
            logger.debug(f"计算因子完成: {factor_name} = {factor_value.value:.4f}")
            return factor_value
            
        except Exception as e:
            logger.error(f"计算因子失败 {factor_name}: {e}")
            return None
    
    def calculate_all_factors(self, symbol: str, data: Dict[str, pd.DataFrame], 
                            categories: List[str] = None) -> Dict[str, FactorValue]:
        """计算所有因子或指定类别的因子"""
        results = {}
        
        # 筛选要计算的因子
        factors_to_calc = {}
        for name, factor in self.factors.items():
            if categories is None or factor.category in categories:
                factors_to_calc[name] = factor
        
        # 并发计算因子
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_name = {
                executor.submit(self.calculate_factor, name, symbol, data): name
                for name in factors_to_calc.keys()
            }
            
            for future in future_to_name:
                factor_name = future_to_name[future]
                try:
                    result = future.result(timeout=30)
                    if result:
                        results[factor_name] = result
                except Exception as e:
                    logger.error(f"并发计算因子失败 {factor_name}: {e}")
        
        logger.info(f"计算因子完成 {symbol}: {len(results)}/{len(factors_to_calc)} 个因子")
        return results
    
    def get_factor_value(self, symbol: str, factor_name: str) -> Optional[FactorValue]:
        """获取最新因子值"""
        cache_key = f"{symbol}_{factor_name}"
        return self.factor_values.get(cache_key)
    
    def get_factor_history(self, symbol: str, factor_name: str, 
                          days: int = 20) -> List[FactorValue]:
        """获取因子历史数据"""
        cache_key = f"{symbol}_{factor_name}"
        history = self.factor_history.get(cache_key, [])
        
        if days > 0:
            return history[-days:]
        return history
    
    def get_factor_matrix(self, symbols: List[str], factor_names: List[str] = None) -> pd.DataFrame:
        """获取因子矩阵（股票 x 因子）"""
        if factor_names is None:
            factor_names = list(self.factors.keys())
        
        matrix_data = []
        for symbol in symbols:
            row_data = {'symbol': symbol}
            for factor_name in factor_names:
                factor_value = self.get_factor_value(symbol, factor_name)
                row_data[factor_name] = factor_value.value if factor_value else np.nan
            matrix_data.append(row_data)
        
        return pd.DataFrame(matrix_data).set_index('symbol')
    
    def normalize_factors(self, factor_matrix: pd.DataFrame, 
                         method: str = 'zscore') -> pd.DataFrame:
        """因子标准化"""
        if method == 'zscore':
            return (factor_matrix - factor_matrix.mean()) / factor_matrix.std()
        elif method == 'minmax':
            return (factor_matrix - factor_matrix.min()) / (factor_matrix.max() - factor_matrix.min())
        elif method == 'rank':
            return factor_matrix.rank(pct=True)
        else:
            return factor_matrix
    
    def save_factors(self, filepath: str = None):
        """保存因子数据到文件"""
        if filepath is None:
            filepath = os.path.join(self.cache_dir, f"factors_{datetime.now().strftime('%Y%m%d')}.pkl")
        
        save_data = {
            'factor_values': self.factor_values,
            'factor_history': self.factor_history,
            'timestamp': datetime.now()
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(save_data, f)
        
        logger.info(f"因子数据已保存: {filepath}")
    
    def load_factors(self, filepath: str):
        """从文件加载因子数据"""
        try:
            with open(filepath, 'rb') as f:
                save_data = pickle.load(f)
            
            self.factor_values = save_data.get('factor_values', {})
            self.factor_history = save_data.get('factor_history', {})
            
            logger.info(f"因子数据已加载: {filepath}")
            
        except Exception as e:
            logger.error(f"加载因子数据失败: {e}")
    
    def get_factor_stats(self) -> Dict:
        """获取因子统计信息"""
        stats = {
            'total_factors': len(self.factors),
            'categories': {},
            'cached_values': len(self.factor_values),
            'history_entries': sum(len(h) for h in self.factor_history.values())
        }
        
        # 按类别统计
        for factor in self.factors.values():
            if factor.category not in stats['categories']:
                stats['categories'][factor.category] = 0
            stats['categories'][factor.category] += 1
        
        return stats
    
    def validate_factor_coverage(self, symbols: List[str], 
                               required_factors: List[str] = None) -> Dict:
        """验证因子覆盖率"""
        if required_factors is None:
            required_factors = list(self.factors.keys())
        
        coverage = {}
        for symbol in symbols:
            coverage[symbol] = {}
            for factor_name in required_factors:
                factor_value = self.get_factor_value(symbol, factor_name)
                coverage[symbol][factor_name] = factor_value is not None
        
        # 计算总体覆盖率
        total_checks = len(symbols) * len(required_factors)
        covered_checks = sum(
            1 for symbol_cov in coverage.values() 
            for is_covered in symbol_cov.values() 
            if is_covered
        )
        
        return {
            'coverage_detail': coverage,
            'overall_coverage': covered_checks / total_checks if total_checks > 0 else 0,
            'symbols_count': len(symbols),
            'factors_count': len(required_factors)
        }

    # ==================== 自动IC评估和优化相关方法 ====================

    def _load_factor_weights(self):
        """加载因子权重配置"""
        weight_file = os.path.join(self.cache_dir, "factor_weights.json")

        if os.path.exists(weight_file):
            try:
                with open(weight_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.factor_weights = data.get('weights', {})
                    self.disabled_factors = set(data.get('disabled', []))
                    logger.info(f"✓ 加载因子权重: {len(self.factor_weights)}个因子")
            except Exception as e:
                logger.error(f"加载因子权重失败: {e}")
                self._initialize_default_weights()
        else:
            self._initialize_default_weights()

    def _initialize_default_weights(self):
        """初始化默认权重（所有因子权重相等）"""
        for factor_name in self.factors.keys():
            self.factor_weights[factor_name] = 1.0
        logger.info("使用默认因子权重（均等）")

    def _save_factor_weights(self):
        """保存因子权重配置"""
        weight_file = os.path.join(self.cache_dir, "factor_weights.json")

        data = {
            'weights': self.factor_weights,
            'disabled': list(self.disabled_factors),
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        with open(weight_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def record_analysis_result(self, symbol: str, factor_values: Dict[str, FactorValue],
                              next_day_return: float = None):
        """
        记录分析结果（自动调用，用于IC计算）

        Args:
            symbol: 股票代码
            factor_values: 因子值字典
            next_day_return: 次日收益率（可选，后续补充）
        """
        if not self.enable_auto_evaluation:
            return

        # 记录因子值
        today = datetime.now().strftime('%Y-%m-%d')

        factor_dict = {
            name: fv.value
            for name, fv in factor_values.items()
        }

        self.data_collector.record_factor_values(today, symbol, factor_dict)

        # 记录收益率（如果有）
        if next_day_return is not None:
            self.data_collector.record_returns(today, symbol, next_day_return)

        # 增加分析计数
        self.analysis_count += 1

        # 定期触发自动评估
        if self.analysis_count % 50 == 0:  # 每50次分析
            self._check_and_auto_evaluate()

    def _check_and_auto_evaluate(self):
        """检查并执行自动评估"""
        # 检查数据是否足够
        summary = self.data_collector.get_summary()

        if summary['num_dates'] < 20:
            logger.debug(f"数据不足20天({summary['num_dates']}天)，跳过自动评估")
            return

        # 检查是否需要评估（距离上次评估>7天）
        today = datetime.now().date()

        if self.last_evaluation_date:
            days_since_last = (today - self.last_evaluation_date).days
            if days_since_last < 7:
                logger.debug(f"距离上次评估{days_since_last}天，跳过")
                return

        # 执行自动评估
        logger.info("\n" + "="*60)
        logger.info("🤖 触发自动因子评估")
        logger.info("="*60)

        self._auto_evaluate_and_optimize()

        # 更新评估日期
        self.last_evaluation_date = today

        # 保存数据
        self.data_collector.save_to_disk()

    def _auto_evaluate_and_optimize(self):
        """自动评估并优化因子"""
        # 1. 计算IC
        self._calculate_ic_for_all_factors()

        # 2. 评估因子
        factor_names = list(self.factors.keys())
        evaluation_results = {}

        for factor_name in factor_names:
            result = self.ic_evaluator.evaluate_factor(factor_name, window=40)
            evaluation_results[factor_name] = result

        # 3. 自动调整权重和淘汰因子
        self._auto_adjust_weights(evaluation_results)

        # 4. 打印结果摘要
        self._print_evaluation_summary(evaluation_results)

    def _calculate_ic_for_all_factors(self):
        """为所有因子计算IC"""
        dates = self.data_collector.get_available_dates()

        if len(dates) < 10:
            return

        calculated_count = 0

        for date in dates:
            returns = self.data_collector.get_returns_by_date(date)

            if not returns:
                continue

            for factor_name in self.factors.keys():
                factor_values = self.data_collector.get_factor_values_by_date(factor_name, date)

                if not factor_values:
                    continue

                # 计算IC
                ic = self.ic_evaluator.calculate_daily_ic(factor_values, returns, date)

                # 更新IC历史
                self.ic_evaluator.update_ic_history(factor_name, date, ic)

            calculated_count += 1

        logger.info(f"✓ 计算IC完成: {calculated_count}天")

    def _auto_adjust_weights(self, evaluation_results: Dict):
        """自动调整权重"""
        adjustments = []

        for factor_name, result in evaluation_results.items():
            if 'rating' not in result:
                continue

            rating = result['rating']
            recommendation = result['recommendation']

            old_weight = self.factor_weights.get(factor_name, 1.0)
            new_weight = old_weight

            # 根据评级调整权重
            if recommendation == 'eliminate' or recommendation == 'eliminate_immediately':
                # 淘汰
                self.disabled_factors.add(factor_name)
                new_weight = 0.0
                adjustments.append(f"  ❌ {factor_name}: 淘汰（{result['reason']}）")

            elif recommendation == 'downweight':
                # 降权
                new_weight = old_weight * 0.7
                adjustments.append(f"  ⬇️ {factor_name}: {old_weight:.2f} → {new_weight:.2f}")

            elif recommendation == 'upweight':
                # 提权
                new_weight = min(old_weight * 1.3, 2.0)  # 最大权重2.0
                adjustments.append(f"  ⬆️ {factor_name}: {old_weight:.2f} → {new_weight:.2f}")

            elif recommendation == 'keep':
                # 保持
                adjustments.append(f"  ✓ {factor_name}: 保持 {old_weight:.2f}")

            self.factor_weights[factor_name] = new_weight

        # 保存权重
        self._save_factor_weights()

        # 打印调整信息
        if adjustments:
            logger.info("\n📊 因子权重调整:")
            for adj in adjustments:
                logger.info(adj)

    def _print_evaluation_summary(self, results: Dict):
        """打印评估摘要"""
        ratings = {'A+': 0, 'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}

        for result in results.values():
            if 'rating' in result:
                rating = result['rating']
                if rating in ratings:
                    ratings[rating] += 1

        logger.info("\n📊 因子评级分布:")
        logger.info(f"  ⭐⭐⭐⭐⭐ A+: {ratings['A+']}个")
        logger.info(f"  ⭐⭐⭐⭐   A:  {ratings['A']}个")
        logger.info(f"  ⭐⭐⭐     B:  {ratings['B']}个")
        logger.info(f"  ⭐⭐       C:  {ratings['C']}个")
        logger.info(f"  ⭐         D:  {ratings['D']}个")
        logger.info(f"  ❌         F:  {ratings['F']}个")

    def calculate_weighted_signal(self, symbol: str, data: Dict[str, pd.DataFrame]) -> float:
        """
        计算加权因子信号（考虑IC评估的权重）

        Args:
            symbol: 股票代码
            data: 数据字典

        Returns:
            加权信号值 (-1到1之间)
        """
        # 计算所有因子
        factor_values = self.calculate_all_factors(symbol, data)

        if not factor_values:
            return 0.0

        # 【自动记录】记录因子值（用于后续IC计算）
        if self.enable_auto_evaluation:
            self.record_analysis_result(symbol, factor_values)

        # 加权计算
        weighted_sum = 0.0
        total_weight = 0.0

        for factor_name, factor_value in factor_values.items():
            # 跳过已禁用的因子
            if factor_name in self.disabled_factors:
                logger.debug(f"跳过已禁用因子: {factor_name}")
                continue

            # 获取权重
            weight = self.factor_weights.get(factor_name, 1.0)

            weighted_sum += factor_value.value * weight
            total_weight += weight

        # 归一化
        if total_weight > 0:
            final_signal = weighted_sum / total_weight
        else:
            final_signal = 0.0

        return final_signal

    def get_factor_health_summary(self) -> Dict:
        """
        获取因子健康状况摘要（供GUI显示）

        Returns:
            健康状况字典
        """
        if not self.enable_auto_evaluation:
            return {'status': 'disabled'}

        summary = {
            'enabled': True,
            'total_factors': len(self.factors),
            'disabled_factors': len(self.disabled_factors),
            'analysis_count': self.analysis_count,
            'data_days': self.data_collector.get_summary()['num_dates'],
            'last_evaluation': self.last_evaluation_date.strftime('%Y-%m-%d') if self.last_evaluation_date else 'Never',
            'factors': {}
        }

        # 获取每个因子的评级（如果有）
        for factor_name in self.factors.keys():
            stats = self.ic_evaluator.get_factor_stats(factor_name)

            if stats and 'rating' in stats:
                summary['factors'][factor_name] = {
                    'rating': stats['rating'],
                    'weight': self.factor_weights.get(factor_name, 1.0),
                    'disabled': factor_name in self.disabled_factors
                }
            else:
                summary['factors'][factor_name] = {
                    'rating': 'N/A',
                    'weight': self.factor_weights.get(factor_name, 1.0),
                    'disabled': factor_name in self.disabled_factors
                }

        return summary


# 全局因子管理器实例
_factor_manager = None

def get_factor_manager() -> FactorManager:
    """获取全局因子管理器实例"""
    global _factor_manager
    if _factor_manager is None:
        _factor_manager = FactorManager()
    return _factor_manager