# -*- coding: utf-8 -*-
"""
辩论控制器
借鉴TradingAgents-CN的ConditionalLogic机制，控制多轮辩论流程
"""

import logging
from typing import Dict, Optional
from .debate_state import DebateState

logger = logging.getLogger(__name__)

class DebateController:
    """辩论控制器 - 管理多轮辩论的流程控制"""

    def __init__(self, max_debate_rounds: int = 2):
        """
        初始化辩论控制器

        Args:
            max_debate_rounds: 最大辩论轮次（每轮包含牛熊各一次发言）
        """
        self.max_debate_rounds = max_debate_rounds
        logger.info(f"🎯 辩论控制器初始化，最大轮次: {max_debate_rounds}")

    def should_continue_debate(self, debate_state: DebateState) -> bool:
        """
        判断是否应该继续辩论

        Args:
            debate_state: 当前辩论状态

        Returns:
            bool: True表示继续辩论，False表示结束辩论
        """
        # 借鉴TradingAgents-CN的逻辑: 2 * max_rounds (牛熊各一轮算一次完整轮次)
        max_total_exchanges = 2 * self.max_debate_rounds
        should_continue = debate_state.count < max_total_exchanges

        if not should_continue:
            logger.info(f"🏁 辩论结束: {debate_state.symbol} 完成 {debate_state.count}/{max_total_exchanges} 轮交流")
        else:
            logger.debug(f"🔄 辩论继续: {debate_state.symbol} 当前 {debate_state.count}/{max_total_exchanges} 轮")

        return should_continue

    def get_next_speaker(self, debate_state: DebateState) -> str:
        """
        确定下一个发言者

        Args:
            debate_state: 当前辩论状态

        Returns:
            str: "Bull" 或 "Bear"
        """
        next_speaker = debate_state.get_next_speaker()
        logger.debug(f"👤 下一发言者: {next_speaker} (当前: {debate_state.latest_speaker})")
        return next_speaker

    def create_debate_context(self,
                            debate_state: DebateState,
                            market_data: Dict,
                            analyses: list,
                            speaker: str) -> Dict:
        """
        为指定发言者创建辩论上下文

        Args:
            debate_state: 辩论状态
            market_data: 市场数据
            analyses: 分析结果
            speaker: 当前发言者 ("Bull" 或 "Bear")

        Returns:
            Dict: 辩论上下文数据
        """
        # 基础上下文
        context = {
            "symbol": debate_state.symbol,
            "company_name": debate_state.company_name,
            "market_data": market_data,
            "analyses": analyses,
            "current_speaker": speaker,
            "debate_round": (debate_state.count // 2) + 1,  # 当前是第几轮完整辩论
            "exchange_count": debate_state.count,  # 总交流次数
            "is_first_round": debate_state.count < 2,  # 是否是第一轮
        }

        # 对话历史
        context["full_history"] = debate_state.history
        context["bull_history"] = debate_state.bull_history
        context["bear_history"] = debate_state.bear_history

        # 对方观点（用于反驳）
        if speaker == "Bull":
            context["opponent_response"] = debate_state.current_bear_response
            context["opponent_history"] = debate_state.bear_history
        else:
            context["opponent_response"] = debate_state.current_bull_response
            context["opponent_history"] = debate_state.bull_history

        # 当前自己的历史观点
        if speaker == "Bull":
            context["own_history"] = debate_state.bull_history
        else:
            context["own_history"] = debate_state.bear_history

        # 辩论状态信息
        context["debate_status"] = {
            "is_opening_statement": debate_state.count == 0 or (speaker == "Bull" and debate_state.count == 0) or (speaker == "Bear" and debate_state.count == 1),
            "is_response_round": debate_state.count >= 2,
            "rounds_remaining": self.max_debate_rounds - ((debate_state.count // 2) + 1),
            "total_exchanges": debate_state.count
        }

        logger.debug(f"📝 为 {speaker} 创建辩论上下文: 第{context['debate_round']}轮, 第{context['exchange_count']+1}次交流")

        return context

    def validate_debate_state(self, debate_state: DebateState) -> bool:
        """
        验证辩论状态的有效性

        Args:
            debate_state: 辩论状态

        Returns:
            bool: 状态是否有效
        """
        if not debate_state.symbol:
            logger.error("❌ 辩论状态验证失败: 缺少股票代码")
            return False

        if debate_state.count < 0:
            logger.error("❌ 辩论状态验证失败: 轮次计数无效")
            return False

        if debate_state.max_rounds < 1:
            logger.error("❌ 辩论状态验证失败: 最大轮次设置无效")
            return False

        return True

    def get_debate_progress(self, debate_state: DebateState) -> Dict:
        """
        获取辩论进度信息

        Args:
            debate_state: 辩论状态

        Returns:
            Dict: 进度信息
        """
        max_exchanges = 2 * self.max_debate_rounds
        current_round = (debate_state.count // 2) + 1
        progress_percentage = min(100, (debate_state.count / max_exchanges) * 100)

        return {
            "current_round": current_round,
            "max_rounds": self.max_debate_rounds,
            "current_exchange": debate_state.count,
            "max_exchanges": max_exchanges,
            "progress_percentage": round(progress_percentage, 1),
            "latest_speaker": debate_state.latest_speaker,
            "next_speaker": self.get_next_speaker(debate_state),
            "is_final_round": current_round >= self.max_debate_rounds,
            "exchanges_remaining": max(0, max_exchanges - debate_state.count)
        }

    def log_debate_summary(self, debate_state: DebateState):
        """记录辩论摘要"""
        progress = self.get_debate_progress(debate_state)
        summary = debate_state.get_debate_summary()

        logger.info(f"""
🎯 辩论摘要 - {debate_state.symbol}:
   📊 进度: {progress['progress_percentage']}% ({progress['current_exchange']}/{progress['max_exchanges']} 交流)
   🗣️  发言统计: 看涨 {summary['bull_exchanges']} 次, 看跌 {summary['bear_exchanges']} 次
   ⏱️  持续时间: {summary['duration']:.1f} 秒
   🏁 状态: {'已完成' if summary['completed'] else '进行中'}
        """.strip())

# 便捷函数
def create_debate_controller(config_manager=None) -> DebateController:
    """创建辩论控制器"""
    max_rounds = 2  # 默认值

    if config_manager:
        max_rounds = config_manager.get_debate_rounds()

    return DebateController(max_debate_rounds=max_rounds)