# -*- coding: utf-8 -*-
"""
统一配置管理器
"""

import json
import os
from typing import Dict, Any
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

            self._apply_env_overrides()

            return self._config

        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return {}

    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        tushare_token = os.getenv('TUSHARE_TOKEN')
        if tushare_token:
            if 'system_settings' in self._config and 'data_sources' in self._config['system_settings']:
                self._config['system_settings']['data_sources']['tushare']['token'] = tushare_token

        primary_source = os.getenv('PRIMARY_DATA_SOURCE')
        if primary_source:
            if 'system_settings' in self._config and 'data_sources' in self._config['system_settings']:
                self._config['system_settings']['data_sources']['primary_source'] = primary_source

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

    def get_max_workers(self) -> int:
        """获取最大线程数"""
        return self.get('system_settings.execution.max_workers', 3)

    def get_price_limit_min(self) -> float:
        """获取价格下限"""
        return self.get('analysis_settings.filters.price_limit_min', 30.0)

    def get_price_limit_max(self) -> float:
        """获取价格上限"""
        return self.get('analysis_settings.filters.price_limit_max', 100000.0)

    def get_exclude_chinext(self) -> bool:
        """获取是否排除创业板股票"""
        return self.get('analysis_settings.filters.exclude_chinext', True)

    def get_factor_system_config(self) -> Dict[str, Any]:
        """获取因子系统配置"""
        return self.get('system_settings.factor_system', {})

    def is_factor_auto_generation_enabled(self) -> bool:
        """生产默认关闭自动因子生成，仅研究模式允许启用"""
        factor_config = self.get_factor_system_config()
        mode = str(factor_config.get('mode', 'production')).lower()
        auto_enabled = bool(factor_config.get('auto_generation_enabled', False))
        return mode == 'research' and auto_enabled

    def get_include_intraday(self) -> bool:
        """获取是否拉取盘中5分钟数据，日批默认关闭"""
        return bool(self.get('system_settings.data_usage.include_intraday', False))

    def is_valid(self) -> bool:
        """检查配置是否有效"""
        return self._config is not None and len(self._config) > 0

# 全局配置管理器实例
config_manager = ConfigManager()

def get_config() -> ConfigManager:
    """获取全局配置管理器"""
    return config_manager
