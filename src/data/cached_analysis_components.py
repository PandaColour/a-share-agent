# -*- coding: utf-8 -*-
"""
缓存数据分析组件
专门用于第二阶段多线程分析的轻量级组件集合，不包含数据提供者初始化
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class CachedAnalysisComponents:
    """
    用于缓存数据分析的轻量级组件集合

    这个类专门为多线程分析阶段设计，只创建分析相关的组件，
    不初始化任何数据提供者或外部连接，避免重复初始化和资源浪费。
    """

    def __init__(self):
        """初始化轻量级分析组件"""
        self.components = None
        self._initialized = False

    def get_components(self) -> Dict[str, Any]:
        """获取分析组件实例（延迟初始化）"""
        if not self._initialized:
            self._init_analysis_components()
        return self.components

    def _init_analysis_components(self):
        """初始化分析组件（不包含数据提供者）"""
        try:
            # 导入分析师组件
            from src.agents.fundamental_analyst import FundamentalAnalyst
            from src.agents.technical_analyst import TechnicalAnalyst
            from src.agents.sentiment_analyst import SentimentAnalyst
            from src.agents.risk_manager import RiskManager
            from src.agents.portfolio_manager import PortfolioManager

            # 创建轻量级组件实例
            self.components = {
                'fundamental_analyst': FundamentalAnalyst(),
                'technical_analyst': TechnicalAnalyst(),
                'sentiment_analyst': SentimentAnalyst(),
                'risk_manager': RiskManager(),
                'portfolio_manager': PortfolioManager()
            }

            self._initialized = True
            logger.debug("缓存数据分析组件初始化完成（无数据提供者）")

        except Exception as e:
            logger.error(f"缓存数据分析组件初始化失败: {e}")
            # 使用空组件避免后续错误
            self.components = {
                'fundamental_analyst': None,
                'technical_analyst': None,
                'sentiment_analyst': None,
                'risk_manager': None,
                'portfolio_manager': None
            }
            raise

    def is_component_available(self, component_name: str) -> bool:
        """检查指定组件是否可用"""
        if not self._initialized:
            return False
        return self.components.get(component_name) is not None

    def get_available_components(self) -> list:
        """获取可用组件列表"""
        if not self._initialized:
            return []
        return [name for name, component in self.components.items() if component is not None]


class ThreadSafeCachedComponents:
    """
    线程安全的缓存数据分析组件管理器

    为每个线程提供独立的分析组件实例，避免线程间冲突
    """

    def __init__(self):
        """初始化线程安全组件管理器"""
        import threading
        self._thread_local = threading.local()
        logger.debug("线程安全缓存组件管理器初始化完成")

    def get_thread_components(self) -> Dict[str, Any]:
        """获取线程本地的分析组件"""
        if not hasattr(self._thread_local, 'cached_components'):
            # 为每个线程创建独立的组件实例
            self._thread_local.cached_components = CachedAnalysisComponents()
            logger.debug(f"为线程创建缓存分析组件实例")

        return self._thread_local.cached_components.get_components()

    def is_thread_component_available(self, component_name: str) -> bool:
        """检查线程本地组件是否可用"""
        if not hasattr(self._thread_local, 'cached_components'):
            return False
        return self._thread_local.cached_components.is_component_available(component_name)

    def get_thread_available_components(self) -> list:
        """获取线程本地可用组件列表"""
        if not hasattr(self._thread_local, 'cached_components'):
            return []
        return self._thread_local.cached_components.get_available_components()


# 全局单例实例
_thread_safe_components = None

def get_thread_safe_cached_components() -> ThreadSafeCachedComponents:
    """获取线程安全缓存组件管理器的全局单例"""
    global _thread_safe_components
    if _thread_safe_components is None:
        _thread_safe_components = ThreadSafeCachedComponents()
        logger.info("创建线程安全缓存组件管理器单例")
    return _thread_safe_components

def get_cached_analysis_components() -> Dict[str, Any]:
    """快捷函数：获取当前线程的缓存分析组件"""
    return get_thread_safe_cached_components().get_thread_components()