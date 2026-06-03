# -*- coding: utf-8 -*-
"""AI模型工厂类"""

from typing import Dict
import logging

from .base import AIModelInterface
from .openai_client import OpenAIClient
from .ollama_client import OllamaClient
from .custom_http_client import CustomHTTPClient
from .ml_prediction_client import MLPredictionClient
from .mock_client import MockAIClient
from .claude_sdk_client import ClaudeSDKClient

logger = logging.getLogger(__name__)


class AIModelFactory:
    """AI模型工厂类"""

    @staticmethod
    def create_model(model_name: str, models_config: Dict) -> AIModelInterface:
        """根据模型名称和配置创建AI模型实例"""
        if model_name not in models_config:
            raise ValueError(f"未找到模型配置: {model_name}")

        model_info = models_config[model_name]
        model_type = model_info.get("type", "mock")
        model_config = model_info.get("config", {})

        logger.info(f"创建AI模型: {model_name} ({model_info.get('name', 'Unknown')}) - 类型: {model_type}")

        if model_type == "openai":
            return OpenAIClient(model_config)
        elif model_type == "ollama":
            return OllamaClient(model_config)
        elif model_type == "custom_http":
            return CustomHTTPClient(model_config)
        elif model_type == "ml_prediction":
            return MLPredictionClient(model_config)
        elif model_type == "claude_sdk":
            return ClaudeSDKClient(model_config.get("config", {}))
        elif model_type == "mock":
            return MockAIClient(model_config)
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")

    @staticmethod
    def create_model_legacy(model_config: Dict) -> AIModelInterface:
        """兼容旧版配置格式的创建方法"""
        model_type = model_config.get("type", "mock")

        if model_type == "openai":
            return OpenAIClient(model_config)
        elif model_type == "ollama":
            return OllamaClient(model_config)
        elif model_type == "custom_http":
            return CustomHTTPClient(model_config)
        elif model_type == "ml_prediction":
            return MLPredictionClient(model_config)
        elif model_type == "claude_sdk":
            return ClaudeSDKClient(model_config.get("config", {}))
        elif model_type == "mock":
            return MockAIClient(model_config)
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")