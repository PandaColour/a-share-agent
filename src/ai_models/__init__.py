# -*- coding: utf-8 -*-
"""
AI模型模块
提供多种AI模型实现，支持不同的AI服务提供商
"""

from .base import AIModelInterface
from .openai_client import OpenAIClient
from .ollama_client import OllamaClient
from .custom_http_client import CustomHTTPClient
from .ml_prediction_client import MLPredictionClient
from .mock_client import MockAIClient
from .factory import AIModelFactory

__all__ = [
    'AIModelInterface',
    'OpenAIClient',
    'OllamaClient',
    'CustomHTTPClient',
    'MLPredictionClient',
    'MockAIClient',
    'AIModelFactory'
]