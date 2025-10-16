# -*- coding: utf-8 -*-
"""情感面分析师 - 增强版，集成智能新闻过滤器"""

import pandas as pd
import numpy as np
from typing import Dict, List
import logging
import sys
import os
import requests
from datetime import datetime

from .base_analyst import BaseAnalyst

# 初始化logger
logger = logging.getLogger(__name__)

# 添加src路径到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# 导入新闻分析模块
try:
    try:
        # 尝试相对导入
        from ..utils.news_filter import IntelligentNewsFilter, NewsItem
        from ..utils.real_news_fetcher import RealNewsFetcher
    except (ImportError, ValueError):
        # 如果相对导入失败，尝试绝对导入
        from src.utils.news_filter import IntelligentNewsFilter, NewsItem
        from src.utils.real_news_fetcher import RealNewsFetcher
    NEWS_MODULES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"新闻模块导入失败: {e}")
    NEWS_MODULES_AVAILABLE = False

# 导入网页数据抓取模块
try:
    try:
        from ..data.web_scraper import scrape_news_for_sentiment, PLAYWRIGHT_AVAILABLE
    except (ImportError, ValueError):
        from src.data.web_scraper import scrape_news_for_sentiment, PLAYWRIGHT_AVAILABLE
    WEB_SCRAPER_AVAILABLE = True
    logger.info(f"✅ 网页抓取模块导入成功，PLAYWRIGHT_AVAILABLE={PLAYWRIGHT_AVAILABLE}")
except ImportError as e:
    logger.warning(f"⚠️ 网页抓取模块导入失败: {e}")
    logger.warning(f"   Python: {sys.executable}")
    WEB_SCRAPER_AVAILABLE = False
    PLAYWRIGHT_AVAILABLE = False
except Exception as e:
    logger.error(f"❌ 网页抓取模块导入时发生未知错误: {e}")
    logger.error(f"   Python: {sys.executable}")
    WEB_SCRAPER_AVAILABLE = False
    PLAYWRIGHT_AVAILABLE = False

# 如果新闻模块不可用，定义兼容性NewsItem类
if not NEWS_MODULES_AVAILABLE:
    class NewsItem:
        def __init__(self, title="", content="", source="", publish_time=None, relevance_score=0.0):
            self.title = title
            self.content = content
            self.source = source
            self.publish_time = publish_time or datetime.now()
            self.relevance_score = relevance_score

class SentimentAnalyst(BaseAnalyst):
    def __init__(self):
        super().__init__("sentiment")
        # 初始化新闻分析功能
        if NEWS_MODULES_AVAILABLE:
            try:
                self.news_filter = IntelligentNewsFilter()
                self.news_fetcher = RealNewsFetcher()
                self.use_real_news = True
                logger.info("新闻分析模块初始化成功")
            except Exception as e:
                logger.error(f"新闻模块初始化失败: {e}")
                self.news_filter = None
                self.news_fetcher = None
                self.use_real_news = False
        else:
            # 新闻分析功能不可用
            self.news_filter = None
            self.news_fetcher = None
            self.use_real_news = False
            logger.warning("新闻分析功能不可用")

        # 初始化网页数据抓取功能
        web_scraping_config = self.config_manager.get('analysis_settings.web_scraping', {})
        web_scraping_enabled = web_scraping_config.get('enabled', False)

        self.enable_web_scraping = (
            WEB_SCRAPER_AVAILABLE and
            PLAYWRIGHT_AVAILABLE and
            web_scraping_enabled
        )

        if self.enable_web_scraping:
            logger.info("✅ 网页数据抓取功能已启用（东方财富+雪球）")
        elif web_scraping_enabled and not (WEB_SCRAPER_AVAILABLE and PLAYWRIGHT_AVAILABLE):
            logger.warning("⚠️ 配置启用了网页抓取，但 Playwright 不可用")
        else:
            logger.info("⚠️ 网页数据抓取功能已禁用")
    
        

    def analyze_with_data(self, symbol: str, stock_data: pd.DataFrame, benchmark_data: Dict, market_data: Dict = None) -> Dict:
        """
        使用预获取的数据进行情感分析（避免重复数据获取）

        Args:
            symbol: 股票代码
            stock_data: 股票价格数据
            benchmark_data: 基准数据字典
            market_data: 预收集的市场数据（行业轮动、社交媒体等）

        Returns:
            分析结果字典
        """
        # 构造兼容的info和indicators参数
        info = {'longName': symbol}  # 简化处理
        indicators = {}

        # 首先进行传统分析
        analysis = self._traditional_analysis(symbol, stock_data, info, indicators)

        # 【已移除】不再在分析阶段抓取网页数据
        # 网页数据应该在数据获取阶段通过 main.py 的 _collect_data_batch() 获取
        # 并通过 market_data 参数传入

        # 检查是否通过 market_data 传入了网页数据
        if market_data and ('web_news' in market_data or 'web_discussions' in market_data):
            news_count = len(market_data.get('web_news', []))
            discussion_count = len(market_data.get('web_discussions', []))
            if news_count > 0 or discussion_count > 0:
                analysis["reasoning"].append(f"网页数据: {news_count}条新闻+{discussion_count}条讨论(已预收集)")

        # 如果启用了AI分析且模型可用，进行AI增强分析
        ai_config = self.config_manager.get_ai_config()
        if (self.ai_model and self.ai_model.is_available() and
            ai_config.get('enable_ai_analysis', False)):
            try:
                ai_analysis = self._ai_analysis(symbol, stock_data, info, indicators, analysis, market_data)
                analysis.update(ai_analysis)
                analysis["reasoning"].append("已使用AI增强分析（使用预收集市场数据）")
            except Exception as e:
                logger.error(f"AI分析失败: {e}")
                analysis["reasoning"].append("AI分析失败，使用传统分析")

        # 【新增】市场状态调整情绪分析
        if benchmark_data:
            try:
                adjusted_analysis = self._apply_market_sentiment_adjustment(
                    analysis, benchmark_data, stock_data
                )
                analysis = adjusted_analysis
            except Exception as e:
                logger.error(f"市场情绪调整失败: {e}")

        return analysis

    def analyze_with_news_data(self, symbol: str, stock_data: pd.DataFrame, benchmark_data: Dict, news_data: list, market_data: Dict = None) -> Dict:
        """
        使用预获取的数据和新闻数据进行情感分析

        Args:
            symbol: 股票代码
            stock_data: 股票价格数据
            benchmark_data: 基准数据字典
            news_data: 新闻数据列表
            market_data: 预收集的市场数据（行业轮动、社交媒体等）

        Returns:
            分析结果字典
        """
        # 先进行基础分析
        analysis = self.analyze_with_data(symbol, stock_data, benchmark_data, market_data)

        # 如果有新闻数据，增强分析
        if news_data:
            try:
                news_sentiment = self._analyze_news_sentiment(news_data)

                # 更新分析结果，使其与原有格式兼容
                analysis["news_count"] = news_sentiment.get('total_news_count', len(news_data))
                analysis["news_summary"] = news_sentiment.get('news_summary', '无新闻摘要')
                analysis["positive_news_count"] = news_sentiment.get('positive_news_count', 0)
                analysis["negative_news_count"] = news_sentiment.get('negative_news_count', 0)

                # 将情感评分转换为可读的情感描述
                news_score = news_sentiment.get('news_sentiment_score', 0)
                if news_score > 0.3:
                    analysis["news_sentiment"] = "积极"
                elif news_score < -0.3:
                    analysis["news_sentiment"] = "消极"
                else:
                    analysis["news_sentiment"] = "中性"

                analysis["reasoning"].append(f"已分析 {len(news_data)} 条预收集新闻: {analysis['news_summary']}")

                # 根据新闻情感调整推荐和信心度
                if news_score > 0.6:
                    if analysis['recommendation'] in ['持有', '买入']:
                        analysis['recommendation'] = '买入'
                    analysis['confidence'] = min(0.9, analysis['confidence'] + 0.1)
                    analysis["reasoning"].append("强烈积极新闻推动买入建议")
                elif news_score < -0.6:
                    if analysis['recommendation'] in ['持有', '卖出']:
                        analysis['recommendation'] = '卖出'
                    analysis['confidence'] = min(0.9, analysis['confidence'] + 0.1)
                    analysis["reasoning"].append("强烈消极新闻推动卖出建议")
                elif abs(news_score) > 0.2:
                    # 中等强度的新闻情感影响
                    analysis['confidence'] = min(0.9, analysis['confidence'] + 0.05)

            except Exception as e:
                logger.error(f"新闻情感分析失败: {e}")
                analysis["reasoning"].append("新闻情感分析失败，使用基础技术分析")
                # 设置默认值
                analysis["news_count"] = len(news_data)
                analysis["news_sentiment"] = "中性"

        return analysis

    def _analyze_news_sentiment(self, news_data: list) -> Dict:
        """分析新闻数据的情感倾向"""
        if not news_data:
            return {
                'news_sentiment_score': 0,
                'news_summary': '无新闻数据',
                'positive_news_count': 0,
                'negative_news_count': 0
            }

        positive_count = 0
        negative_count = 0
        neutral_count = 0

        # 简化的情感分析：基于关键词
        positive_keywords = ['上涨', '增长', '利好', '盈利', '突破', '创新', '获得', '合作', '签约', '中标']
        negative_keywords = ['下跌', '亏损', '利空', '风险', '下滑', '减少', '取消', '延期', '调查', '处罚']

        for news_item in news_data:
            title = news_item.get('title', '')
            content = news_item.get('content', '')
            text = title + ' ' + content

            positive_score = sum(1 for keyword in positive_keywords if keyword in text)
            negative_score = sum(1 for keyword in negative_keywords if keyword in text)

            if positive_score > negative_score:
                positive_count += 1
            elif negative_score > positive_score:
                negative_count += 1
            else:
                neutral_count += 1

        total_news = len(news_data)
        if total_news == 0:
            sentiment_score = 0
        else:
            sentiment_score = (positive_count - negative_count) / total_news

        return {
            'news_sentiment_score': round(sentiment_score, 3),
            'news_summary': f'积极新闻{positive_count}条，消极新闻{negative_count}条，中性新闻{neutral_count}条',
            'positive_news_count': positive_count,
            'negative_news_count': negative_count,
            'neutral_news_count': neutral_count,
            'total_news_count': total_news
        }

    def _traditional_analysis(self, symbol: str, data: pd.DataFrame, info: Dict, indicators: Dict) -> Dict:
        """传统情感面分析 - 集成新闻过滤器"""
        analysis = {
            "analyst_type": "情感面分析",
            "recommendation": "持有", 
            "confidence": 0.5,
            "reasoning": []
        }
        
        # 获取公司名称
        company_name = info.get('longName', '') or info.get('shortName', '') or symbol
        
        # 1. 价格趋势分析 (传统部分)
        if not data.empty and len(data) > 5:
            recent_returns = data['Close'].pct_change().tail(5)
            avg_return = recent_returns.mean()
            
            if not pd.isna(avg_return):
                if avg_return > 0.02:
                    analysis["reasoning"].append("近期涨势良好")
                    analysis["confidence"] += 0.1
                    analysis["recommendation"] = "买入"
                elif avg_return < -0.02:
                    analysis["reasoning"].append("近期跌幅较大")
                    analysis["confidence"] -= 0.1
                    analysis["recommendation"] = "卖出"
        
        # 2. 成交量分析
        if not data.empty and len(data) > 20:
            recent_volume = data['Volume'].tail(5).mean()
            avg_volume = data['Volume'].tail(20).mean()
            
            if not pd.isna(recent_volume) and not pd.isna(avg_volume) and avg_volume > 0:
                if recent_volume > avg_volume * 1.5:
                    analysis["reasoning"].append("成交量放大")
                    analysis["confidence"] += 0.1
        
        # 3. 新闻情感分析（基础分析中不获取新闻，避免网络请求）
        # 在基础分析中设置默认值，新闻分析在analyze_with_news_data中处理
        analysis["news_count"] = 0
        analysis["news_sentiment"] = "中性"
        analysis["reasoning"].append("基础分析模式，如需新闻分析请使用analyze_with_news_data方法")
        
        # 确保信心度在合理范围内
        analysis["confidence"] = self._ensure_confidence_range(analysis["confidence"])
        
        return analysis
    
    def _ai_analysis(self, symbol: str, data: pd.DataFrame, info: Dict,
                    indicators: Dict, traditional_analysis: Dict, market_data: Dict = None) -> Dict:
        """AI增强情感面分析"""
        # 计算近期收益率
        recent_returns = "N/A"
        if not data.empty and len(data) > 5:
            returns = data['Close'].pct_change().tail(5)
            if not returns.empty:
                recent_returns = f"{returns.mean() * 100:.2f}%"
        
        # 计算成交量趋势
        volume_trend = "N/A"
        if not data.empty and len(data) > 20:
            recent_volume = data['Volume'].tail(5).mean()
            avg_volume = data['Volume'].tail(20).mean()
            if avg_volume > 0:
                volume_trend = f"{(recent_volume - avg_volume) / avg_volume * 100:.1f}%"
        
        # 计算波动率
        volatility = "N/A"
        if not data.empty and len(data) > 20:
            returns = data['Close'].pct_change().tail(20)
            if not returns.empty:
                volatility = f"{returns.std() * 100:.2f}%"
        
        # 获取分析提示词
        prompt_config = self._get_ai_prompt_config()
        
        # 构建上下文数据
        context = {
            "symbol": symbol,
            "recent_returns": recent_returns,
            "volume_trend": volume_trend,
            "volatility": volatility,
            "traditional_analysis": traditional_analysis
        }
        
        # 获取公司名称
        company_name = info.get('longName', '') or info.get('shortName', '') or symbol

        # 获取增强情感数据（行业轮动+社交媒体）
        enhanced_sentiment_data = self._get_enhanced_sentiment_data(symbol, data, market_data)

        # 构建用户提示词
        user_prompt = prompt_config["user_prompt"].format(
            symbol=symbol,
            company_name=company_name,
            recent_returns=recent_returns,
            volume_trend=volume_trend,
            volatility=volatility,
            # 行业轮动与资金流向
            sector_heat_ranking=enhanced_sentiment_data.get('sector_heat_ranking', 'N/A'),
            sector_money_flow=enhanced_sentiment_data.get('sector_money_flow', 'N/A'),
            rotation_stage=enhanced_sentiment_data.get('rotation_stage', 'N/A'),
            style_shift=enhanced_sentiment_data.get('style_shift', 'N/A'),
            # 社交媒体与市场关注
            longhu_appearances=enhanced_sentiment_data.get('longhu_appearances', 'N/A'),
            social_mentions=enhanced_sentiment_data.get('social_mentions', 'N/A'),
            institutional_attention=enhanced_sentiment_data.get('institutional_attention', 'N/A'),
            retail_discussion=enhanced_sentiment_data.get('retail_discussion', 'N/A'),
            # 市场情绪与风险偏好
            market_risk_preference=enhanced_sentiment_data.get('market_risk_preference', 'N/A'),
            beta_sentiment_impact=enhanced_sentiment_data.get('beta_sentiment_impact', 'N/A'),
            systematic_sentiment_risk=enhanced_sentiment_data.get('systematic_sentiment_risk', 'N/A')
        )
        
        # 调用AI模型
        ai_response = self.ai_model.generate_analysis(user_prompt, context)
        
        # 解析AI响应并增强分析
        enhanced_analysis = {}
        
        # 使用基类的通用合并逻辑
        ai_recommendation = self._extract_ai_recommendation(ai_response)
        return self._combine_traditional_and_ai_analysis(traditional_analysis, ai_recommendation, ai_response)
    
    def _analyze_news_sentiment_with_fetch(self, symbol: str, company_name: str) -> Dict:
        """分析新闻情感（包含获取过程，已废弃）"""
        try:
            # 获取新闻数据 (模拟实现，可替换为真实新闻API)
            raw_news = self._fetch_stock_news(symbol, company_name)
            
            if not raw_news:
                logger.info(f"未获取到{symbol}的新闻数据，使用中性评估")
                return {
                    "sentiment": "中性", 
                    "confidence_adjustment": 0.0,
                    "reasoning": ["无新闻数据，基于中性舆论进行评估"],
                    "news_count": 0,
                    "avg_news_quality": 0.5
                }
            
            # 使用智能新闻过滤器
            filtered_news = self.news_filter.filter_news_batch(
                raw_news, symbol, company_name
            )
            
            if not filtered_news:
                logger.info(f"过滤后无有效新闻: {symbol}，使用中性评估")
                return {
                    "sentiment": "中性",
                    "confidence_adjustment": 0.0,
                    "reasoning": ["无有效新闻，基于中性舆论进行评估"],
                    "news_count": 0,
                    "avg_news_quality": 0.5
                }
            
            # 分析过滤后新闻的情感倾向
            sentiment_analysis = self._analyze_filtered_news_sentiment(filtered_news)
            
            # 获取过滤统计
            filter_stats = self.news_filter.get_filter_statistics(len(raw_news), filtered_news)
            
            logger.info(f"新闻情感分析完成 {symbol}: "
                       f"原始{filter_stats['original_count']}条 -> "
                       f"过滤后{filter_stats['filtered_count']}条, "
                       f"情感倾向: {sentiment_analysis['sentiment']}")
            
            # 生成最近新闻时间信息摘要
            recent_news_summary = self._generate_news_time_summary(raw_news)
            
            return {
                **sentiment_analysis,
                "news_count": len(filtered_news),
                "original_news_count": len(raw_news),
                "filter_rate": filter_stats['filter_rate'],
                "avg_news_quality": filter_stats['avg_quality'],
                "recent_news_info": recent_news_summary
            }
            
        except Exception as e:
            logger.error(f"新闻情感分析失败 {symbol}: {e}")
            return None
    
    def _generate_news_time_summary(self, news_list: List[Dict]) -> str:
        """生成新闻时间信息摘要"""
        if not news_list:
            return "- 无新闻数据"
            
        from datetime import datetime
        recent_news = []
        old_news = []
        current_time = datetime.now()
        
        for news in news_list[:10]:  # 只分析前10条新闻
            time_desc = news.get('time_description', '未知时间')
            days_ago = news.get('days_ago', -1)
            is_recent = news.get('is_recent', False)
            title = news.get('title', '')[:30] + '...' if len(news.get('title', '')) > 30 else news.get('title', '')
            
            if is_recent and days_ago >= 0:
                # 检查是否为关键词新闻
                is_keyword_news = news.get('is_keyword_news', False)
                search_keyword = news.get('search_keyword', '')
                
                if is_keyword_news and search_keyword:
                    old_news.append(f"  • [{search_keyword}] {time_desc}: {title}")
                else:
                    recent_news.append(f"  • {time_desc}: {title}")
            elif days_ago >= 0:
                # 检查是否为关键词新闻
                is_keyword_news = news.get('is_keyword_news', False) 
                search_keyword = news.get('search_keyword', '')
                
                if is_keyword_news and search_keyword:
                    old_news.append(f"  • [{search_keyword}] {time_desc}: {title}")
                else:
                    old_news.append(f"  • {time_desc}: {title}")
                
        summary_parts = []
        keyword_news = []
        
        # 分离关键词新闻到单独显示
        for item in old_news[:]:
            if '[' in item and ']' in item:
                keyword_news.append(item)
                old_news.remove(item)
        
        if recent_news:
            summary_parts.append("- 最近新闻 (3天内):")
            summary_parts.extend(recent_news[:3])  # 最多显示3条最近新闻
            
        if old_news:
            summary_parts.append("- 较早新闻:")
            summary_parts.extend(old_news[:2])  # 最多显示2条较早新闻
            
        if keyword_news:
            summary_parts.append("- 相关行业/概念新闻:")
            summary_parts.extend(keyword_news[:3])  # 最多显示3条关键词新闻
            
        if not recent_news and not old_news and not keyword_news:
            summary_parts.append("- 新闻时间信息解析失败")
            
        return "\n".join(summary_parts)
    
    def _fetch_stock_news(self, symbol: str, company_name: str) -> List[Dict]:
        """获取股票新闻 (仅真实数据)"""
        
        # 只尝试获取真实新闻数据
        if self.use_real_news and self.news_fetcher is not None:
            try:
                logger.info(f"正在获取真实新闻数据: {company_name} ({symbol})")
                real_news = self.news_fetcher.fetch_stock_news(symbol, company_name)

                if real_news and len(real_news) > 0:
                    logger.info(f"成功获取{len(real_news)}条真实新闻: {company_name}")
                    return real_news
                else:
                    logger.warning(f"未获取到真实新闻数据: {company_name}")
                    return []

            except Exception as e:
                logger.error(f"获取真实新闻失败: {company_name}, 错误: {e}")
                return []
        elif self.use_real_news and self.news_fetcher is None:
            logger.warning(f"新闻获取器未初始化，无法获取真实新闻: {company_name}")
            return []
        
        # 如果未启用真实新闻，返回空列表
        logger.warning(f"真实新闻功能未启用: {company_name}")
        return []
    
    def _fetch_mock_news(self, symbol: str, company_name: str) -> List[Dict]:
        """获取模拟新闻数据 (原逻辑)"""
        mock_news = [
            {
                'title': f'{company_name}发布季度财报，业绩超预期',
                'content': f'{company_name}最新发布的季度财报显示，公司营收和利润均超出市场预期，展现出强劲的增长势头。',
                'source': '财经新闻',
                'time': '2小时前',
                'url': f'https://example.com/news/{symbol}/1'
            },
            {
                'title': f'机构看好{company_name}长期发展前景',
                'content': f'多家投资机构发布研报，看好{company_name}在行业中的竞争地位和长期发展前景。',
                'source': '投资快报',
                'time': '5小时前', 
                'url': f'https://example.com/news/{symbol}/2'
            },
            {
                'title': f'{company_name}股价震荡，投资者关注后市走向',
                'content': f'{company_name}近期股价出现震荡，市场对其后续走势存在分歧，投资者密切关注。',
                'source': '股市动态',
                'time': '1天前',
                'url': f'https://example.com/news/{symbol}/3'
            },
            {
                'title': '点击不看后悔！某股票内幕消息大爆料',
                'content': '传言某公司内部消息，据说可能有重大变动，但消息真实性存疑。',
                'source': '小道消息',
                'time': '2天前',
                'url': 'https://example.com/fake/news'
            }
        ]
        
        return mock_news[:3]  # 排除垃圾新闻
    
    def set_real_news_enabled(self, enabled: bool):
        """设置是否启用真实新闻"""
        self.use_real_news = enabled
        logger.info(f"真实新闻功能{'启用' if enabled else '禁用'}")
    
    def get_news_cache_stats(self) -> Dict:
        """获取新闻缓存统计"""
        if hasattr(self.news_fetcher, 'get_cache_stats'):
            return self.news_fetcher.get_cache_stats()
        return {"message": "缓存统计不可用"}
    
    def clear_news_cache(self):
        """清理新闻缓存"""
        if hasattr(self.news_fetcher, 'clear_cache'):
            self.news_fetcher.clear_cache()
            logger.info("新闻缓存已清理")
    
    def _analyze_filtered_news_sentiment(self, news_items: List[NewsItem]) -> Dict:
        """分析过滤后新闻的情感倾向 - 增强版分析算法"""
        if not news_items:
            return {
                "sentiment": "中性",
                "confidence_adjustment": 0.0,
                "reasoning": ["无可用新闻"]
            }
        
        # 增强的关键词词典 (参考TradingAgents-CN的深度分析)
        positive_keywords = {
            # 业绩相关
            '超预期': 3.0, '业绩增长': 2.5, '营收增长': 2.5, '利润增长': 2.8, '盈利': 2.0,
            # 评级相关  
            '买入': 2.8, '推荐': 2.2, '看好': 2.5, '上调': 2.3, '目标价上调': 3.0,
            # 趋势相关
            '增长': 2.0, '上涨': 2.2, '强劲': 2.6, '突破': 2.4, '创新高': 3.2,
            # 利好消息
            '利好': 2.5, '积极': 2.0, '乐观': 2.3, '机会': 1.8, '潜力': 2.0
        }
        
        negative_keywords = {
            # 业绩相关
            '亏损': 3.0, '下滑': 2.5, '减少': 2.0, '不及预期': 2.8, '业绩下降': 3.0,
            # 评级相关
            '卖出': 2.8, '下调': 2.3, '减持': 2.0, '目标价下调': 3.0,
            # 风险相关
            '风险': 2.2, '警告': 2.8, '困难': 2.4, '问题': 2.0, '调查': 2.6,
            # 趋势相关
            '下跌': 2.5, '震荡': 1.8, '疲软': 2.2, '压力': 2.0, '不利': 2.3
        }
        
        # 计算加权情感得分
        sentiment_analysis = self._calculate_weighted_sentiment(news_items, positive_keywords, negative_keywords)
        
        # 考虑新闻时效性 (TradingAgents-CN的时效性权重)
        time_weighted_score = self._apply_time_weight(news_items, sentiment_analysis['base_score'])
        
        # 考虑新闻来源可信度
        source_weighted_score = self._apply_source_weight(news_items, time_weighted_score)
        
        # 最终情感判断
        final_sentiment = self._determine_final_sentiment(source_weighted_score)
        
        return {
            **final_sentiment,
            "reasoning": sentiment_analysis['reasoning'],
            "base_score": sentiment_analysis['base_score'],
            "time_weighted_score": time_weighted_score,
            "final_score": source_weighted_score,
            "news_count": len(news_items),
            "high_quality_news_count": len([item for item in news_items if item.final_score > 0.7])
        }
    
    def _calculate_weighted_sentiment(self, news_items: List[NewsItem], 
                                    positive_keywords: Dict[str, float], 
                                    negative_keywords: Dict[str, float]) -> Dict:
        """计算加权情感得分"""
        positive_score = 0
        negative_score = 0
        total_weight = 0
        reasoning = []
        
        for item in news_items:
            # 新闻质量权重
            weight = item.final_score
            text = f"{item.title} {item.content}"
            
            # 计算加权正面分数
            item_positive = 0
            item_negative = 0
            
            for keyword, keyword_weight in positive_keywords.items():
                count = text.count(keyword)
                if count > 0:
                    item_positive += count * keyword_weight
            
            for keyword, keyword_weight in negative_keywords.items():
                count = text.count(keyword)
                if count > 0:
                    item_negative += count * keyword_weight
            
            # 应用新闻质量权重
            weighted_positive = item_positive * weight
            weighted_negative = item_negative * weight
            
            positive_score += weighted_positive
            negative_score += weighted_negative
            total_weight += weight
            
            # 记录重要新闻标题 (高质量且有明显情感倾向)
            if (len(reasoning) < 3 and item.final_score > 0.6 and 
                (weighted_positive > 1.0 or weighted_negative > 1.0)):
                sentiment_type = "正面" if weighted_positive > weighted_negative else "负面"
                reasoning.append(f"[{sentiment_type}] {item.title[:35]}...")
        
        base_score = (positive_score - negative_score) / max(total_weight, 1)
        
        return {
            "base_score": base_score,
            "positive_score": positive_score,
            "negative_score": negative_score,
            "total_weight": total_weight,
            "reasoning": reasoning
        }
    
    def _apply_time_weight(self, news_items: List[NewsItem], base_score: float) -> float:
        """应用时效性权重"""
        if not news_items:
            return base_score
        
        # 计算平均新闻时效性权重
        total_time_weight = 0
        for item in news_items:
            # 假设recent_score反映新闻的时效性
            time_weight = getattr(item, 'recent_score', 0.5)  
            total_time_weight += time_weight
        
        avg_time_weight = total_time_weight / len(news_items)
        
        # 新闻越新，情感得分影响越大
        time_factor = 0.5 + avg_time_weight * 0.5  # 权重范围 0.5-1.0
        
        return base_score * time_factor
    
    def _apply_source_weight(self, news_items: List[NewsItem], score: float) -> float:
        """应用来源可信度权重"""
        if not news_items:
            return score
        
        # 计算平均来源权重
        total_source_weight = 0
        for item in news_items:
            source_weight = getattr(item, 'source_weight', 0.5)
            total_source_weight += source_weight
        
        avg_source_weight = total_source_weight / len(news_items)
        
        # 来源越可靠，情感得分影响越大
        source_factor = 0.6 + avg_source_weight * 0.4  # 权重范围 0.6-1.0
        
        return score * source_factor
    
    def _determine_final_sentiment(self, final_score: float) -> Dict:
        """确定最终情感判断"""
        # 动态阈值 (比简单固定阈值更精确)
        strong_positive_threshold = 1.5
        positive_threshold = 0.4
        negative_threshold = -0.4  
        strong_negative_threshold = -1.5
        
        if final_score >= strong_positive_threshold:
            sentiment = "积极"
            confidence_adjustment = min(0.2, final_score * 0.1)
        elif final_score >= positive_threshold:
            sentiment = "积极"
            confidence_adjustment = min(0.15, final_score * 0.08)
        elif final_score <= strong_negative_threshold:
            sentiment = "消极"
            confidence_adjustment = max(-0.2, final_score * 0.1)
        elif final_score <= negative_threshold:
            sentiment = "消极" 
            confidence_adjustment = max(-0.15, final_score * 0.08)
        else:
            sentiment = "中性"
            confidence_adjustment = final_score * 0.02  # 轻微调整
        
        return {
            "sentiment": sentiment,
            "confidence_adjustment": confidence_adjustment,
            "sentiment_strength": abs(final_score)
        }

    def _get_enhanced_sentiment_data(self, symbol: str, data: pd.DataFrame, market_data: Dict = None) -> Dict:
        """获取增强情感数据（行业轮动+社交媒体）"""
        try:
            enhanced_data = {}

            # 获取行业轮动数据（使用预收集的数据）
            sector_rotation_data = market_data.get('sector_rotation_data', {}) if market_data else {}
            sector_data = self._get_sector_rotation_sentiment_data(symbol, sector_rotation_data)
            enhanced_data.update(sector_data)

            # 获取社交媒体数据（使用预收集的数据）
            social_media_data = market_data.get('social_media_data', {}) if market_data else {}
            social_data = self._get_social_media_sentiment_data(symbol, social_media_data)
            enhanced_data.update(social_data)

            # 获取市场情绪风险数据
            risk_data = self._get_market_sentiment_risk_data(symbol, data)
            enhanced_data.update(risk_data)

            return enhanced_data

        except Exception as e:
            logger.error(f"获取增强情感数据失败: {e}")
            return self._get_default_sentiment_data()

    def _get_sector_rotation_sentiment_data(self, symbol: str, sector_rotation_data: Dict = None) -> Dict:
        """获取行业轮动情感数据（使用预收集数据）"""
        try:
            # 使用预收集的行业轮动数据
            if sector_rotation_data and isinstance(sector_rotation_data, dict):
                # 从预收集数据中提取信息
                longhu_data = sector_rotation_data.get('longhu_data', [])
                sector_flow_data = sector_rotation_data.get('sector_flow_data', {})

                # 分析行业热度
                if longhu_data:
                    sector_heat_ranking = f"前{len(longhu_data)}活跃股票"
                    sector_money_flow = "资金净流入"
                    rotation_stage = "轮动活跃期"
                    style_shift = "成长风格"
                else:
                    sector_heat_ranking = "数据不足"
                    sector_money_flow = "N/A"
                    rotation_stage = "N/A"
                    style_shift = "N/A"

                # 如果有具体的资金流向数据，使用它
                if sector_flow_data:
                    sector_money_flow = sector_flow_data.get('net_flow_status', sector_money_flow)
                    rotation_stage = sector_flow_data.get('rotation_stage', rotation_stage)

            else:
                # 没有预收集数据时的默认值
                sector_heat_ranking = "数据未收集"
                sector_money_flow = "N/A"
                rotation_stage = "N/A"
                style_shift = "N/A"

            return {
                'sector_heat_ranking': sector_heat_ranking,
                'sector_money_flow': sector_money_flow,
                'rotation_stage': rotation_stage,
                'style_shift': style_shift
            }

        except Exception as e:
            logger.error(f"处理行业轮动情感数据失败: {e}")
            return {
                'sector_heat_ranking': 'N/A',
                'sector_money_flow': 'N/A',
                'rotation_stage': 'N/A',
                'style_shift': 'N/A'
            }

    def _get_social_media_sentiment_data(self, symbol: str, social_media_data: Dict = None) -> Dict:
        """获取社交媒体情感数据（使用预收集数据）"""
        try:
            # 使用预收集的社交媒体数据
            if social_media_data and isinstance(social_media_data, dict):
                # 从预收集数据中提取信息
                longhu_data = social_media_data.get('longhu_data', [])

                # 检查是否在龙虎榜中出现（作为关注度指标）
                longhu_appearances = 0
                if longhu_data:
                    for stock_info in longhu_data:
                        if symbol in str(stock_info):
                            longhu_appearances += 1

                # 从预收集数据中获取社交媒体指标
                social_mentions = social_media_data.get('social_mentions', 'N/A')
                institutional_attention = social_media_data.get('institutional_attention', 'N/A')
                retail_discussion = social_media_data.get('retail_discussion', 'N/A')

                # 如果没有直接的社交媒体数据，基于龙虎榜数据推断
                if social_mentions == 'N/A':
                    if longhu_appearances > 0:
                        social_mentions = "高"
                        institutional_attention = "关注"
                        retail_discussion = "活跃"
                    else:
                        social_mentions = "低"
                        institutional_attention = "一般"
                        retail_discussion = "平淡"

            else:
                # 没有预收集数据时的默认值
                longhu_appearances = 'N/A'
                social_mentions = "数据未收集"
                institutional_attention = "N/A"
                retail_discussion = "N/A"

            return {
                'longhu_appearances': longhu_appearances,
                'social_mentions': social_mentions,
                'institutional_attention': institutional_attention,
                'retail_discussion': retail_discussion
            }

        except Exception as e:
            logger.error(f"处理社交媒体情感数据失败: {e}")
            return {
                'longhu_appearances': 'N/A',
                'social_mentions': 'N/A',
                'institutional_attention': 'N/A',
                'retail_discussion': 'N/A'
            }

    def _get_market_sentiment_risk_data(self, symbol: str, data: pd.DataFrame) -> Dict:
        """获取市场情绪风险数据"""
        try:
            # 计算基本的情绪风险指标
            if data.empty or len(data) < 20:
                return {
                    'market_risk_preference': 'N/A',
                    'beta_sentiment_impact': 'N/A',
                    'systematic_sentiment_risk': 'N/A'
                }

            # 基于波动率判断市场风险偏好
            returns = data['Close'].pct_change().tail(20)
            volatility = returns.std()

            if volatility > 0.03:
                market_risk_preference = "风险偏好高"
            elif volatility > 0.015:
                market_risk_preference = "风险偏好中等"
            else:
                market_risk_preference = "风险偏好低"

            # 模拟Beta情绪影响（实际应该从市场相关性分析中获取）
            # 假设高波动率对应高Beta影响
            if volatility > 0.03:
                beta_sentiment_impact = "情绪放大效应强"
                systematic_sentiment_risk = "30"
            elif volatility > 0.015:
                beta_sentiment_impact = "情绪影响适中"
                systematic_sentiment_risk = "15"
            else:
                beta_sentiment_impact = "情绪影响较小"
                systematic_sentiment_risk = "5"

            return {
                'market_risk_preference': market_risk_preference,
                'beta_sentiment_impact': beta_sentiment_impact,
                'systematic_sentiment_risk': systematic_sentiment_risk
            }

        except Exception as e:
            logger.error(f"获取市场情绪风险数据失败: {e}")
            return {
                'market_risk_preference': 'N/A',
                'beta_sentiment_impact': 'N/A',
                'systematic_sentiment_risk': 'N/A'
            }

    def _get_default_sentiment_data(self) -> Dict:
        """返回默认的情感数据"""
        return {
            'sector_heat_ranking': 'N/A',
            'sector_money_flow': 'N/A',
            'rotation_stage': 'N/A',
            'style_shift': 'N/A',
            'longhu_appearances': 'N/A',
            'social_mentions': 'N/A',
            'institutional_attention': 'N/A',
            'retail_discussion': 'N/A',
            'market_risk_preference': 'N/A',
            'beta_sentiment_impact': 'N/A',
            'systematic_sentiment_risk': 'N/A'
        }

    def _apply_market_sentiment_adjustment(self, analysis: Dict,
                                          benchmark_data: Dict,
                                          stock_data: pd.DataFrame) -> Dict:
        """
        根据市场状态调整情绪分析结果

        在市场恐慌时，好消息影响减弱；在市场狂热时，坏消息影响减弱
        """
        try:
            # 获取市场状态
            market_state = benchmark_data.get('market_state')
            stock_beta = benchmark_data.get('stock_beta', 1.0)

            if not market_state:
                logger.debug("无市场状态数据，跳过市场情绪调整")
                return analysis

            # 获取市场趋势
            trend = market_state.get('trend')
            if not trend:
                return analysis

            trend_str = str(trend.value) if hasattr(trend, 'value') else str(trend)
            daily_return = market_state.get('daily_return', 0)
            risk_level = market_state.get('risk_level', '中')

            # 记录原始建议
            original_rec = analysis['recommendation']
            original_conf = analysis['confidence']

            # 情绪调整逻辑
            adjustment_info = self._calculate_sentiment_market_adjustment(
                original_rec, original_conf, trend_str, daily_return,
                risk_level, stock_beta
            )

            if adjustment_info['adjusted']:
                # 更新分析结果
                adjusted_analysis = analysis.copy()
                adjusted_analysis['recommendation'] = adjustment_info['new_recommendation']
                adjusted_analysis['confidence'] = adjustment_info['new_confidence']

                # 添加市场调整信息
                adjusted_analysis['original_sentiment_recommendation'] = original_rec
                adjusted_analysis['original_sentiment_confidence'] = original_conf
                adjusted_analysis['market_sentiment_adjustment'] = adjustment_info['reason']

                # 添加到推理中
                adjusted_analysis['reasoning'].append(
                    f"市场情绪调整: {adjustment_info['reason']}"
                )

                logger.info(f"情绪分析已调整: {original_rec}({original_conf:.0%}) → "
                          f"{adjustment_info['new_recommendation']}({adjustment_info['new_confidence']:.0%})")

                return adjusted_analysis

            return analysis

        except Exception as e:
            logger.error(f"市场情绪调整异常: {e}")
            return analysis

    def _calculate_sentiment_market_adjustment(self, original_rec: str,
                                              original_conf: float,
                                              trend: str, daily_return: float,
                                              risk_level: str, stock_beta: float) -> Dict:
        """
        计算基于市场状态的情绪调整

        核心理念：
        1. 市场恐慌时，正面情绪的影响力大幅下降
        2. 市场狂热时，负面情绪的影响力下降
        3. 高Beta股票对市场情绪更敏感
        """
        adjustment = {
            'adjusted': False,
            'new_recommendation': original_rec,
            'new_confidence': original_conf,
            'reason': ''
        }

        # 市场暴跌场景（日跌幅 < -4%）
        if '暴跌' in trend or 'CRASH' in trend or daily_return < -0.04:
            # 市场恐慌，情绪分析可靠性下降
            if original_rec == '买入':
                # 买入信号在暴跌中不可信，降级为持有
                adjustment['adjusted'] = True
                adjustment['new_recommendation'] = '持有'
                adjustment['new_confidence'] = min(original_conf + 0.1, 0.85)
                adjustment['reason'] = f"市场暴跌({daily_return:.1%})，市场恐慌压倒个股情绪，买入降级为持有"

            elif original_rec == '持有':
                # 高Beta股票在暴跌中更危险
                if stock_beta > 1.2:
                    adjustment['adjusted'] = True
                    adjustment['new_recommendation'] = '卖出'
                    adjustment['new_confidence'] = min(original_conf + 0.15, 0.90)
                    adjustment['reason'] = f"市场暴跌+高Beta({stock_beta:.2f})，恐慌情绪加剧，建议卖出"
                else:
                    # 低Beta股票相对防御，但降低信心
                    adjustment['adjusted'] = True
                    adjustment['new_confidence'] = max(original_conf - 0.05, 0.4)
                    adjustment['reason'] = f"市场暴跌，但Beta适中({stock_beta:.2f})，维持持有但降低信心"

            elif original_rec == '卖出':
                # 卖出信号在暴跌中更可信
                adjustment['adjusted'] = True
                adjustment['new_confidence'] = min(original_conf + 0.15, 0.95)
                adjustment['reason'] = f"市场暴跌({daily_return:.1%})，卖出信号得到市场确认"

        # 市场急跌场景（-4% < 日跌幅 < -2%）
        elif '急跌' in trend or 'STRONG_BEAR' in trend or (-0.04 < daily_return < -0.02):
            if original_rec == '买入':
                # 买入信号谨慎对待
                if stock_beta > 1.2:
                    adjustment['adjusted'] = True
                    adjustment['new_recommendation'] = '持有'
                    adjustment['new_confidence'] = original_conf
                    adjustment['reason'] = f"市场急跌+高Beta({stock_beta:.2f})，买入信号不可靠，建议持有观望"
                else:
                    adjustment['adjusted'] = True
                    adjustment['new_confidence'] = max(original_conf - 0.1, 0.4)
                    adjustment['reason'] = f"市场急跌({daily_return:.1%})，降低买入信心"

            elif original_rec == '持有' and stock_beta > 1.3:
                # 超高Beta股票需警惕
                adjustment['adjusted'] = True
                adjustment['new_confidence'] = max(original_conf - 0.1, 0.4)
                adjustment['reason'] = f"市场急跌+超高Beta({stock_beta:.2f})，持有风险增加"

        # 市场温和下跌场景（-2% < 日跌幅 < -0.5%）
        elif '下跌' in trend or 'BEAR' in trend or (-0.02 < daily_return < -0.005):
            if original_rec == '买入' and stock_beta > 1.2:
                # 高Beta股票在下跌市中买入需谨慎
                adjustment['adjusted'] = True
                adjustment['new_confidence'] = max(original_conf - 0.08, 0.45)
                adjustment['reason'] = f"市场下跌+高Beta({stock_beta:.2f})，情绪乐观但需谨慎"

        # 市场强势上涨场景（日涨幅 > 2%）
        elif '强势' in trend or 'STRONG_BULL' in trend or daily_return > 0.02:
            # 市场狂热，负面情绪影响减弱
            if original_rec == '卖出':
                # 卖出信号在强势上涨中可能过于悲观
                if stock_beta > 1.1:
                    adjustment['adjusted'] = True
                    adjustment['new_recommendation'] = '持有'
                    adjustment['new_confidence'] = max(original_conf - 0.1, 0.5)
                    adjustment['reason'] = f"市场强势上涨({daily_return:.1%})+高Beta({stock_beta:.2f})，负面情绪被市场热情抵消"
                else:
                    adjustment['adjusted'] = True
                    adjustment['new_confidence'] = max(original_conf - 0.08, 0.5)
                    adjustment['reason'] = f"市场强势上涨({daily_return:.1%})，卖出信号可能过于悲观"

            elif original_rec == '买入' and stock_beta > 1.1:
                # 高Beta股票在上涨中更有动力
                adjustment['adjusted'] = True
                adjustment['new_confidence'] = min(original_conf + 0.1, 0.92)
                adjustment['reason'] = f"市场强势+高Beta({stock_beta:.2f})，买入情绪得到市场支持"

        # 市场温和上涨场景（0.5% < 日涨幅 < 2%）
        elif '上涨' in trend or 'BULL' in trend or (0.005 < daily_return < 0.02):
            if original_rec == '买入' and stock_beta > 1.1:
                adjustment['adjusted'] = True
                adjustment['new_confidence'] = min(original_conf + 0.05, 0.88)
                adjustment['reason'] = f"市场温和上涨+高Beta({stock_beta:.2f})，情绪积极得到验证"

        return adjustment
