# -*- coding: utf-8 -*-
"""
智能新闻过滤器
基于TradingAgents-CN的新闻质量评估系统
"""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 可选的jieba分词支持
try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    logger.warning("jieba分词库未安装，将使用简单的文本相似度计算")

@dataclass
class NewsItem:
    """新闻项目数据类"""
    title: str
    content: str
    source: str
    timestamp: datetime
    url: Optional[str] = None
    relevance_score: float = 0.0
    quality_score: float = 0.0
    final_score: float = 0.0

class IntelligentNewsFilter:
    """智能新闻过滤器"""

    def __init__(self):
        self.stock_keywords = {
            '高相关': ['股价', '涨停', '跌停', '涨幅', '跌幅', '成交量', '市值', '财报', '业绩',
                     '营收', '利润', '亏损', '盈利', '分红', '派息', '重组', '并购'],
            '中相关': ['公司', '企业', '董事会', '股东', '投资', '融资', '上市', '退市',
                     '监管', '政策', '行业', '市场', '竞争', '合作'],
            '低相关': ['新闻', '消息', '报道', '宣布', '发布', '表示', '称', '表明']
        }

        self.quality_indicators = {
            '正面': ['权威', '官方', '证券', '交易所', '监管', '财经', '专业', '深度'],
            '负面': ['传言', '小道消息', '据说', '可能', '或许', '估计', '大概', '八卦'],
            '垃圾': ['点击', '震惊', '不看后悔', '你绝对想不到', '史上最', '内幕', '秘密']
        }

        self.duplicate_threshold = 0.8  # 重复内容相似度阈值

    def filter_news_batch(self, news_list: List[Dict], stock_symbol: str,
                         company_name: str = "") -> List[NewsItem]:
        """
        批量过滤新闻

        Args:
            news_list: 原始新闻列表
            stock_symbol: 股票代码
            company_name: 公司名称

        Returns:
            过滤后的高质量新闻列表
        """
        logger.info(f"开始过滤新闻，原始数量: {len(news_list)}")

        # 转换为NewsItem对象
        news_items = []
        for news in news_list:
            try:
                item = NewsItem(
                    title=news.get('title', ''),
                    content=news.get('content', ''),
                    source=news.get('source', ''),
                    timestamp=self._parse_timestamp(news.get('time', '')),
                    url=news.get('url', '')
                )
                news_items.append(item)
            except Exception as e:
                logger.warning(f"解析新闻失败: {e}")
                continue

        # 第一层：基础过滤
        basic_filtered = self._basic_filter(news_items, stock_symbol, company_name)
        logger.info(f"基础过滤后数量: {len(basic_filtered)}")

        # 第二层：质量评估
        quality_filtered = self._quality_assessment(basic_filtered)
        logger.info(f"质量评估后数量: {len(quality_filtered)}")

        # 第三层：去重过滤
        final_filtered = self._deduplication_filter(quality_filtered)
        logger.info(f"最终过滤后数量: {len(final_filtered)}")

        # 按最终得分排序
        final_filtered.sort(key=lambda x: x.final_score, reverse=True)

        return final_filtered

    def _basic_filter(self, news_items: List[NewsItem], stock_symbol: str,
                     company_name: str) -> List[NewsItem]:
        """基础过滤：相关性评估"""
        filtered_items = []

        for item in news_items:
            # 计算相关性得分
            relevance_score = self._calculate_relevance_score(
                item, stock_symbol, company_name
            )

            if relevance_score >= 0.3:  # 相关性阈值
                item.relevance_score = relevance_score
                filtered_items.append(item)
                logger.debug(f"新闻通过相关性过滤: {item.title[:30]}... (得分: {relevance_score:.2f})")
            else:
                logger.debug(f"新闻被相关性过滤: {item.title[:30]}... (得分: {relevance_score:.2f})")

        return filtered_items

    def _calculate_relevance_score(self, item: NewsItem, stock_symbol: str,
                                 company_name: str) -> float:
        """计算新闻相关性得分"""
        text = f"{item.title} {item.content}".lower()
        score = 0.0

        # 股票代码匹配 (最高权重)
        if stock_symbol.lower() in text or stock_symbol.replace('.', '').lower() in text:
            score += 0.5

        # 公司名称匹配
        if company_name and company_name in text:
            score += 0.3

        # 关键词匹配
        for level, keywords in self.stock_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in text)
            if level == '高相关':
                score += matches * 0.1
            elif level == '中相关':
                score += matches * 0.05
            else:  # 低相关
                score += matches * 0.02

        return min(score, 1.0)  # 限制最高分为1.0

    def _quality_assessment(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """质量评估：评估新闻质量"""
        filtered_items = []

        for item in news_items:
            quality_score = self._calculate_quality_score(item)

            if quality_score >= 0.2:  # 质量阈值
                item.quality_score = quality_score
                item.final_score = (item.relevance_score * 0.6 + quality_score * 0.4)
                filtered_items.append(item)
                logger.debug(f"新闻通过质量评估: {item.title[:30]}... (质量: {quality_score:.2f})")
            else:
                logger.debug(f"新闻被质量过滤: {item.title[:30]}... (质量: {quality_score:.2f})")

        return filtered_items

    def _calculate_quality_score(self, item: NewsItem) -> float:
        """计算新闻质量得分"""
        text = f"{item.title} {item.content}".lower()
        score = 0.5  # 基础分

        # 正面指标
        for keyword in self.quality_indicators['正面']:
            if keyword in text:
                score += 0.1

        # 负面指标
        for keyword in self.quality_indicators['负面']:
            if keyword in text:
                score -= 0.1

        # 垃圾指标 (严重扣分)
        for keyword in self.quality_indicators['垃圾']:
            if keyword in text:
                score -= 0.3

        # 内容长度评估
        content_length = len(item.content)
        if content_length > 500:
            score += 0.1
        elif content_length < 100:
            score -= 0.1

        # 时效性评估
        if item.timestamp:
            days_old = (datetime.now() - item.timestamp).days
            if days_old == 0:
                score += 0.1  # 今日新闻加分
            elif days_old > 7:
                score -= 0.1  # 超过一周扣分

        return max(score, 0.0)  # 确保非负

    def _deduplication_filter(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """去重过滤：移除重复内容"""
        unique_items = []

        for item in news_items:
            is_duplicate = False

            for existing_item in unique_items:
                similarity = self._calculate_similarity(item.title, existing_item.title)

                if similarity > self.duplicate_threshold:
                    is_duplicate = True
                    # 保留得分更高的新闻
                    if item.final_score > existing_item.final_score:
                        unique_items.remove(existing_item)
                        unique_items.append(item)
                        logger.debug(f"替换重复新闻: {existing_item.title[:20]} -> {item.title[:20]}")
                    else:
                        logger.debug(f"跳过重复新闻: {item.title[:20]}")
                    break

            if not is_duplicate:
                unique_items.append(item)

        return unique_items

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度"""
        # 基于词汇重叠的相似度计算
        if JIEBA_AVAILABLE:
            # 使用jieba分词
            words1 = set(jieba.cut(text1))
            words2 = set(jieba.cut(text2))
        else:
            # 简单字符级分词
            words1 = set(text1.split())
            words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0

    def _parse_timestamp(self, time_str: str) -> Optional[datetime]:
        """解析时间字符串"""
        if not time_str:
            return None

        try:
            # 尝试多种时间格式
            time_formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%m-%d %H:%M",
                "%H:%M"
            ]

            for fmt in time_formats:
                try:
                    return datetime.strptime(time_str, fmt)
                except ValueError:
                    continue

            # 如果都不匹配，返回当前时间
            return datetime.now()

        except Exception as e:
            logger.warning(f"解析时间失败: {time_str}, {e}")
            return datetime.now()

    def get_filter_statistics(self, original_count: int,
                            filtered_items: List[NewsItem]) -> Dict:
        """获取过滤统计信息"""
        if not filtered_items:
            return {
                "original_count": original_count,
                "filtered_count": 0,
                "filter_rate": 0.0,
                "avg_relevance": 0.0,
                "avg_quality": 0.0,
                "avg_final_score": 0.0
            }

        return {
            "original_count": original_count,
            "filtered_count": len(filtered_items),
            "filter_rate": (original_count - len(filtered_items)) / original_count if original_count > 0 else 0,
            "avg_relevance": sum(item.relevance_score for item in filtered_items) / len(filtered_items),
            "avg_quality": sum(item.quality_score for item in filtered_items) / len(filtered_items),
            "avg_final_score": sum(item.final_score for item in filtered_items) / len(filtered_items),
            "top_sources": self._get_top_sources(filtered_items)
        }

    def _get_top_sources(self, news_items: List[NewsItem]) -> List[Tuple[str, int]]:
        """获取主要新闻源统计"""
        source_count = {}
        for item in news_items:
            source = item.source or "未知来源"
            source_count[source] = source_count.get(source, 0) + 1

        return sorted(source_count.items(), key=lambda x: x[1], reverse=True)[:5]