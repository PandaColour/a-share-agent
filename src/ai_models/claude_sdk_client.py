# -*- coding: utf-8 -*-
"""
Claude Code SDK 客户端
基于 claude-code-sdk 的集成
"""

import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from .base import AIModelInterface

logger = logging.getLogger(__name__)


class ClaudeSDKClient(AIModelInterface):
    """Claude Code SDK 客户端实现"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化 Claude Code SDK 客户端

        Args:
            config: 配置字典，包含以下键:
                - model: 模型名称（可选）
                - working_dir: 工作目录（可选，默认使用项目根目录）
                - system_prompt: 系统提示词（可选）

        注意: Claude Code SDK 使用本地配置，不需要 API key
        """
        self.config = config
        self.model = config.get('model')
        self.working_dir = config.get('working_dir', Path.cwd())
        self.system_prompt = config.get('system_prompt')
        self.client = None

        # 延迟导入，避免未安装时影响其他模块
        try:
            from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient as SDKClient
            from claude_agent_sdk import AssistantMessage, TextBlock, ResultMessage

            self.SDKClient = SDKClient
            self.ClaudeAgentOptions = ClaudeAgentOptions
            self.AssistantMessage = AssistantMessage
            self.TextBlock = TextBlock
            self.ResultMessage = ResultMessage
            self.available = True
            logger.info(f"Claude Agent SDK 导入成功")
        except ImportError as e:
            logger.warning(f"claude-agent-sdk 包未安装: {e}")
            logger.warning("请运行: pip install claude-agent-sdk")
            self.available = False
        except Exception as e:
            logger.error(f"Claude Code SDK 导入失败: {e}")
            self.available = False

    def is_available(self) -> bool:
        """检查客户端是否可用"""
        return self.available

    async def _initialize_client(self):
        """初始化 Claude SDK 客户端"""
        if self.client:
            return  # 已经初始化

        try:
            # 确保工作目录存在
            working_dir = Path(self.working_dir)
            working_dir.mkdir(parents=True, exist_ok=True)

            # 创建选项
            options = self.ClaudeAgentOptions(
                cwd=str(working_dir),
                system_prompt=self.system_prompt,
                permission_mode="acceptEdits"  # 自动接受编辑，启用工具
            )

            # 如果配置了模型，设置模型
            if self.model:
                options.model = self.model

            # 创建客户端
            self.client = self.SDKClient(options=options)

            # 连接
            await self.client.connect()
            logger.info("Claude Code SDK 连接成功")

        except Exception as e:
            logger.error(f"Claude Code SDK 初始化失败: {e}")
            raise

    async def _query_async(self, prompt: str) -> str:
        """
        异步查询 Claude Code SDK

        Args:
            prompt: 用户提示词

        Returns:
            生成的文本
        """
        try:
            # 初始化客户端（如果未初始化）
            await self._initialize_client()

            # 发送查询
            await self.client.query(prompt)

            # 接收响应
            response_parts = []
            async for msg in self.client.receive_response():
                if isinstance(msg, self.AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, self.TextBlock):
                            response_parts.append(block.text)
                elif isinstance(msg, self.ResultMessage):
                    break

            return ''.join(response_parts) if response_parts else ""

        except Exception as e:
            logger.error(f"Claude Code SDK 查询失败: {e}")
            raise

    def _run_async(self, coro):
        """
        在同步代码中运行异步协程

        Args:
            coro: 异步协程

        Returns:
            协程的返回值
        """
        try:
            # 尝试获取当前事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，创建新的事件循环在新线程中运行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
            else:
                # 如果事件循环未运行，直接运行
                return loop.run_until_complete(coro)
        except RuntimeError:
            # 如果没有事件循环，创建新的
            return asyncio.run(coro)

    def generate_analysis(self, prompt: str, context: Dict = None) -> str:
        """
        生成分析结果

        Args:
            prompt: 提示词
            context: 上下文信息（可选）

        Returns:
            生成的分析文本，失败返回错误信息
        """
        if not self.is_available():
            return "Claude Code SDK 客户端不可用，请检查安装: pip install claude-agent-sdk"

        try:
            # 如果有上下文，添加到提示词中
            if context:
                context_str = str(context)[:500]
                full_prompt = f"当前分析的股票信息：{context_str}\n\n{prompt}"
            else:
                full_prompt = prompt

            logger.info(f"调用 Claude Code SDK")

            # 运行异步查询
            result = self._run_async(self._query_async(full_prompt))

            if result:
                logger.info(f"Claude Code SDK 调用成功，返回长度: {len(result)}")
                return result
            else:
                logger.warning("Claude Code SDK 返回空内容")
                return "Claude Code SDK 返回空内容"

        except Exception as e:
            logger.error(f"Claude Code SDK 调用失败: {e}")
            import traceback
            traceback.print_exc()
            return f"Claude Code SDK 调用失败: {str(e)}"

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """
        生成文本（兼容旧接口）

        Args:
            prompt: 提示词
            **kwargs: 额外参数
                - system: 系统提示词（会临时覆盖配置的系统提示词）

        Returns:
            生成的文本，失败返回None
        """
        if not self.is_available():
            logger.error("Claude Code SDK 客户端不可用")
            return None

        try:
            # 如果提供了系统提示词，临时更新
            original_system_prompt = self.system_prompt
            if 'system' in kwargs:
                self.system_prompt = kwargs['system']
                # 重置客户端以使用新的系统提示词
                self.client = None

            try:
                logger.info(f"调用 Claude Code SDK")

                # 运行异步查询
                result = self._run_async(self._query_async(prompt))

                if result:
                    logger.info(f"Claude Code SDK 调用成功，返回长度: {len(result)}")
                    return result
                else:
                    logger.warning("Claude Code SDK 返回空内容")
                    return None

            finally:
                # 恢复原始系统提示词
                if 'system' in kwargs:
                    self.system_prompt = original_system_prompt

        except Exception as e:
            logger.error(f"Claude Code SDK 调用失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def __del__(self):
        """清理资源"""
        # 不主动断开连接，让客户端自然清理
        self.client = None
