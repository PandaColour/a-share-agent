# -*- coding: utf-8 -*-
"""AI模型抽象基类"""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class AIModelInterface(ABC):
    """AI模型抽象接口"""

    @abstractmethod
    def generate_analysis(self, prompt: str, context: Dict = None) -> str:
        """生成分析结果"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查模型是否可用"""
        pass