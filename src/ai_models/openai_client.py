# -*- coding: utf-8 -*-
"""OpenAI API客户端"""

import os
import json
import requests
from typing import Dict, Any
import logging

from .base import AIModelInterface

logger = logging.getLogger(__name__)


class OpenAIClient(AIModelInterface):
    """OpenAI API客户端"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        self.model = config.get("model", "gpt-3.5-turbo")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.max_tokens = config.get("max_tokens", 1000)
        self.temperature = config.get("temperature", 0.7)

    def generate_analysis(self, prompt: str, context: Dict = None) -> str:
        if not self.is_available():
            return "OpenAI API不可用，请检查API密钥"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if context:
            messages.append({
                "role": "system",
                "content": f"你是一个专业的股票分析师。当前分析的股票信息：{json.dumps(context, ensure_ascii=False)}"
            })
        messages.append({"role": "user", "content": prompt})

        data = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        try:
            response = requests.post(f"{self.base_url}/chat/completions",
                                   headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"OpenAI API调用失败: {e}")
            return f"AI分析失败: {str(e)}"

    def is_available(self) -> bool:
        return bool(self.api_key)