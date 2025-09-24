# -*- coding: utf-8 -*-
"""分析师基类 - 提取所有分析师的公共逻辑"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
import sys
import os
from abc import ABC, abstractmethod

# 添加src路径到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from ..ai_models import AIModelFactory
except ImportError:
    # 当作为脚本直接运行时使用绝对导入
    from ai_models import AIModelFactory
# 修复: 使用统一配置管理器而不是旧的config系统
import sys
import os
config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config')
sys.path.insert(0, config_dir)
from config_manager import get_config

logger = logging.getLogger(__name__)

class BaseAnalyst(ABC):
    """分析师基类，提取所有分析师的公共功能"""

    def __init__(self, agent_type: str):
        """
        初始化分析师基类

        Args:
            agent_type: 分析师类型 ('fundamental', 'technical', 'sentiment')
        """
        self.agent_type = agent_type
        self.ai_model = None
        self.config_manager = get_config()
        self.init_ai_model()

    def init_ai_model(self):
        """初始化AI模型 - 所有分析师通用逻辑"""
        try:
            # 使用统一配置管理器检查AI分析是否启用
            ai_config = self.config_manager.get_ai_config()
            if ai_config.get('enable_ai_analysis', False):
                # 获取分析师分配的模型
                analyst_assignments = ai_config.get('analyst_assignments', {})
                model_name = analyst_assignments.get(self.agent_type, ai_config.get('default_model', 'mock_model'))

                # 获取模型配置
                models_config = ai_config.get('models', {})
                model_info = models_config.get(model_name, {})

                if model_info:
                    self.ai_model = AIModelFactory.create_model(model_name, models_config)
                    analyst_type_cn = self._get_analyst_type_cn()
                    logger.info(f"{analyst_type_cn}已加载AI模型: {model_info.get('name')} ({model_info.get('type')})")
                else:
                    logger.warning(f"未找到模型配置: {model_name}")
                    self.ai_model = None
            else:
                logger.info("AI分析已禁用，使用传统分析方法")
        except Exception as e:
            logger.error(f"AI模型初始化失败: {e}")
            self.ai_model = None

    def _get_analyst_type_cn(self) -> str:
        """获取分析师类型的中文名称"""
        type_mapping = {
            'fundamental': '基本面分析师',
            'technical': '技术面分析师',
            'sentiment': '情感面分析师'
        }
        return type_mapping.get(self.agent_type, f'{self.agent_type}分析师')

    def analyze(self, symbol: str, data: pd.DataFrame, info: Dict, indicators: Dict) -> Dict:
        """
        分析入口方法 - 所有分析师通用流程

        Args:
            symbol: 股票代码
            data: 价格数据
            info: 股票信息
            indicators: 技术指标

        Returns:
            分析结果字典
        """
        # 首先进行传统分析
        analysis = self._traditional_analysis(symbol, data, info, indicators)

        # 如果启用了AI分析且模型可用，进行AI增强分析
        ai_config = self.config_manager.get_ai_config()
        if (self.ai_model and self.ai_model.is_available() and
            ai_config.get('enable_ai_analysis', False)):
            try:
                ai_analysis = self._ai_analysis(symbol, data, info, indicators, analysis)
                analysis.update(ai_analysis)
                analysis["reasoning"].append("已使用AI增强分析")
            except Exception as e:
                logger.error(f"AI分析失败: {e}")
                # 直接标记AI分析失败，不降级
                analysis = self._create_ai_failure_response(str(e))

        return analysis

    def _create_ai_failure_response(self, error_msg: str) -> Dict:
        """创建AI分析失败时的响应"""
        analyst_type_cn = self._get_analyst_type_cn()
        return {
            "analyst_type": analyst_type_cn.replace("分析师", "分析"),
            "recommendation": "无法分析",
            "confidence": 0.0,
            "reasoning": [f"AI增强分析失败: {error_msg}", "建议检查AI模型配置或网络连接"]
        }

    def _extract_ai_recommendation(self, ai_response: str) -> str:
        """从AI响应中提取投资建议 - 通用逻辑"""
        ai_lower = ai_response.lower()
        if "买入" in ai_response or "buy" in ai_lower:
            return "买入"
        elif "卖出" in ai_response or "sell" in ai_lower:
            return "卖出"
        else:
            return "持有"

    def _combine_traditional_and_ai_analysis(self, traditional_analysis: Dict,
                                           ai_recommendation: str, ai_reasoning: str) -> Dict:
        """合并传统分析和AI分析结果 - 通用逻辑"""
        enhanced_analysis = {}

        # 添加AI分析信息
        enhanced_analysis["ai_recommendation"] = ai_recommendation
        enhanced_analysis["ai_reasoning"] = ai_reasoning[:200] + "..." if len(ai_reasoning) > 200 else ai_reasoning

        # 综合传统分析和AI分析的结果
        if ai_recommendation == traditional_analysis["recommendation"]:
            # AI和传统分析一致，提高信心度
            enhanced_analysis["confidence"] = min(0.9, traditional_analysis["confidence"] + 0.1)
            enhanced_analysis["recommendation"] = traditional_analysis["recommendation"]
        else:
            # AI和传统分析结果不一致，降低信心度
            enhanced_analysis["confidence"] = max(0.3, traditional_analysis["confidence"] - 0.1)
            enhanced_analysis["recommendation"] = traditional_analysis["recommendation"]  # 优先使用传统分析结果

        return enhanced_analysis

    def _get_ai_prompt_config(self) -> Dict:
        """获取AI分析的提示词配置"""
        return self.config_manager.get(f"system_settings.analysis_prompts.{self.agent_type}", {
            "system_prompt": f"你是一个专业的{self._get_analyst_type_cn()}",
            "user_prompt": "请分析这只股票"
        })

    def _ensure_confidence_range(self, confidence: float) -> float:
        """确保信心度在合理范围内 [0.1, 0.9]"""
        return max(0.1, min(0.9, confidence))

    def _create_default_analysis_result(self, reason: str = "数据不足") -> Dict:
        """创建默认分析结果"""
        analyst_type_cn = self._get_analyst_type_cn()
        return {
            "analyst_type": analyst_type_cn.replace("分析师", "分析"),
            "recommendation": "持有",
            "confidence": 0.5,
            "reasoning": [reason]
        }

    @abstractmethod
    def _traditional_analysis(self, symbol: str, data: pd.DataFrame,
                            info: Dict, indicators: Dict) -> Dict:
        """
        传统分析方法 - 子类必须实现

        Args:
            symbol: 股票代码
            data: 价格数据
            info: 股票信息
            indicators: 技术指标

        Returns:
            传统分析结果字典
        """
        pass

    @abstractmethod
    def _ai_analysis(self, symbol: str, data: pd.DataFrame, info: Dict,
                    indicators: Dict, traditional_analysis: Dict) -> Dict:
        """
        AI增强分析方法 - 子类必须实现

        Args:
            symbol: 股票代码
            data: 价格数据
            info: 股票信息
            indicators: 技术指标
            traditional_analysis: 传统分析结果

        Returns:
            AI增强分析结果字典
        """
        pass