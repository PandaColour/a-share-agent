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
                # 安全地转换context为字符串，避免特殊字符
                context_str = self._safe_json_dumps(context)
                messages.append({
                    "role": "system",
                    "content": f"你是一个专业的股票分析师。当前分析的股票信息：{context_str}"
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
                context_str = self._safe_json_dumps(context)
                full_prompt = f"股票信息：{context_str}\n\n{prompt}"
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

    def _safe_json_dumps(self, data: Dict) -> str:
        """安全地序列化JSON数据，处理特殊字符和编码问题"""
        try:
            # 清理并限制数据大小
            cleaned_data = self._clean_context_data(data)

            # 使用安全的JSON序列化
            json_str = json.dumps(cleaned_data,
                                ensure_ascii=True,  # 确保ASCII编码
                                separators=(',', ':'),  # 压缩格式
                                default=str)  # 处理无法序列化的对象

            # 限制长度避免请求过大
            if len(json_str) > 5000:
                return json_str[:5000] + "..."

            return json_str

        except Exception as e:
            logger.warning(f"JSON序列化失败，使用简化格式: {e}")
            # 降级为简单字符串表示
            return str(data)[:1000]

    def _clean_context_data(self, data: Dict) -> Dict:
        """清理context数据，移除可能引起问题的字段"""
        if not isinstance(data, dict):
            return {"data": str(data)[:500]}

        cleaned = {}
        for key, value in data.items():
            try:
                # 跳过过大的数据或复杂对象
                if isinstance(value, (list, tuple)) and len(value) > 50:
                    cleaned[key] = f"[{len(value)} items]"
                elif isinstance(value, dict) and len(str(value)) > 1000:
                    cleaned[key] = f"{{large_dict}}"
                elif isinstance(value, str) and len(value) > 500:
                    cleaned[key] = value[:500] + "..."
                else:
                    cleaned[key] = value
            except Exception:
                cleaned[key] = str(value)[:100]

        return cleaned

    def generate_response(self, prompt: str, context: Dict = None) -> str:
        """生成回应 - 用于辩论和对话场景"""
        # 复用现有的generate_analysis方法
        return self.generate_analysis(prompt, context)

    def is_available(self) -> bool:
        try:
            # 简单的健康检查
            response = requests.get(self.endpoint.replace("/chat/completions", "/health"))
            return response.status_code < 500
        except:
            # 如果没有健康检查端点，假设可用
            return True