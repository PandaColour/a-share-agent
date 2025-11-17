# -*- coding: utf-8 -*-
"""
多轮辩论看涨研究员
借鉴TradingAgents-CN的辩论机制，支持基于对话历史的多轮辩论
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

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

class MultiRoundBullResearcher:
    """多轮辩论看涨研究员 - 支持基于历史对话的辩论"""

    def __init__(self, config_manager=None):
        """
        初始化多轮看涨研究员

        Args:
            config_manager: 配置管理器（保留向后兼容）
        """
        self.config_manager = config_manager or get_config()
        self.agent_type = "bull_researcher"
        self.ai_model = None

        # 初始化AI模型
        self.init_ai_model()

    def init_ai_model(self):
        """初始化AI模型"""
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
                    logger.info(f"🐂 看涨研究员已加载AI模型: {model_info.get('name')} ({model_info.get('type')})")
                else:
                    logger.warning(f"🐂 看涨研究员未找到模型配置: {model_name}")
                    self.ai_model = None
            else:
                logger.info("🐂 AI分析已禁用，看涨研究员使用传统方法")
        except Exception as e:
            logger.error(f"🐂 看涨研究员AI模型初始化失败: {e}")
            self.ai_model = None

    def create_debate_argument(self, debate_context: Dict) -> str:
        """
        基于辩论上下文创建看涨论证

        Args:
            debate_context: 辩论上下文，包含历史对话、市场数据等

        Returns:
            str: 看涨研究员的论证内容
        """
        logger.info(f"[INFO] Bull researcher starting round {debate_context['debate_round']} debate: {debate_context['symbol']}")

        try:
            # 获取辩论prompt配置
            prompt_config = self._get_debate_prompts()
            if not prompt_config:
                return self._fallback_argument(debate_context)

            # 构建完整的prompt
            full_prompt = self._build_debate_prompt(prompt_config, debate_context)

            # 调用AI模型生成回应
            if self.ai_model:
                response = self.ai_model.generate_response(full_prompt)
                logger.debug(f"🐂 看涨研究员AI回应生成成功: {len(response)} 字符")
                return response
            else:
                logger.warning("🐂 AI模型未配置，使用备选方案")
                return self._fallback_argument(debate_context)

        except Exception as e:
            logger.error(f"🐂 看涨研究员辩论生成失败: {e}")
            return self._fallback_argument(debate_context)

    def _get_debate_prompts(self) -> Optional[Dict]:
        """获取辩论prompt配置"""
        if not self.config_manager:
            return None

        try:
            prompts = self.config_manager.get('system_settings.debate_prompts.bull_researcher', {})
            if not prompts:
                logger.warning("🐂 未找到看涨研究员辩论prompt配置")
                return None

            return prompts
        except Exception as e:
            logger.error(f"🐂 获取辩论prompt失败: {e}")
            return None

    def _build_debate_prompt(self, prompt_config: Dict, context: Dict) -> str:
        """
        构建完整的辩论prompt

        Args:
            prompt_config: prompt配置
            context: 辩论上下文

        Returns:
            str: 完整的prompt
        """
        try:
            # 系统prompt
            system_prompt = prompt_config.get('system_prompt', '')

            # 用户prompt模板
            debate_prompt_template = prompt_config.get('debate_prompt', '')

            # 准备模板参数
            template_params = {
                'symbol': context.get('symbol', ''),
                'company_name': context.get('company_name', ''),
                'market_data': self._format_market_data(context.get('market_data', {})),
                'analyses': self._format_analyses(context.get('analyses', [])),
                'debate_round': context.get('debate_round', 1),
                'exchange_count': context.get('exchange_count', 0),
                'rounds_remaining': context.get('debate_status', {}).get('rounds_remaining', 0),
                'full_history': context.get('full_history', '暂无历史对话'),
                'opponent_response': context.get('opponent_response', '对方尚未发言'),
            }

            # 格式化prompt
            formatted_prompt = debate_prompt_template.format(**template_params)

            # 组合系统prompt和用户prompt
            full_prompt = f"{system_prompt}\n\n{formatted_prompt}"

            logger.debug(f"🐂 构建prompt成功: {len(full_prompt)} 字符")
            return full_prompt

        except Exception as e:
            logger.error(f"🐂 构建prompt失败: {e}")
            return self._create_fallback_prompt(context)

    def _format_market_data(self, market_data: Dict) -> str:
        """格式化市场数据为可读文本"""
        if not market_data:
            return "暂无市场数据"

        formatted_data = []

        # 基本价格信息
        if 'current_price' in market_data:
            formatted_data.append(f"当前价格: {market_data['current_price']}元")

        if 'daily_change_pct' in market_data:
            formatted_data.append(f"日涨跌幅: {market_data['daily_change_pct']:.2f}%")

        if 'volume' in market_data:
            formatted_data.append(f"成交量: {market_data['volume']}")

        # 技术指标
        if 'technical_indicators' in market_data:
            indicators = market_data['technical_indicators']
            if 'MA5' in indicators:
                formatted_data.append(f"MA5: {indicators['MA5']}元")
            if 'RSI' in indicators:
                formatted_data.append(f"RSI: {indicators['RSI']}")

        return '\n'.join(formatted_data) if formatted_data else "市场数据不完整"

    def _format_analyses(self, analyses: List[Dict]) -> str:
        """格式化分析结果为可读文本"""
        if not analyses:
            return "暂无分析报告"

        formatted_analyses = []
        for analysis in analyses:
            analyst_type = analysis.get('analyst_type', '未知分析师')
            recommendation = analysis.get('recommendation', '无推荐')
            confidence = analysis.get('confidence', 0)

            formatted_analyses.append(f"{analyst_type}: {recommendation} (置信度: {confidence:.2f})")

            # 添加主要推理
            reasoning = analysis.get('reasoning', [])
            if reasoning:
                main_reasons = reasoning[:3]  # 取前3个主要推理
                for reason in main_reasons:
                    formatted_analyses.append(f"  - {reason}")

        return '\n'.join(formatted_analyses)

    def _fallback_argument(self, context: Dict) -> str:
        """备选论证方案（当AI调用失败时使用）"""
        symbol = context.get('symbol', '')
        debate_round = context.get('debate_round', 1)

        return f"""🐂 看涨观点 - 第{debate_round}轮：

💡 核心论证：基于当前市场环境和数据分析，{symbol}具备明显的投资价值和上涨潜力。

📊 数据支撑：
- 当前估值水平相对合理，存在低估空间
- 技术面显示积极信号，支撑位稳固
- 行业基本面向好，政策环境有利

🎯 目标价位：建议关注15-20%的上涨空间

🛡️ 风险应对：建议分批建仓，设置合理止损位

🔥 反驳要点：市场短期波动不改变长期价值，当前调整为较好的入场机会。

注：此为系统备选回应，建议配置AI模型以获得更专业的分析。"""

    def _create_fallback_prompt(self, context: Dict) -> str:
        """创建备选prompt"""
        return f"""请作为专业的看涨研究员，针对股票 {context.get('symbol', '')} 进行分析，
基于提供的市场数据和历史对话，提出有说服力的看涨论证。
请重点关注投资机会和上涨催化剂，并针对可能的看跌观点进行反驳。"""

    def get_researcher_info(self) -> Dict:
        """获取研究员信息"""
        return {
            "agent_type": self.agent_type,
            "role": "多轮辩论看涨研究员",
            "capabilities": [
                "基于历史对话的多轮辩论",
                "投资机会识别与论证",
                "看跌观点反驳",
                "数据驱动的分析"
            ],
            "ai_enabled": self.ai_client is not None,
            "config_loaded": self.config_manager is not None
        }