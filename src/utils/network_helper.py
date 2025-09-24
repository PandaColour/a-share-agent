#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
网络连接辅助工具
解决Connection aborted和RemoteDisconnected问题
"""

import time
import logging
import requests
from typing import Callable, Any, Optional
from functools import wraps
import akshare as ak

logger = logging.getLogger(__name__)


class NetworkHelper:
    """网络连接辅助类"""

    def __init__(self):
        """初始化网络配置"""
        # 配置requests会话
        self.session = requests.Session()

        # 设置更长的超时时间
        self.session.timeout = (10, 30)  # 连接超时10秒，读取超时30秒

        # 设置重试适配器
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retry_strategy = Retry(
            total=0,  # 总重试次数设为0，立即失败转移
            backoff_factor=1,  # 退避因子
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的HTTP状态码
            allowed_methods=["HEAD", "GET", "OPTIONS"]  # 允许重试的HTTP方法
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # 设置更好的User-Agent
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })


def retry_on_connection_error(max_retries: int = 0, delay: float = 1.0, backoff: float = 2.0):
    """
    连接错误重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间(秒)
        backoff: 退避倍数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"函数 {func.__name__} 在第 {attempt + 1} 次尝试后成功")
                    return result

                except (requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout,
                        ConnectionError,
                        Exception) as e:

                    last_exception = e
                    error_msg = str(e)

                    # 检查是否是网络相关错误
                    network_errors = [
                        'Connection aborted',
                        'RemoteDisconnected',
                        'Connection broken',
                        'Connection reset',
                        'Connection timed out',
                        'Read timed out',
                        'HTTP Error 429',  # Too Many Requests
                        'HTTP Error 502',  # Bad Gateway
                        'HTTP Error 503',  # Service Unavailable
                        'HTTP Error 504'   # Gateway Timeout
                    ]

                    is_network_error = any(err in error_msg for err in network_errors)

                    if attempt < max_retries and is_network_error:
                        logger.warning(f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}")
                        logger.info(f"等待 {current_delay:.1f} 秒后重试...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        if is_network_error:
                            logger.error(f"函数 {func.__name__} 在 {max_retries + 1} 次尝试后仍然失败: {e}")
                        raise e

            raise last_exception

        return wrapper
    return decorator


def safe_akshare_call(func_name: str, *args, **kwargs) -> Optional[Any]:
    """
    安全的akshare API调用

    Args:
        func_name: akshare函数名
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        API调用结果或None
    """
    @retry_on_connection_error(max_retries=0, delay=2.0, backoff=2.0)
    def _call_akshare():
        # 获取akshare函数
        if not hasattr(ak, func_name):
            raise AttributeError(f"akshare没有函数: {func_name}")

        ak_func = getattr(ak, func_name)
        logger.debug(f"调用 ak.{func_name}({args}, {kwargs})")

        # 添加一些延迟避免频繁请求
        time.sleep(0.5)  # 500ms延迟

        return ak_func(*args, **kwargs)

    try:
        return _call_akshare()
    except Exception as e:
        logger.error(f"akshare.{func_name} 调用失败: {e}")
        return None


def configure_akshare_settings():
    """配置akshare的网络设置"""
    try:
        # 设置请求延迟（如果akshare支持）
        if hasattr(ak, 'set_global_timeout'):
            ak.set_global_timeout(30)

        # 设置其他可能的配置
        logger.info("已配置akshare网络设置")

    except Exception as e:
        logger.warning(f"配置akshare设置失败: {e}")


# 全局网络助手实例
network_helper = NetworkHelper()

# 在模块加载时配置akshare
configure_akshare_settings()