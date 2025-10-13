# -*- coding: utf-8 -*-
"""
网页数据抓取器 - 使用 Playwright 抓取财经网站数据
用于增强情感分析和社交媒体监控
"""

import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("⚠️ Playwright 未安装，网页抓取功能不可用")


class WebScraper:
    """网页数据抓取器"""

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        初始化抓取器

        Args:
            headless: 是否使用无头模式
            timeout: 超时时间（毫秒）
        """
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self.playwright = None

        if not PLAYWRIGHT_AVAILABLE:
            logger.error("❌ Playwright 不可用，无法初始化 WebScraper")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        if not PLAYWRIGHT_AVAILABLE:
            return self

        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            logger.info("✅ Playwright 浏览器启动成功")
        except Exception as e:
            logger.error(f"❌ 启动浏览器失败: {e}")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.browser:
            await self.browser.close()
            logger.debug("浏览器已关闭")
        if self.playwright:
            await self.playwright.stop()

    async def scrape_eastmoney_news(self, symbol: str, max_news: int = 10) -> List[Dict]:
        """
        抓取东方财富个股新闻

        Args:
            symbol: 股票代码（如 '600519'）
            max_news: 最大新闻数量

        Returns:
            List[Dict]: 新闻列表
        """
        if not self.browser:
            logger.warning("浏览器未初始化")
            return []

        news_list = []

        try:
            # 东方财富个股页面
            url = f"https://quote.eastmoney.com/{symbol}.html"
            logger.info(f"📰 抓取东方财富新闻: {url}")

            page = await self.browser.new_page()
            await page.goto(url, timeout=self.timeout)

            # 等待新闻区域加载
            try:
                await page.wait_for_selector(".news-list, .newslist", timeout=10000)
            except PlaywrightTimeoutError:
                logger.warning(f"⚠️ 新闻列表加载超时: {symbol}")
                await page.close()
                return []

            # 提取新闻数据（需要根据实际页面结构调整选择器）
            news_items = await page.query_selector_all(".news-item, li.newslist")

            for i, item in enumerate(news_items[:max_news]):
                try:
                    # 提取标题
                    title_elem = await item.query_selector("a, .title")
                    if not title_elem:
                        continue

                    title = await title_elem.inner_text()
                    link = await title_elem.get_attribute("href")

                    # 提取时间
                    time_elem = await item.query_selector(".time, .date")
                    time_text = await time_elem.inner_text() if time_elem else "未知时间"

                    # 补全链接
                    if link and not link.startswith("http"):
                        link = f"https://finance.eastmoney.com{link}"

                    news_list.append({
                        "title": title.strip(),
                        "link": link,
                        "time": time_text.strip(),
                        "source": "东方财富",
                        "symbol": symbol,
                        "crawl_time": datetime.now().isoformat()
                    })

                    logger.debug(f"  - {title[:30]}...")

                except Exception as e:
                    logger.debug(f"解析新闻项失败: {e}")
                    continue

            await page.close()
            logger.info(f"✅ 抓取到 {len(news_list)} 条东方财富新闻")

        except Exception as e:
            logger.error(f"❌ 抓取东方财富新闻失败: {e}")

        return news_list

    async def scrape_xueqiu_discussions(self, symbol: str, max_items: int = 20) -> List[Dict]:
        """
        抓取雪球讨论帖子

        Args:
            symbol: 股票代码（如 '600519'）
            max_items: 最大帖子数量

        Returns:
            List[Dict]: 讨论列表
        """
        if not self.browser:
            logger.warning("浏览器未初始化")
            return []

        discussions = []

        try:
            # 转换股票代码格式
            if symbol.startswith('6'):
                xq_symbol = f"SH{symbol}"
            elif symbol.startswith('0') or symbol.startswith('3'):
                xq_symbol = f"SZ{symbol}"
            else:
                xq_symbol = symbol

            url = f"https://xueqiu.com/S/{xq_symbol}"
            logger.info(f"💬 抓取雪球讨论: {url}")

            page = await self.browser.new_page()

            # 设置 User-Agent 避免被识别为爬虫
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })

            await page.goto(url, timeout=self.timeout)

            # 等待讨论区加载
            try:
                await page.wait_for_selector(".timeline, .feed-list", timeout=10000)
            except PlaywrightTimeoutError:
                logger.warning(f"⚠️ 雪球讨论区加载超时: {symbol}")
                await page.close()
                return []

            # 滚动页面加载更多内容
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(0.5)

            # 提取讨论数据
            feed_items = await page.query_selector_all(".timeline__item, .feed-item")

            for i, item in enumerate(feed_items[:max_items]):
                try:
                    # 提取帖子内容
                    content_elem = await item.query_selector(".timeline__item__content, .feed-content")
                    if not content_elem:
                        continue

                    content = await content_elem.inner_text()

                    # 提取时间
                    time_elem = await item.query_selector(".timeline__item__time, .feed-time")
                    time_text = await time_elem.inner_text() if time_elem else "未知时间"

                    # 提取作者
                    author_elem = await item.query_selector(".timeline__item__name, .user-name")
                    author = await author_elem.inner_text() if author_elem else "匿名"

                    # 简单情感判断（基于关键词）
                    sentiment = self._simple_sentiment_analysis(content)

                    discussions.append({
                        "content": content.strip()[:500],  # 限制长度
                        "author": author.strip(),
                        "time": time_text.strip(),
                        "sentiment": sentiment,
                        "source": "雪球",
                        "symbol": symbol,
                        "crawl_time": datetime.now().isoformat()
                    })

                    logger.debug(f"  - {content[:30]}... [{sentiment}]")

                except Exception as e:
                    logger.debug(f"解析雪球帖子失败: {e}")
                    continue

            await page.close()
            logger.info(f"✅ 抓取到 {len(discussions)} 条雪球讨论")

        except Exception as e:
            logger.error(f"❌ 抓取雪球讨论失败: {e}")

        return discussions

    def _simple_sentiment_analysis(self, text: str) -> str:
        """
        简单的情感分析（基于关键词）

        Args:
            text: 文本内容

        Returns:
            str: 'positive', 'negative', 'neutral'
        """
        positive_keywords = ['看好', '买入', '上涨', '利好', '突破', '强势', '涨停', '牛市']
        negative_keywords = ['看跌', '卖出', '下跌', '利空', '风险', '弱势', '跌停', '熊市']

        positive_count = sum(1 for keyword in positive_keywords if keyword in text)
        negative_count = sum(1 for keyword in negative_keywords if keyword in text)

        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'

    async def scrape_stock_announcement(self, symbol: str) -> List[Dict]:
        """
        抓取巨潮资讯网公司公告（简化版）

        Args:
            symbol: 股票代码

        Returns:
            List[Dict]: 公告列表
        """
        # TODO: 实现公司公告抓取
        logger.info(f"📋 公司公告抓取功能待实现: {symbol}")
        return []


# 便捷函数
async def scrape_news_for_sentiment(symbol: str) -> Dict:
    """
    为情感分析抓取综合数据

    Args:
        symbol: 股票代码

    Returns:
        Dict: 包含新闻和讨论的综合数据
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("Playwright 不可用，跳过网页数据抓取")
        return {"news": [], "discussions": []}

    try:
        async with WebScraper(headless=True) as scraper:
            # 并行抓取新闻和讨论
            news_task = scraper.scrape_eastmoney_news(symbol, max_news=10)
            discussions_task = scraper.scrape_xueqiu_discussions(symbol, max_items=15)

            news, discussions = await asyncio.gather(
                news_task,
                discussions_task,
                return_exceptions=True
            )

            # 处理异常
            if isinstance(news, Exception):
                logger.error(f"新闻抓取失败: {news}")
                news = []
            if isinstance(discussions, Exception):
                logger.error(f"讨论抓取失败: {discussions}")
                discussions = []

            return {
                "news": news,
                "discussions": discussions,
                "total_items": len(news) + len(discussions),
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.error(f"综合数据抓取失败: {e}")
        return {"news": [], "discussions": []}