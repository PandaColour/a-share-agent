# -*- coding: utf-8 -*-
"""
辩论置信度动态计算器
基于辩论内容质量动态调整置信度，而非简单统计发言次数
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DebateConfidenceCalculator:
    """辩论置信度计算器 - 基于多维度辩论质量评估"""

    def __init__(self):
        """初始化置信度计算器"""
        # 置信度关键词权重
        self.confidence_keywords = {
            # 强势关键词（增加置信度）
            "强烈": 0.10,
            "明确": 0.08,
            "显著": 0.08,
            "确定": 0.08,
            "充分": 0.06,
            "有力": 0.06,
            "突破": 0.05,
            "大幅": 0.05,

            # 弱势关键词（降低置信度）
            "可能": -0.05,
            "或许": -0.06,
            "不确定": -0.08,
            "模糊": -0.08,
            "有限": -0.06,
            "谨慎": -0.04,
            "风险": -0.03,
        }

        # 数据支撑关键词
        self.data_support_keywords = [
            "PE", "PB", "ROE", "市盈率", "市净率", "净资产收益率",
            "元", "价格", "目标价", "增长率", "%",
            "MACD", "RSI", "均线", "成交量", "换手率",
            "财报", "业绩", "利润", "营收", "现金流"
        ]

        # 逻辑性关键词
        self.logic_keywords = [
            "因为", "所以", "由于", "导致", "基于", "根据",
            "数据显示", "分析表明", "证明", "验证", "支撑"
        ]

    def calculate_dynamic_confidence(self,
                                     debate_rounds: List[Dict],
                                     min_confidence: float = 0.6,
                                     max_confidence: float = 0.95) -> Dict:
        """
        基于辩论质量动态计算置信度

        Args:
            debate_rounds: 辩论轮次列表，每轮包含 {"speaker": "Bull/Bear", "response": "..."}
            min_confidence: 最小置信度阈值
            max_confidence: 最大置信度阈值

        Returns:
            Dict: 包含置信度、详细评分、决策建议
        """
        if not debate_rounds:
            logger.warning("⚠️ 辩论轮次为空，返回默认置信度")
            return {
                "confidence": min_confidence,
                "action": "持有",
                "reason": "辩论数据不足",
                "quality_scores": {}
            }

        # 分析牛熊双方的辩论质量
        bull_scores = self._analyze_side_quality("Bull", debate_rounds)
        bear_scores = self._analyze_side_quality("Bear", debate_rounds)

        # 计算质量差异
        quality_diff = bull_scores["total_score"] - bear_scores["total_score"]

        # 基于质量差异计算置信度
        base_confidence = 0.5

        # 质量差异影响系数（-1.0 到 1.0）
        quality_factor = max(-1.0, min(1.0, quality_diff / 100))

        # 辩论轮次奖励（更多轮次表示更充分讨论）
        rounds_bonus = min(0.1, len(debate_rounds) * 0.02)

        # 【优化1】扩大置信度调整幅度：从0.3提升到0.45，使强弱信号区分更明显
        # 使用非线性映射增强极端信号的影响
        confidence_adjustment = (abs(quality_factor) ** 1.3) * 0.45 * (1 if quality_factor > 0 else -1)
        confidence = base_confidence + confidence_adjustment + rounds_bonus

        # 限制在合理区间
        confidence = max(min_confidence, min(max_confidence, confidence))

        # 【优化2】缩小决策阈值：从±0.15降到±0.08，减少"持有"决策比例
        if quality_factor > 0.08:
            action = "买入"
            winning_side = "Bull"
        elif quality_factor < -0.08:
            action = "卖出"
            winning_side = "Bear"
        else:
            # 【优化3】质量差异较小时，使用综合优势判断，避免单一维度误判
            bull_advantage = (
                bull_scores["data_richness"] +
                bull_scores["logic_strength"] +
                bull_scores["confidence_score"]
            ) / 3
            bear_advantage = (
                bear_scores["data_richness"] +
                bear_scores["logic_strength"] +
                bear_scores["confidence_score"]
            ) / 3

            # 只需5%的综合优势即可触发方向性决策
            if bull_advantage > bear_advantage * 1.05:
                action = "买入"
                winning_side = "Bull"
            elif bear_advantage > bull_advantage * 1.05:
                action = "卖出"
                winning_side = "Bear"
            else:
                action = "持有"
                winning_side = "Tie"

        # 生成决策理由
        reason = self._generate_decision_reason(
            action, quality_factor, bull_scores, bear_scores, winning_side
        )

        logger.info(f"📊 动态置信度计算完成: {action} (置信度: {confidence:.2%})")
        logger.info(f"   看涨质量: {bull_scores['total_score']:.1f}, 看跌质量: {bear_scores['total_score']:.1f}")

        return {
            "confidence": round(confidence, 3),
            "action": action,
            "reason": reason,
            "quality_scores": {
                "bull": bull_scores,
                "bear": bear_scores,
                "quality_diff": quality_diff,
                "quality_factor": quality_factor
            },
            "winning_side": winning_side
        }

    def _analyze_side_quality(self, side: str, debate_rounds: List[Dict]) -> Dict:
        """
        分析某一方的辩论质量

        Args:
            side: "Bull" 或 "Bear"
            debate_rounds: 辩论轮次列表

        Returns:
            Dict: 质量评分详情
        """
        # 提取该方的所有发言
        responses = [
            r["response"] for r in debate_rounds
            if r.get("speaker") == side
        ]

        if not responses:
            return {
                "total_score": 0,
                "confidence_score": 0,
                "data_richness": 0,
                "logic_strength": 0,
                "response_count": 0,
                "avg_length": 0
            }

        # 计算各维度得分
        confidence_score = self._calculate_confidence_score(responses)
        data_richness = self._calculate_data_richness(responses)
        logic_strength = self._calculate_logic_strength(responses)

        # 计算回应质量（平均长度和回应次数）
        avg_length = sum(len(r) for r in responses) / len(responses)
        response_count = len(responses)

        # 长度奖励（适度长度表示充分论证）
        length_score = min(20, avg_length / 50)  # 1000字符 = 20分

        # 综合得分
        total_score = (
            confidence_score * 0.3 +    # 置信度关键词 30%
            data_richness * 0.35 +      # 数据支撑 35%
            logic_strength * 0.25 +     # 逻辑性 25%
            length_score * 0.1          # 长度适度 10%
        )

        return {
            "total_score": round(total_score, 2),
            "confidence_score": round(confidence_score, 2),
            "data_richness": round(data_richness, 2),
            "logic_strength": round(logic_strength, 2),
            "response_count": response_count,
            "avg_length": round(avg_length, 0)
        }

    def _calculate_confidence_score(self, responses: List[str]) -> float:
        """计算置信度关键词得分（0-100）"""
        score = 50.0  # 基础分
        full_text = "\n".join(responses)

        for keyword, weight in self.confidence_keywords.items():
            count = full_text.count(keyword)
            score += count * weight * 100

        return max(0, min(100, score))

    def _calculate_data_richness(self, responses: List[str]) -> float:
        """计算数据丰富度得分（0-100）"""
        full_text = "\n".join(responses)

        # 统计数据关键词出现次数
        data_count = sum(
            full_text.count(keyword)
            for keyword in self.data_support_keywords
        )

        # 识别具体数字
        number_pattern = r'\d+\.?\d*[%元]?'
        numbers = re.findall(number_pattern, full_text)
        number_count = len(numbers)

        # 数据丰富度评分
        score = min(100, (data_count * 5) + (number_count * 2))

        return score

    def _calculate_logic_strength(self, responses: List[str]) -> float:
        """计算逻辑强度得分（0-100）"""
        full_text = "\n".join(responses)

        # 统计逻辑关键词
        logic_count = sum(
            full_text.count(keyword)
            for keyword in self.logic_keywords
        )

        # 识别结构化论证（包含"核心论证"、"数据支撑"等标记）
        structure_markers = ["核心论证", "数据支撑", "目标价位", "风险应对", "反驳要点", "核心风险", "质疑要点"]
        structure_count = sum(
            full_text.count(marker)
            for marker in structure_markers
        )

        # 逻辑强度评分
        score = min(100, (logic_count * 8) + (structure_count * 15))

        return score

    def _generate_decision_reason(self,
                                  action: str,
                                  quality_factor: float,
                                  bull_scores: Dict,
                                  bear_scores: Dict,
                                  winning_side: str) -> str:
        """生成决策理由"""
        if winning_side == "Tie":
            return (f"看涨看跌观点质量接近（质量差异{abs(quality_factor):.1%}），"
                   f"牛方数据丰富度{bull_scores['data_richness']:.1f}，"
                   f"熊方逻辑强度{bear_scores['logic_strength']:.1f}，建议{action}")

        winner_scores = bull_scores if winning_side == "Bull" else bear_scores
        loser_scores = bear_scores if winning_side == "Bull" else bull_scores
        side_name = "看涨" if winning_side == "Bull" else "看跌"

        # 识别优势维度
        advantages = []
        if winner_scores['data_richness'] > loser_scores['data_richness'] + 10:
            advantages.append(f"数据支撑更充分({winner_scores['data_richness']:.1f} vs {loser_scores['data_richness']:.1f})")
        if winner_scores['logic_strength'] > loser_scores['logic_strength'] + 10:
            advantages.append(f"逻辑论证更严谨({winner_scores['logic_strength']:.1f} vs {loser_scores['logic_strength']:.1f})")
        if winner_scores['confidence_score'] > loser_scores['confidence_score'] + 5:
            advantages.append(f"论述更有信心({winner_scores['confidence_score']:.1f} vs {loser_scores['confidence_score']:.1f})")

        advantages_str = "、".join(advantages) if advantages else "综合质量更优"

        return (f"{side_name}观点在辩论中占据优势（质量差异{abs(quality_factor):.1%}），"
               f"{advantages_str}，"
               f"经过{bull_scores['response_count'] + bear_scores['response_count']}轮充分辩论")


# 便捷函数
def calculate_debate_confidence(debate_rounds: List[Dict],
                                min_confidence: float = 0.6,
                                max_confidence: float = 0.95) -> Dict:
    """
    计算辩论置信度的便捷函数

    Args:
        debate_rounds: 辩论轮次数据
        min_confidence: 最小置信度
        max_confidence: 最大置信度

    Returns:
        Dict: 置信度计算结果
    """
    calculator = DebateConfidenceCalculator()
    return calculator.calculate_dynamic_confidence(
        debate_rounds, min_confidence, max_confidence
    )