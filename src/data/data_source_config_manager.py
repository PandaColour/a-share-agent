# -*- coding: utf-8 -*-
"""
数据源配置管理器
负责管理多数据源的配置和切换
"""

import os
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class DataSourceConfigManager:
    """数据源配置管理器"""
    
    def __init__(self, config_file: str = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径，如果为None则使用默认路径
        """
        self.config_file = config_file or self._get_default_config_path()
        self.config = self._load_config()
        
    def _get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / "config" / "data_source_config.json")
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        default_config = self._get_default_config()
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                
                # 合并配置
                if 'data_source_settings' in file_config:
                    default_config.update(file_config['data_source_settings'])
                    
                logger.info(f"已加载数据源配置: {self.config_file}")
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}，使用默认配置")
        else:
            logger.warning(f"配置文件不存在: {self.config_file}，使用默认配置")
        
        # 从环境变量覆盖配置
        self._override_from_env(default_config)
        
        return default_config
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "primary_source": "akshare",
            "fallback_sources": ["yfinance"],
            "akshare": {"enabled": True},
            "tushare": {"enabled": False, "token": ""},
            "yfinance": {"enabled": True}
        }
    
    def _override_from_env(self, config: Dict):
        """从环境变量覆盖配置"""
        # 主数据源
        primary_source = os.getenv('PRIMARY_DATA_SOURCE')
        if primary_source:
            config['primary_source'] = primary_source
            logger.info(f"从环境变量设置主数据源: {primary_source}")
        
        # 备用数据源
        fallback_sources = os.getenv('FALLBACK_DATA_SOURCES')
        if fallback_sources:
            config['fallback_sources'] = [s.strip() for s in fallback_sources.split(',')]
            logger.info(f"从环境变量设置备用数据源: {config['fallback_sources']}")
        
        # Tushare配置
        tushare_token = os.getenv('TUSHARE_TOKEN')
        tushare_enabled = os.getenv('TUSHARE_ENABLED', '').lower() in ['true', '1', 'yes', 'on']
        
        if tushare_token:
            config['tushare']['token'] = tushare_token
            config['tushare']['enabled'] = True
            logger.info("从环境变量获取Tushare配置")
        elif tushare_enabled:
            config['tushare']['enabled'] = tushare_enabled
        
        # 其他数据源开关
        for source in ['akshare', 'yfinance']:
            env_key = f"{source.upper()}_ENABLED"
            env_value = os.getenv(env_key, '').lower()
            if env_value in ['true', '1', 'yes', 'on']:
                config[source]['enabled'] = True
            elif env_value in ['false', '0', 'no', 'off']:
                config[source]['enabled'] = False
    
    def get_primary_source(self) -> str:
        """获取主数据源"""
        return self.config.get('primary_source', 'akshare')
    
    def get_fallback_sources(self) -> List[str]:
        """获取备用数据源列表"""
        return self.config.get('fallback_sources', ['yfinance'])
    
    def is_source_enabled(self, source_name: str) -> bool:
        """检查数据源是否启用"""
        source_config = self.config.get(source_name, {})
        return source_config.get('enabled', False)
    
    def get_tushare_token(self) -> Optional[str]:
        """获取Tushare token"""
        tushare_config = self.config.get('tushare', {})
        token = tushare_config.get('token', '')
        return token if token else None
    
    def get_enabled_sources(self) -> List[str]:
        """获取所有启用的数据源"""
        enabled_sources = []
        for source_name in ['akshare', 'tushare', 'yfinance']:
            if self.is_source_enabled(source_name):
                enabled_sources.append(source_name)
        return enabled_sources
    
    def get_data_provider_config(self) -> Dict:
        """获取数据提供者需要的配置"""
        return {
            'primary_source': self.get_primary_source(),
            'fallback_sources': self.get_fallback_sources(),
            'tushare': {
                'enabled': self.is_source_enabled('tushare'),
                'token': self.get_tushare_token()
            },
            'akshare': {
                'enabled': self.is_source_enabled('akshare')
            },
            'yfinance': {
                'enabled': self.is_source_enabled('yfinance')
            }
        }
    
    def set_primary_source(self, source_name: str):
        """设置主数据源"""
        if source_name in ['akshare', 'tushare', 'yfinance']:
            self.config['primary_source'] = source_name
            logger.info(f"已设置主数据源为: {source_name}")
        else:
            logger.error(f"不支持的数据源: {source_name}")
    
    def enable_source(self, source_name: str):
        """启用数据源"""
        if source_name in ['akshare', 'tushare', 'yfinance']:
            if source_name not in self.config:
                self.config[source_name] = {}
            self.config[source_name]['enabled'] = True
            logger.info(f"已启用数据源: {source_name}")
        else:
            logger.error(f"不支持的数据源: {source_name}")
    
    def disable_source(self, source_name: str):
        """禁用数据源"""
        if source_name in ['akshare', 'tushare', 'yfinance']:
            if source_name not in self.config:
                self.config[source_name] = {}
            self.config[source_name]['enabled'] = False
            logger.info(f"已禁用数据源: {source_name}")
        else:
            logger.error(f"不支持的数据源: {source_name}")
    
    def set_tushare_token(self, token: str):
        """设置Tushare token"""
        if 'tushare' not in self.config:
            self.config['tushare'] = {}
        self.config['tushare']['token'] = token
        self.config['tushare']['enabled'] = True
        logger.info("已设置Tushare token")
    
    def get_source_info(self, source_name: str) -> Dict:
        """获取数据源详细信息"""
        # 从完整配置文件中获取详细信息
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                full_config = json.load(f)
                
            source_info = full_config.get('data_source_settings', {}).get(source_name, {})
            
            # 添加当前状态
            source_info['enabled'] = self.is_source_enabled(source_name)
            
            if source_name == 'tushare':
                source_info['token_configured'] = bool(self.get_tushare_token())
            
            return source_info
            
        except Exception as e:
            logger.error(f"获取数据源信息失败: {e}")
            return {"enabled": self.is_source_enabled(source_name)}
    
    def get_usage_scenario_config(self, scenario: str) -> Dict:
        """根据使用场景获取推荐配置"""
        scenarios = {
            'development': {
                'primary_source': 'akshare',
                'fallback_sources': ['yfinance'],
                'description': '开发测试环境，使用免费数据源'
            },
            'production_free': {
                'primary_source': 'akshare',
                'fallback_sources': ['yfinance'],
                'description': '生产环境免费方案'
            },
            'production_professional': {
                'primary_source': 'tushare',
                'fallback_sources': ['akshare', 'yfinance'],
                'description': '生产环境专业方案，需要Tushare token'
            },
            'backtesting': {
                'primary_source': 'tushare',
                'fallback_sources': ['akshare'],
                'description': '回测专用，优先使用数据质量最高的Tushare'
            }
        }
        
        return scenarios.get(scenario, scenarios['development'])
    
    def apply_scenario_config(self, scenario: str):
        """应用场景配置"""
        scenario_config = self.get_usage_scenario_config(scenario)
        
        self.set_primary_source(scenario_config['primary_source'])
        self.config['fallback_sources'] = scenario_config['fallback_sources']
        
        logger.info(f"已应用场景配置: {scenario} - {scenario_config['description']}")
    
    def validate_config(self) -> Dict:
        """验证配置的有效性"""
        results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        primary_source = self.get_primary_source()
        
        # 检查主数据源是否启用
        if not self.is_source_enabled(primary_source):
            results['errors'].append(f"主数据源 {primary_source} 未启用")
            results['valid'] = False
        
        # 检查Tushare配置
        if self.is_source_enabled('tushare'):
            if not self.get_tushare_token():
                results['errors'].append("Tushare已启用但未配置token")
                results['valid'] = False
        
        # 检查是否至少有一个数据源可用
        enabled_sources = self.get_enabled_sources()
        if not enabled_sources:
            results['errors'].append("没有启用任何数据源")
            results['valid'] = False
        
        # 检查备用数据源
        fallback_sources = self.get_fallback_sources()
        for source in fallback_sources:
            if not self.is_source_enabled(source):
                results['warnings'].append(f"备用数据源 {source} 未启用")
        
        return results
    
    def get_status_report(self) -> Dict:
        """获取配置状态报告"""
        enabled_sources = self.get_enabled_sources()
        
        report = {
            'primary_source': self.get_primary_source(),
            'fallback_sources': self.get_fallback_sources(),
            'enabled_sources': enabled_sources,
            'total_sources': len(enabled_sources),
            'tushare_configured': bool(self.get_tushare_token()) if 'tushare' in enabled_sources else False,
            'validation': self.validate_config()
        }
        
        return report
    
    def save_config(self):
        """保存当前配置到文件"""
        try:
            # 确保目录存在
            config_dir = os.path.dirname(self.config_file)
            os.makedirs(config_dir, exist_ok=True)
            
            # 构建完整配置结构
            full_config = {
                'data_source_settings': self.config,
                'last_updated': datetime.now().isoformat(),
                'note': 'This file was automatically generated'
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(full_config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"配置已保存到: {self.config_file}")
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")


# 创建全局配置管理器实例
data_source_config_manager = DataSourceConfigManager()

def get_data_provider_config() -> Dict:
    """快捷函数：获取数据提供者配置"""
    return data_source_config_manager.get_data_provider_config()

def get_primary_data_source() -> str:
    """快捷函数：获取主数据源"""
    return data_source_config_manager.get_primary_source()