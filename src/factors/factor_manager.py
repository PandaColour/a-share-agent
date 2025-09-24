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
            if dep not in data or data[dep].empty:
                logger.warning(f"因子{self.name}缺少依赖数据: {dep}")
                return False
        return True

class FactorManager:
    """因子管理器"""
    
    def __init__(self, cache_dir: str = "factor_cache"):
        self.factors = {}  # 注册的因子
        self.cache_dir = cache_dir
        self.factor_values = {}  # 因子值缓存
        self.factor_history = {}  # 因子历史数据
        self.lock = threading.Lock()
        
        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)
        
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


# 全局因子管理器实例
_factor_manager = None

def get_factor_manager() -> FactorManager:
    """获取全局因子管理器实例"""
    global _factor_manager
    if _factor_manager is None:
        _factor_manager = FactorManager()
    return _factor_manager