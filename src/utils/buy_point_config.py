#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
买点优化配置管理器
从unified_config.json读取优化配置
"""

import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class BuyPointConfigManager:
    """买点优化配置管理器"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径，默认为 config/unified_config.json
        """
        if config_path is None:
            # 默认配置文件路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            config_path = os.path.join(project_root, 'config', 'unified_config.json')

        self.config_path = config_path
        self._config_cache = None
        self._last_modified = None

    def get_config(self) -> Dict[str, Any]:
        """
        获取买点优化配置

        Returns:
            Dict: 买点优化配置字典
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(self.config_path):
                logger.warning(f"配置文件不存在: {self.config_path}")
                return self._get_default_config()

            # 检查文件是否被修改
            current_modified = os.path.getmtime(self.config_path)
            if self._config_cache is None or self._last_modified != current_modified:
                self._load_config()
                self._last_modified = current_modified

            return self._config_cache.get('buy_point_optimization', {})

        except Exception as e:
            logger.error(f"读取配置失败: {e}")
            return self._get_default_config()

    def _load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config_cache = json.load(f)
            logger.debug("配置文件加载成功")

        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            self._config_cache = {}

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "enabled": True,
            "version": "1.0.0",
            "description": "买点优化配置 - 右侧交易优先，减少回调后等待时间",

            "signal_weights": {
                "right_side": 0.6,
                "left_side": 0.4,
                "description": "右侧交易（确认信号）权重60%，左侧交易（预测信号）权重40%"
            },

            "trend_confirmation": {
                "enabled": True,
                "min_gain_threshold": 0.015,
                "volume_multiplier": 1.3,
                "consecutive_up_days": 2,
                "ma_breakthrough_required": False,
                "description": "趋势确认参数 - 最小涨幅1.5%，成交量放大1.3倍，连续上涨2天"
            },

            "signal_types": {
                "right_side_signals": {
                    "breakthrough": 0.3,
                    "volume_surge": 0.25,
                    "ma_alignment": 0.2,
                    "momentum_confirm": 0.25,
                    "description": "右侧交易信号权重配置"
                },
                "left_side_signals": {
                    "oversold": 0.2,
                    "support_level": 0.15,
                    "undervalued": 0.15,
                    "contrarian": 0.1,
                    "description": "左侧交易信号权重配置"
                }
            },

            "position_sizing": {
                "base_position": 0.1,
                "max_position": 0.25,
                "min_position": 0.05,
                "right_side_bonus": 1.3,
                "trend_multiplier": {
                    "confirmed_uptrend": 1.4,
                    "early_uptrend": 1.1,
                    "consolidation": 0.8,
                    "weak_downtrend": 0.5,
                    "strong_downtrend": 0.3
                },
                "quality_multiplier": {
                    "excellent": 1.2,
                    "good": 1.1,
                    "general": 1.0,
                    "poor": 0.8
                },
                "description": "动态仓位管理配置"
            },

            "fallback_settings": {
                "enable_fallback": True,
                "fallback_confidence": 0.3,
                "description": "降级设置 - 优化功能异常时的处理"
            }
        }

    def is_enabled(self) -> bool:
        """检查优化功能是否启用"""
        config = self.get_config()
        return config.get('enabled', True)

    def get_signal_weights(self) -> Dict[str, float]:
        """获取信号权重配置"""
        return self.get_config().get('signal_weights', {"right_side": 0.6, "left_side": 0.4})

    def get_trend_confirmation_config(self) -> Dict[str, Any]:
        """获取趋势确认配置"""
        return self.get_config().get('trend_confirmation', {})

    def get_signal_type_weights(self) -> Dict[str, Dict[str, float]]:
        """获取信号类型权重配置"""
        return self.get_config().get('signal_types', {})

    def get_position_sizing_config(self) -> Dict[str, Any]:
        """获取仓位管理配置"""
        return self.get_config().get('position_sizing', {})

    def get_wait_time_thresholds(self) -> Dict[str, float]:
        """获取等待时间阈值配置"""
        wait_time_config = self.get_config().get('wait_time_warning', {})
        return {
            "long_wait_threshold": wait_time_config.get('long_wait_threshold', 7.0),
            "short_wait_threshold": wait_time_config.get('short_wait_threshold', 3.0)
        }

    def get_trend_status_multipliers(self) -> Dict[str, float]:
        """获取趋势状态乘数配置"""
        return self.get_config().get('trend_status_multipliers', {
            "confirmed_uptrend": 1.5,
            "early_uptrend": 1.2,
            "consolidation": 1.0,
            "weak_downtrend": 0.7,
            "strong_downtrend": 0.5
        })

    def get_decision_engine_config(self) -> Dict[str, Any]:
        """获取决策引擎配置"""
        return self.get_config().get('decision_engine', {
            "right_side_bonus_weights": {
                "trend_confirmed": 0.2,
                "right_side_signals": 0.15,
                "signal_quality": 0.1
            },
            "max_right_side_bonus": 0.3
        })

    def get_fallback_settings(self) -> Dict[str, Any]:
        """获取降级设置"""
        return self.get_config().get('fallback_settings', {
            "enable_fallback": True,
            "fallback_confidence": 0.3
        })

    def reload_config(self):
        """重新加载配置"""
        self._config_cache = None
        self._last_modified = None
        logger.info("配置缓存已清除，下次访问将重新加载")

    def validate_config(self) -> Dict[str, Any]:
        """验证配置有效性"""
        config = self.get_config()
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

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

# 全局配置管理器实例
_config_manager = None

def get_config_manager() -> BuyPointConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = BuyPointConfigManager()
    return _config_manager

def get_buy_point_config() -> Dict[str, Any]:
    """快捷获取买点优化配置"""
    return get_config_manager().get_config()

def is_optimization_enabled() -> bool:
    """快捷检查优化功能是否启用"""
    return get_config_manager().is_enabled()