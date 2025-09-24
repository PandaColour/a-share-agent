# -*- coding: utf-8 -*-
"""Ollama本地模型客户端"""

import json
import requests
from typing import Dict, Any
import logging

from .base import AIModelInterface

logger = logging.getLogger(__name__)


class OllamaClient(AIModelInterface):
    """Ollama本地模型客户端"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = config.get("model", "llama2")
        self.host = config.get("host", "http://localhost:11434").rstrip('/')
        self.options = config.get("options", {})

    def generate_analysis(self, prompt: str, context: Dict = None) -> str:
        if not self.is_available():
            return "Ollama服务不可用，请检查是否启动"

        full_prompt = prompt
        if context:
            full_prompt = f"股票信息：{json.dumps(context, ensure_ascii=False)}\n\n{prompt}"

        data = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": self.options
        }

        # 设置默认选项
        if not self.options:
            data["options"] = {
                "temperature": 0.3,
                "num_predict": 500
            }

        try:
            response = requests.post(f"{self.host}/api/generate",
                                   json=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "未获取到响应")
        except Exception as e:
            logger.error(f"Ollama API调用失败: {e}")
            return f"AI分析失败: {str(e)}"

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False