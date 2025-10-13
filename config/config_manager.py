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