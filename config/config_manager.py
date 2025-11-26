# -*- coding: utf-8 -*-
"""
统一配置管理器
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

class ConfigManager:
    """统一配置管理器"""
    
    def __init__(self, config_file: str = "config/unified_config.json"):
        """初始化配置管理器"""
        self.config_file = Path(config_file)
        self._config = None
        self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if not self.config_file.exists():
                raise FileNotFoundError(f"配置文件不存在: {self.config_file}")
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            
            # 应用环境变量覆盖
            self._apply_env_overrides()
            
            return self._config
            
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return {}
    
    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        # Tushare token
        tushare_token = os.getenv('TUSHARE_TOKEN')
        if tushare_token:
            if 'system_settings' in self._config and 'data_sources' in self._config['system_settings']:
                self._config['system_settings']['data_sources']['tushare']['token'] = tushare_token
        
        # 数据源配置
        primary_source = os.getenv('PRIMARY_DATA_SOURCE')
        if primary_source:
            if 'system_settings' in self._config and 'data_sources' in self._config['system_settings']:
                self._config['system_settings']['data_sources']['primary_source'] = primary_source
        
        # AI配置
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if openai_api_key:
            # 可以添加OpenAI配置覆盖逻辑
            pass
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点分割路径"""
        if not self._config:
            return default
        
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_system_config(self) -> Dict[str, Any]:
        """获取系统配置"""
        return self.get('system_settings', {})
    
    def get_analysis_config(self) -> Dict[str, Any]:
        """获取分析配置"""
        return self.get('analysis_settings', {})
    
    def get_backtest_config(self) -> Dict[str, Any]:
        """获取回测配置"""
        return self.get('backtest_settings', {})
    
    def get_data_source_config(self) -> Dict[str, Any]:
        """获取数据源配置"""
        return self.get('system_settings.data_sources', {})
    
    def get_ai_config(self) -> Dict[str, Any]:
        """获取AI配置"""
        return self.get('system_settings.ai_models', {})
    
    def get_execution_config(self) -> Dict[str, Any]:
        """获取执行配置"""
        return self.get('system_settings.execution', {})
    
    def get_max_workers(self) -> int:
        """获取最大线程数"""
        return self.get('system_settings.execution.max_workers', 3)
    
    def get_debate_rounds(self) -> int:
        """获取辩论轮次"""
        return self.get('system_settings.debate_settings.debate_rounds', 2)
    
    def get_price_limit_min(self) -> float:
        """获取价格限制"""
        return self.get('analysis_settings.filters.price_limit_min', 30.0)

    def get_price_limit_max(self) -> float:
        """获取价格限制"""
        return self.get('analysis_settings.filters.price_limit_max', 100000.0)
    
    def get_exclude_chinext(self) -> bool:
        """获取是否排除创业板股票"""
        return self.get('analysis_settings.filters.exclude_chinext', True)
    
    def get_primary_data_source(self) -> str:
        """获取主数据源"""
        return self.get('system_settings.data_sources.primary_source', 'akshare')
    
    def get_fallback_data_sources(self) -> list:
        """获取备用数据源"""
        return self.get('system_settings.data_sources.fallback_sources', ['tushare', 'yfinance'])

    # ========== 买点优化配置相关方法 ==========

    def get_buy_point_config(self) -> Dict[str, Any]:
        """获取买点优化配置"""
        return self.get('system_settings.buy_point_optimization', {})

    def is_buy_point_optimization_enabled(self) -> bool:
        """检查买点优化功能是否启用"""
        return self.get('system_settings.buy_point_optimization.enabled', True)

    def get_signal_weights(self) -> Dict[str, float]:
        """获取信号权重配置"""
        return self.get('system_settings.buy_point_optimization.signal_weights', {
            "right_side": 0.75,
            "left_side": 0.25
        })

    def get_trend_confirmation_config(self) -> Dict[str, Any]:
        """获取趋势确认配置"""
        return self.get('system_settings.buy_point_optimization.trend_confirmation', {})

    def get_signal_type_weights(self) -> Dict[str, Dict[str, float]]:
        """获取信号类型权重配置"""
        return self.get('system_settings.buy_point_optimization.signal_types', {})

    def get_position_sizing_config(self) -> Dict[str, Any]:
        """获取仓位管理配置"""
        return self.get('system_settings.buy_point_optimization.position_sizing', {})

    def get_wait_time_thresholds(self) -> Dict[str, float]:
        """获取等待时间阈值配置"""
        wait_time_config = self.get('system_settings.buy_point_optimization.wait_time_warning', {})
        return {
            "long_wait_threshold": wait_time_config.get('long_wait_threshold', 7.0),
            "short_wait_threshold": wait_time_config.get('short_wait_threshold', 3.0)
        }

    def get_trend_status_multipliers(self) -> Dict[str, float]:
        """获取趋势状态乘数配置"""
        return self.get('system_settings.buy_point_optimization.trend_status_multipliers', {
            "confirmed_uptrend": 1.5,
            "early_uptrend": 1.2,
            "consolidation": 1.0,
            "weak_downtrend": 0.7,
            "strong_downtrend": 0.5
        })

    def validate_buy_point_config(self) -> Dict[str, Any]:
        """验证买点优化配置有效性"""
        config = self.get_buy_point_config()
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        if not config:
            validation_result["errors"].append("买点优化配置不存在")
            validation_result["valid"] = False
            return validation_result

        try:
            # 检查必需字段
            required_fields = ['enabled', 'signal_weights', 'trend_confirmation']
            for field in required_fields:
                if field not in config:
                    validation_result["errors"].append(f"缺少必需字段: {field}")
                    validation_result["valid"] = False

            # 检查信号权重
            signal_weights = config.get('signal_weights', {})
            if 'right_side' in signal_weights and 'left_side' in signal_weights:
                total_weight = signal_weights['right_side'] + signal_weights['left_side']
                if abs(total_weight - 1.0) > 0.01:  # 允许1%的误差
                    validation_result["warnings"].append(f"信号权重总和不为1.0: {total_weight}")
            else:
                validation_result["errors"].append("信号权重配置不完整")
                validation_result["valid"] = False

            # 检查仓位配置
            position_config = config.get('position_sizing', {})
            required_position_fields = ['base_position', 'max_position', 'min_position']
            for field in required_position_fields:
                if field not in position_config:
                    validation_result["errors"].append(f"仓位配置缺少字段: {field}")
                    validation_result["valid"] = False

            # 检查仓位范围合理性
            if all(field in position_config for field in required_position_fields):
                base_pos = position_config['base_position']
                max_pos = position_config['max_position']
                min_pos = position_config['min_position']

                if not (min_pos <= base_pos <= max_pos):
                    validation_result["errors"].append("仓位大小配置不合理: min <= base <= max")
                    validation_result["valid"] = False

                if max_pos > 0.5:
                    validation_result["warnings"].append("最大仓位超过50%，风险较高")

        except Exception as e:
            validation_result["errors"].append(f"配置验证异常: {e}")
            validation_result["valid"] = False

        return validation_result

    # ========== 原有方法 ==========

    def save_config(self, config: Dict[str, Any] = None):
        """保存配置文件"""
        try:
            config_to_save = config or self._config
            if not config_to_save:
                return False
            
            # 确保目录存在
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def update_config(self, key: str, value: Any):
        """更新配置值"""
        if not self._config:
            return False
        
        keys = key.split('.')
        config = self._config
        
        # 导航到最后一级的父级
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置值
        config[keys[-1]] = value
        return True
    
    def is_valid(self) -> bool:
        """检查配置是否有效"""
        return self._config is not None and len(self._config) > 0

# 全局配置管理器实例
config_manager = ConfigManager()

def get_config() -> ConfigManager:
    """获取全局配置管理器"""
    return config_manager

# ========== 买点优化配置的便捷函数 ==========

def get_buy_point_config() -> Dict[str, Any]:
    """快捷获取买点优化配置"""
    return config_manager.get_buy_point_config()

def is_optimization_enabled() -> bool:
    """快捷检查优化功能是否启用"""
    return config_manager.is_buy_point_optimization_enabled()
