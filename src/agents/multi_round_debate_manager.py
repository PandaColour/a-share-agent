# -*- coding: utf-8 -*-
"""
多轮辩论管理器
借鉴TradingAgents-CN的多轮辩论机制，协调看涨和看跌研究员进行多轮辩论
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .debate_state import DebateState
from .debate_controller import DebateController, create_debate_controller
from .multi_round_bull_researcher import MultiRoundBullResearcher
from .multi_round_bear_researcher import MultiRoundBearResearcher

# 添加AI模型相关导入
import sys
import os
config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config')
sys.path.insert(0, config_dir)
from config_manager import get_config

try:
    from ..ai_models import AIModelFactory
except ImportError:
    from ai_models import AIModelFactory

logger = logging.getLogger(__name__)

class MultiRoundDebateManager:
    """多轮辩论管理器 - 协调多轮辩论流程"""

    def __init__(self, config_manager=None):
        """
        初始化多轮辩论管理器

        Args:
            config_manager: 配置管理器（保留向后兼容）
        """
        self.config_manager = config_manager or get_config()
        self.agent_type = "debate"
        self.ai_model = None

        # 初始化AI模型（使用BaseAnalyst的模式）
        self.init_ai_model()

        # 初始化组件
        self.debate_controller = create_debate_controller(self.config_manager)
        self.bull_researcher = MultiRoundBullResearcher()
        self.bear_researcher = MultiRoundBearResearcher()

        # 当前辩论状态
        self.current_debate_state: Optional[DebateState] = None

        logger.info(f"🎯 多轮辩论管理器初始化完成，最大轮次: {self.debate_controller.max_debate_rounds}")

    def init_ai_model(self):
        """初始化AI模型 - 复制BaseAnalyst的逻辑"""
        try:
            # 使用统一配置管理器检查AI分析是否启用
            ai_config = self.config_manager.get_ai_config()
            if ai_config.get('enable_ai_analysis', False):
                # 获取分析师分配的模型
                analyst_assignments = ai_config.get('analyst_assignments', {})
                model_name = analyst_assignments.get(self.agent_type, ai_config.get('default_model', 'mock_model'))

                # 获取模型配置
                models_config = ai_config.get('models', {})
                model_info = models_config.get(model_name, {})

                if model_info:
                    self.ai_model = AIModelFactory.create_model(model_name, models_config)
                    logger.info(f"多轮辩论分析师已加载AI模型: {model_info.get('name')} ({model_info.get('type')})")
                else:
                    logger.warning(f"未找到模型配置: {model_name}")
                    self.ai_model = None
            else:
                logger.info("AI分析已禁用，多轮辩论分析师使用传统方法")
        except Exception as e:
            logger.error(f"多轮辩论分析师AI模型初始化失败: {e}")
            self.ai_model = None

    def conduct_multi_round_debate(self,
                                 symbol: str,
                                 company_name: str,
                                 analyses: List[Dict],
                                 market_data: Dict,
                                 risk_assessment: Dict) -> Dict:
        """
        执行多轮辩论

        Args:
            symbol: 股票代码
            company_name: 公司名称
            analyses: 分析结果列表
            market_data: 市场数据
            risk_assessment: 风险评估

        Returns:
            Dict: 完整的辩论结果
        """
        logger.info(f"🎯 开始多轮辩论: {symbol}({company_name})")

        # 初始化辩论状态
        self._initialize_debate_state(symbol, company_name, market_data, analyses, risk_assessment)

        debate_result = {
            "manager_type": "多轮辩论管理器",
            "symbol": symbol,
            "company_name": company_name,
            "debate_rounds": [],
            "final_decision": {},
            "debate_summary": {},
            "confidence_level": 0.5,
            "key_factors": [],
            "risk_assessment": risk_assessment,
            "timestamp": datetime.now().isoformat()
        }

        try:
            # 执行多轮辩论循环
            round_count = 0
            max_rounds = self.debate_controller.max_debate_rounds

            while self.debate_controller.should_continue_debate(self.current_debate_state):
                round_count += 1
                logger.info(f"🔄 执行第 {round_count} 轮辩论: {symbol}")

                # 确定下一个发言者
                next_speaker = self.debate_controller.get_next_speaker(self.current_debate_state)

                # 创建辩论上下文
                debate_context = self.debate_controller.create_debate_context(
                    self.current_debate_state, market_data, analyses, next_speaker
                )

                # 执行单轮辩论
                round_result = self._execute_debate_round(next_speaker, debate_context)

                # 更新辩论状态
                self._update_debate_state(next_speaker, round_result)

                # 记录轮次结果
                debate_result["debate_rounds"].append({
                    "round": round_count,
                    "speaker": next_speaker,
                    "response": round_result,
                    "timestamp": datetime.now().isoformat()
                })

                # 防止无限循环
                if round_count >= max_rounds * 3:  # 安全上限
                    logger.warning(f"⚠️ 达到安全上限，强制结束辩论: {symbol}")
                    break

            # 生成最终决策
            final_decision = self._make_final_decision()
            debate_result["final_decision"] = final_decision
            debate_result["confidence_level"] = final_decision.get("confidence", 0.5)

            # 生成辩论摘要
            debate_summary = self._generate_debate_summary()
            debate_result["debate_summary"] = debate_summary

            # 识别关键因素
            key_factors = self._identify_key_factors()
            debate_result["key_factors"] = key_factors

            # 记录辩论完成
            self.debate_controller.log_debate_summary(self.current_debate_state)

            logger.info(f"🏁 多轮辩论完成: {symbol}, 总轮次: {round_count}, 决策: {final_decision.get('action', '未知')}")

        except Exception as e:
            logger.error(f"🚫 多轮辩论执行失败 {symbol}: {e}")
            debate_result["final_decision"] = {
                "action": "持有",
                "confidence": 0.1,
                "reason": f"辩论过程出现错误: {str(e)}",
                "recommendation": "持有"
            }

        return debate_result

    def _initialize_debate_state(self,
                               symbol: str,
                               company_name: str,
                               market_data: Dict,
                               analyses: List[Dict],
                               risk_assessment: Dict):
        """初始化辩论状态"""
        max_rounds = self.debate_controller.max_debate_rounds

        self.current_debate_state = DebateState(
            symbol=symbol,
            company_name=company_name,
            max_rounds=max_rounds,
            market_data=market_data,
            analyses=analyses,
            risk_assessment=risk_assessment
        )

        logger.debug(f"📝 辩论状态初始化: {symbol}, 最大轮次: {max_rounds}")

    def _execute_debate_round(self, speaker: str, context: Dict) -> str:
        """
        执行单轮辩论

        Args:
            speaker: 发言者 ("Bull" 或 "Bear")
            context: 辩论上下文

        Returns:
            str: 辩论回应
        """
        try:
            if speaker == "Bull":
                response = self.bull_researcher.create_debate_argument(context)
                logger.debug(f"🐂 看涨研究员发言完成: {len(response)} 字符")
            elif speaker == "Bear":
                response = self.bear_researcher.create_debate_argument(context)
                logger.debug(f"🐻 看跌研究员发言完成: {len(response)} 字符")
            else:
                logger.error(f"❌ 未知发言者: {speaker}")
                response = f"发言者错误: {speaker}"

            return response

        except Exception as e:
            logger.error(f"🚫 单轮辩论执行失败 {speaker}: {e}")
            return f"辩论发言生成失败: {str(e)}"

    def _update_debate_state(self, speaker: str, response: str):
        """更新辩论状态"""
        if not self.current_debate_state:
            logger.error("❌ 辩论状态未初始化")
            return

        if speaker == "Bull":
            self.current_debate_state.add_bull_response(response)
        elif speaker == "Bear":
            self.current_debate_state.add_bear_response(response)

        logger.debug(f"📝 辩论状态更新: {speaker}, 总轮次: {self.current_debate_state.count}")

    def _make_final_decision(self) -> Dict:
        """生成最终投资决策"""
        if not self.current_debate_state:
            return {
                "action": "持有",
                "confidence": 0.1,
                "reason": "辩论状态异常",
                "recommendation": "持有"
            }

        # 分析辩论结果
        bull_exchanges = len([line for line in self.current_debate_state.history.split('\n') if line.startswith('Bull:')])
        bear_exchanges = len([line for line in self.current_debate_state.history.split('\n') if line.startswith('Bear:')])

        # 简化的决策逻辑（可以后续优化为更复杂的AI决策）
        bull_strength = bull_exchanges
        bear_strength = bear_exchanges

        # 基于交流内容长度和轮次数评估
        if bull_strength > bear_strength:
            confidence = min(0.8, 0.5 + (bull_strength - bear_strength) * 0.1)
            action = "买入" if confidence > 0.6 else "持有"
            reason = f"看涨观点更具说服力 (看涨{bull_strength}轮 vs 看跌{bear_strength}轮)"
        elif bear_strength > bull_strength:
            confidence = min(0.8, 0.5 + (bear_strength - bull_strength) * 0.1)
            action = "卖出" if confidence > 0.6 else "持有"
            reason = f"看跌观点更具说服力 (看跌{bear_strength}轮 vs 看涨{bull_strength}轮)"
        else:
            confidence = 0.5
            action = "持有"
            reason = "看涨看跌观点势均力敌，建议保持观望"

        return {
            "action": action,
            "confidence": round(confidence, 3),
            "reason": reason,
            "recommendation": action,
            "bull_strength": bull_strength,
            "bear_strength": bear_strength
        }

    def _generate_debate_summary(self) -> Dict:
        """生成辩论摘要"""
        if not self.current_debate_state:
            return {}

        summary = self.current_debate_state.get_debate_summary()
        progress = self.debate_controller.get_debate_progress(self.current_debate_state)

        return {
            "total_exchanges": summary["total_rounds"],
            "bull_exchanges": summary["bull_exchanges"],
            "bear_exchanges": summary["bear_exchanges"],
            "duration_seconds": summary["duration"],
            "completion_rate": progress["progress_percentage"],
            "debate_quality": "正常" if summary["completed"] else "未完成",
            "final_speaker": self.current_debate_state.latest_speaker
        }

    def _identify_key_factors(self) -> List[str]:
        """识别关键因素"""
        if not self.current_debate_state:
            return []

        key_factors = []

        # 从辩论历史中提取关键信息
        history_lines = self.current_debate_state.history.split('\n')
        for line in history_lines:
            if '核心论证' in line or '核心风险' in line:
                key_factors.append(line.strip())

        # 添加辩论过程信息
        summary = self.current_debate_state.get_debate_summary()
        key_factors.append(f"辩论轮次: {summary['total_rounds']}轮交流")
        key_factors.append(f"参与情况: 看涨{summary['bull_exchanges']}次, 看跌{summary['bear_exchanges']}次")

        return key_factors[:5]  # 返回前5个关键因素

    def get_debate_status(self) -> Dict:
        """获取当前辩论状态"""
        if not self.current_debate_state:
            return {"status": "未初始化"}

        progress = self.debate_controller.get_debate_progress(self.current_debate_state)
        return {
            "status": "进行中" if self.debate_controller.should_continue_debate(self.current_debate_state) else "已完成",
            "current_round": progress["current_round"],
            "progress": f"{progress['progress_percentage']}%",
            "latest_speaker": self.current_debate_state.latest_speaker,
            "next_speaker": progress["next_speaker"] if progress["exchanges_remaining"] > 0 else "无"
        }

    def reset_debate(self):
        """重置辩论状态"""
        if self.current_debate_state:
            self.current_debate_state.reset()
            logger.info("🔄 辩论状态已重置")

# 便捷函数
def create_multi_round_debate_manager(config_manager=None, ai_client=None) -> MultiRoundDebateManager:
    """创建多轮辩论管理器"""
    return MultiRoundDebateManager(config_manager, ai_client)