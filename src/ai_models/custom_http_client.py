# -*- coding: utf-8 -*-
"""自定义HTTP API客户端"""

import json
import requests
from typing import Dict, Any
import logging

from .base import AIModelInterface

logger = logging.getLogger(__name__)


class CustomHTTPClient(AIModelInterface):
    """自定义HTTP API客户端"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.endpoint = config.get("endpoint", "")
        self.headers = config.get("headers", {"Content-Type": "application/json"})
        self.request_format = config.get("request_format", "openai")  # "openai" or "custom"
        self.model = config.get("model", "")
        self.max_tokens = config.get("max_tokens", 1000)
        self.temperature = config.get("temperature", 0.7)

    def generate_analysis(self, prompt: str, context: Dict = None) -> str:
        if not self.is_available():
            return "自定义API服务不可用"

        if self.request_format == "openai":
            # OpenAI兼容格式
            messages = []
            if context:
                messages.append({
                    "role": "system",
                    "content": f"你是一个专业的股票分析师。当前分析的股票信息：{json.dumps(context, ensure_ascii=False)}"
                })
            messages.append({"role": "user", "content": prompt})

            data = {
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            if self.model:
                data["model"] = self.model
        else:
            # 自定义格式
            full_prompt = prompt
            if context:
                full_prompt = f"股票信息：{json.dumps(context, ensure_ascii=False)}\n\n{prompt}"
            data = {
                "prompt": full_prompt,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            if self.model:
                data["model"] = self.model

        try:
            response = requests.post(self.endpoint,
                                   headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()

            # 尝试不同的响应格式
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0].get("message", {}).get("content", "")
            elif "response" in result:
                return result["response"]
            elif "text" in result:
                return result["text"]
            else:
                return str(result)

        except Exception as e:
            logger.error(f"自定义API调用失败: {e}")
            return f"AI分析失败: {str(e)}"

    def is_available(self) -> bool:
        try:
            # 简单的健康检查
            response = requests.get(self.endpoint.replace("/chat/completions", "/health"),
                                  timeout=5)
            return response.status_code < 500
        except:
            # 如果没有健康检查端点，假设可用
            return True