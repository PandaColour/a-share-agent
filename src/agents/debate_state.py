# -*- coding: utf-8 -*-
"""
辩论状态管理
借鉴TradingAgents-CN的状态管理机制
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class DebateState:
    """辩论状态管理类"""

    # 基本信息
    symbol: str = ""
    company_name: str = ""

    # 辩论历史和状态
    history: str = ""
    bull_history: str = ""
    bear_history: str = ""

    # 当前回应
    current_bull_response: str = ""
    current_bear_response: str = ""
    latest_speaker: str = ""  # "Bull" or "Bear"

    # 轮次控制
    count: int = 0
    max_rounds: int = 2  # 默认2轮

    # 辩论数据
    market_data: Dict = field(default_factory=dict)
    analyses: List[Dict] = field(default_factory=list)
    risk_assessment: Dict = field(default_factory=dict)

    # 时间戳
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.start_time is None:
            self.start_time = datetime.now()
        self.last_update = datetime.now()

    def add_bull_response(self, response: str, speaker: str = "Bull"):
        """添加看涨研究员的回应"""
        argument = f"{speaker}: {response}"

        # 更新历史记录
        self.history += "\n" + argument if self.history else argument
        self.bull_history += "\n" + argument if self.bull_history else argument

        # 更新当前状态
        self.current_bull_response = argument
        self.latest_speaker = speaker
        self.count += 1
        self.last_update = datetime.now()

        logger.debug(f"🐂 添加看涨回应，轮次: {self.count}")

    def add_bear_response(self, response: str, speaker: str = "Bear"):
        """添加看跌研究员的回应"""
        argument = f"{speaker}: {response}"

        # 更新历史记录
        self.history += "\n" + argument if self.history else argument
        self.bear_history += "\n" + argument if self.bear_history else argument

        # 更新当前状态
        self.current_bear_response = argument
        self.latest_speaker = speaker
        self.count += 1
        self.last_update = datetime.now()

        logger.debug(f"🐻 添加看跌回应，轮次: {self.count}")

    def should_continue_debate(self) -> bool:
        """判断是否应该继续辩论"""
        # 参考TradingAgents-CN的逻辑: count >= 2 * max_rounds (牛熊各一轮算一次完整轮次)
        max_total_exchanges = 2 * self.max_rounds
        should_continue = self.count < max_total_exchanges

        logger.debug(f"🎯 辩论控制: 轮次 {self.count}/{max_total_exchanges}, 继续: {should_continue}")
        return should_continue

    def get_next_speaker(self) -> str:
        """获取下一个发言者"""
        if not self.latest_speaker:
            return "Bull"  # 默认从看涨开始
        elif self.latest_speaker == "Bull":
            return "Bear"  # 看涨后轮到看跌
        else:
            return "Bull"  # 看跌后轮到看涨

    def get_debate_summary(self) -> Dict:
        """获取辩论摘要"""
        return {
            "symbol": self.symbol,
            "total_rounds": self.count,
            "max_rounds": self.max_rounds,
            "completed": not self.should_continue_debate(),
            "duration": (self.last_update - self.start_time).total_seconds() if self.last_update and self.start_time else 0,
            "bull_exchanges": len([line for line in self.history.split('\n') if line.startswith('Bull:')]),
            "bear_exchanges": len([line for line in self.history.split('\n') if line.startswith('Bear:')]),
            "latest_speaker": self.latest_speaker
        }

    def reset(self):
        """重置辩论状态"""
        self.history = ""
        self.bull_history = ""
        self.bear_history = ""
        self.current_bull_response = ""
        self.current_bear_response = ""
        self.latest_speaker = ""
        self.count = 0
        self.start_time = datetime.now()
        self.last_update = datetime.now()

        logger.info(f"🔄 重置辩论状态: {self.symbol}")

    def to_dict(self) -> Dict:
        """转换为字典格式（用于序列化）"""
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "history": self.history,
            "bull_history": self.bull_history,
            "bear_history": self.bear_history,
            "current_bull_response": self.current_bull_response,
            "current_bear_response": self.current_bear_response,
            "latest_speaker": self.latest_speaker,
            "count": self.count,
            "max_rounds": self.max_rounds,
            "debate_summary": self.get_debate_summary()
        }