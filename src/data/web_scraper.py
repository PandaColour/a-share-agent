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
import sys

logger = logging.getLogger(__name__)

# 诊断日志：记录导入时的Python环境
logger.info(f"[INFO] web_scraper 模块加载 - Python: {sys.executable}")
logger.info(f"[INFO] sys.path[0:3]: {sys.path[:3]}")

try:
    from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
    logger.info("[SUCCESS] Playwright 导入成功")
except ImportError as e:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning(f"[WARNING] Playwright 未安装，网页抓取功能不可用")
    logger.warning(f"   导入错误详情: {e}")
    logger.warning(f"   当前Python: {sys.executable}")
except Exception as e:
    PLAYWRIGHT_AVAILABLE = False
    logger.error(f"[ERROR] Playwright 导入时发生未知错误: {e}")
    logger.error(f"   当前Python: {sys.executable}")


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
        self._xueqiu_logged_in = False
        self._xueqiu_cookies_file = "xueqiu_cookies.json"
        self._xueqiu_session = None

        if not PLAYWRIGHT_AVAILABLE:
            logger.error("[ERROR] Playwright 不可用，无法初始化 WebScraper")

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
            logger.info("[SUCCESS] Playwright 浏览器启动成功")
        except Exception as e:
            logger.error(f"[ERROR] 启动浏览器失败: {e}")

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
            symbol: 股票代码（如 '600519' 或 '600519.SH'）
            max_news: 最大新闻数量

        Returns:
            List[Dict]: 新闻列表
        """
        if not self.browser:
            logger.warning("浏览器未初始化")
            return []

        news_list = []

        try:
            # 移除市场后缀（.SH, .SZ）
            clean_symbol = symbol.split('.')[0]

            # 东方财富个股页面
            url = f"https://quote.eastmoney.com/{clean_symbol}.html"
            logger.info(f"[INFO] 抓取东方财富新闻: {url}")

            page = await self.browser.new_page()
            await page.goto(url, timeout=self.timeout)

            # 等待页面加载完成
            await asyncio.sleep(2)

            # 尝试多个可能的选择器（2024-2025年网站结构）
            news_selectors = [
                # 新版选择器（优先尝试）
                "#app",                                    # Vue应用容器
                "[class*='quote-']",                       # 行情相关类名
                "div[class*='news']",                      # 包含news的div
                "ul[class*='news']",                       # 包含news的列表

                # 通用选择器
                "article",                                 # HTML5文章标签
                "a[href*='finance.eastmoney']",           # 东方财富新闻链接

                # 旧版选择器（兼容）
                ".news-list",
                ".newslist",
                "#newslist"
            ]

            news_container_found = False
            for selector in news_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=3000)
                    logger.debug(f"  ✓ 找到容器: {selector}")
                    news_container_found = True
                    break
                except PlaywrightTimeoutError:
                    continue

            if not news_container_found:
                logger.warning(f"[WARNING] 无法找到新闻容器: {symbol}")
                logger.info(f"💡 网页可能已改版，建议运行诊断工具")

                # 尝试抓取任何链接作为降级方案
                all_links = await page.query_selector_all("a[href*='news'], a[href*='finance']")
                logger.info(f"  降级方案: 找到 {len(all_links)} 个可能的新闻链接")

                for i, link in enumerate(all_links[:max_news]):
                    try:
                        title = await link.inner_text()
                        href = await link.get_attribute("href")

                        if title and len(title.strip()) > 5:  # 过滤掉太短的标题
                            news_list.append({
                                "title": title.strip(),
                                "link": href if href and href.startswith("http") else f"https://finance.eastmoney.com{href}",
                                "time": "未知时间",
                                "source": "东方财富",
                                "symbol": clean_symbol,
                                "crawl_time": datetime.now().isoformat()
                            })
                    except:
                        continue

                await page.close()
                if news_list:
                    logger.info(f"[SUCCESS] 降级方案抓取到 {len(news_list)} 条新闻")
                return news_list

            # 提取新闻项（尝试多种结构）
            news_item_selectors = [
                "a[href*='finance.eastmoney']",
                "a[href*='news']",
                "li",
                ".news-item",
                "article"
            ]

            news_items = []
            for item_selector in news_item_selectors:
                news_items = await page.query_selector_all(item_selector)
                if len(news_items) > 0:
                    logger.debug(f"  ✓ 使用项目选择器: {item_selector} (找到 {len(news_items)} 项)")
                    break

            for i, item in enumerate(news_items[:max_news * 2]):  # 多抓取一些，过滤后返回
                try:
                    # 提取标题
                    title_text = await item.inner_text()
                    if not title_text or len(title_text.strip()) < 5:
                        continue

                    link = await item.get_attribute("href")

                    # 过滤非新闻链接
                    if not link or ('javascript' in link.lower() or '#' in link):
                        continue

                    # 补全链接
                    if link and not link.startswith("http"):
                        if link.startswith("//"):
                            link = f"https:{link}"
                        elif link.startswith("/"):
                            link = f"https://finance.eastmoney.com{link}"

                    # 尝试提取时间
                    time_text = "未知时间"
                    try:
                        parent = await item.query_selector("..")
                        if parent:
                            time_elem = await parent.query_selector("[class*='time'], [class*='date'], span")
                            if time_elem:
                                time_text = await time_elem.inner_text()
                    except:
                        pass

                    news_list.append({
                        "title": title_text.strip()[:200],  # 限制标题长度
                        "link": link,
                        "time": time_text.strip(),
                        "source": "东方财富",
                        "symbol": clean_symbol,
                        "crawl_time": datetime.now().isoformat()
                    })

                    if len(news_list) >= max_news:
                        break

                except Exception as e:
                    logger.debug(f"解析新闻项失败: {e}")
                    continue

            await page.close()
            logger.info(f"[SUCCESS] 抓取到 {len(news_list)} 条东方财富新闻")

        except Exception as e:
            logger.error(f"[ERROR] 抓取东方财富新闻失败: {e}")

        return news_list

    async def scrape_xueqiu_discussions(self, symbol: str, max_items: int = 20) -> List[Dict]:
        """
        抓取雪球讨论帖子

        Args:
            symbol: 股票代码（如 '600519' 或 '600519.SH'）
            max_items: 最大帖子数量

        Returns:
            List[Dict]: 讨论列表
        """
        if not self.browser:
            logger.warning("浏览器未初始化")
            return []

        discussions = []

        try:
            # 移除市场后缀（.SH, .SZ）
            clean_symbol = symbol.split('.')[0]

            # 转换股票代码格式
            if clean_symbol.startswith('6'):
                xq_symbol = f"SH{clean_symbol}"
            elif clean_symbol.startswith('0') or clean_symbol.startswith('3'):
                xq_symbol = f"SZ{clean_symbol}"
            else:
                xq_symbol = clean_symbol

            url = f"https://xueqiu.com/S/{xq_symbol}"
            logger.info(f"💬 抓取雪球讨论: {url}")

            page = await self.browser.new_page()

            # 设置更真实的浏览器 headers 避免被雪球反爬虫拦截
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1'
            })

            # 检查是否需要雪球登录
            login_success = await self._ensure_xueqiu_login(page)
            if not login_success:
                logger.warning("雪球登录失败，跳过讨论抓取")
                return []

            await page.goto(url, timeout=self.timeout)

            # 等待页面加载完成
            await asyncio.sleep(2)

            # 尝试多个可能的选择器（2024-2025年网站结构）
            discussion_selectors = [
                # 新版选择器（优先尝试）
                "#app",                                    # Vue应用容器
                "article",                                 # HTML5文章标签
                "[class*='card']",                        # 卡片布局
                "[class*='post']",                        # 帖子容器
                "div[class*='timeline']",                 # 时间线容器
                "div[class*='feed']",                     # 信息流容器

                # 通用选择器
                "a[href*='/status/']",                    # 雪球帖子链接格式
                "div[class*='content']",                  # 内容容器

                # 旧版选择器（兼容）
                ".timeline",
                ".feed-list",
                ".timeline__item",
                ".feed-item"
            ]

            discussion_container_found = False
            for selector in discussion_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=3000)
                    logger.debug(f"  ✓ 找到容器: {selector}")
                    discussion_container_found = True
                    break
                except PlaywrightTimeoutError:
                    continue

            if not discussion_container_found:
                logger.warning(f"[WARNING] 无法找到讨论容器: {symbol}")
                logger.info(f"💡 网页可能已改版，建议运行诊断工具")

                # 尝试抓取任何帖子链接作为降级方案
                all_items = await page.query_selector_all("div[class*='item'], article, [class*='card']")
                logger.info(f"  降级方案: 找到 {len(all_items)} 个可能的讨论项")

                for i, item in enumerate(all_items[:max_items]):
                    try:
                        content_text = await item.inner_text()

                        if content_text and len(content_text.strip()) > 10:  # 过滤掉太短的内容
                            sentiment = self._simple_sentiment_analysis(content_text)

                            discussions.append({
                                "content": content_text.strip()[:500],
                                "author": "匿名",
                                "time": "未知时间",
                                "sentiment": sentiment,
                                "source": "雪球",
                                "symbol": clean_symbol,
                                "crawl_time": datetime.now().isoformat()
                            })
                    except:
                        continue

                await page.close()
                if discussions:
                    logger.info(f"[SUCCESS] 降级方案抓取到 {len(discussions)} 条讨论")
                return discussions

            # 滚动页面加载更多内容
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(0.5)

            # 提取讨论项（尝试多种结构）
            discussion_item_selectors = [
                ".timeline__item",
                ".feed-item",
                "article",
                "[class*='card']",
                "[class*='post']",
                "div[class*='item']"
            ]

            feed_items = []
            for item_selector in discussion_item_selectors:
                feed_items = await page.query_selector_all(item_selector)
                if len(feed_items) > 0:
                    logger.debug(f"  ✓ 使用项目选择器: {item_selector} (找到 {len(feed_items)} 项)")
                    break

            for i, item in enumerate(feed_items[:max_items * 2]):  # 多抓取一些，过滤后返回
                try:
                    # 提取帖子内容
                    content_elem = await item.query_selector(".timeline__item__content, .feed-content, [class*='content']")
                    if not content_elem:
                        # 尝试直接获取文本
                        content = await item.inner_text()
                    else:
                        content = await content_elem.inner_text()

                    if not content or len(content.strip()) < 10:
                        continue

                    # 提取时间
                    time_text = "未知时间"
                    try:
                        time_elem = await item.query_selector(".timeline__item__time, .feed-time, [class*='time'], time")
                        if time_elem:
                            time_text = await time_elem.inner_text()
                    except:
                        pass

                    # 提取作者
                    author = "匿名"
                    try:
                        author_elem = await item.query_selector(".timeline__item__name, .user-name, [class*='author'], [class*='user']")
                        if author_elem:
                            author = await author_elem.inner_text()
                    except:
                        pass

                    # 简单情感判断（基于关键词）
                    sentiment = self._simple_sentiment_analysis(content)

                    discussions.append({
                        "content": content.strip()[:500],  # 限制长度
                        "author": author.strip(),
                        "time": time_text.strip(),
                        "sentiment": sentiment,
                        "source": "雪球",
                        "symbol": clean_symbol,
                        "crawl_time": datetime.now().isoformat()
                    })

                    if len(discussions) >= max_items:
                        break

                except Exception as e:
                    logger.debug(f"解析雪球帖子失败: {e}")
                    continue

            await page.close()
            logger.info(f"[SUCCESS] 抓取到 {len(discussions)} 条雪球讨论")

        except Exception as e:
            logger.error(f"[ERROR] 抓取雪球讨论失败: {e}")

        return discussions

    async def _ensure_xueqiu_login(self, page) -> bool:
        """
        确保雪球登录状态

        Args:
            page: Playwright页面对象

        Returns:
            bool: 是否登录成功
        """
        # 检查配置是否启用登录
        from config.config_manager import get_config
        config = get_config()
        web_config = config.get('analysis_settings.web_scraping', {})
        xueqiu_config = web_config.get('xueqiu_login', {})

        if not xueqiu_config.get('enabled', False):
            logger.debug("雪球登录未启用")
            return False

        phone = xueqiu_config.get('phone', '').strip()
        password = xueqiu_config.get('password', '').strip()

        if not phone or not password:
            logger.warning("雪球登录配置不完整")
            return False

        # 检查是否已经登录
        if await self._check_xueqiu_login_status(page):
            logger.info("雪球已登录，复用会话")
            return True

        # 尝试加载保存的cookies
        if await self._load_xueqiu_cookies(page):
            logger.info("雪球登录成功（使用保存的会话）")
            self._xueqiu_logged_in = True
            return True

        # 需要重新登录
        logger.info("雪球需要重新登录")
        return await self._login_xueqiu(page, phone, password)

    async def _check_xueqiu_login_status(self, page) -> bool:
        """检查雪球登录状态"""
        try:
            # 访问雪球首页检查登录状态
            await page.goto("https://xueqiu.com", timeout=15000)
            await asyncio.sleep(3)

            # 更新的未登录指示器（2025年）
            login_indicators = [
                # 未登录的元素
                "//a[contains(@href, 'passport')]",
                "//a[contains(@href, '/login')]",
                "//button[contains(text(), '登录')]",
                "//span[contains(text(), '登录')]",
                "[class*='login'] a",
                "[class*='auth'] a",
                "#app a[href*='login']",
                "[class*='header'] a:has-text('登录')",
                "[id*='login']",
                "//div[contains(@class, 'header')]//a[contains(text(), '登录')]"
            ]

            # 更新的已登录指示器（2025年）
            logged_in_indicators = [
                # 已登录的元素
                "//a[contains(@href, '/user')]",
                "//a[contains(@href, 'user')]",
                "//div[contains(@class, 'user')]",
                "//span[contains(text(), '退出')]",
                "//button[contains(text(), '退出')]",
                "//a[contains(text(), '退出')]",
                "[class*='avatar']",
                "[class*='user-info']",
                "[class*='user']",
                ".user__avatar",
                ".user__name",
                ".header__user",
                "//div[contains(@class, 'header')]//a[contains(@href, 'user')]",
                "[class*='profile']",
                "[class*='account']"
            ]

            # 首先检查明显的登录按钮（如果存在，说明未登录）
            for i, indicator in enumerate(login_indicators):
                try:
                    element = await page.wait_for_selector(indicator, timeout=1500)
                    if element and await element.is_visible():
                        logger.debug(f"发现未登录指示器 {i+1}: {indicator}")
                        # 检查是否真的是登录按钮，而不是其他装饰性元素
                        text = await element.inner_text()
                        if '登录' in text or '注册' in text:
                            logger.info(f"发现登录按钮: {text}")
                            return False  # 未登录
                except:
                    continue

            # 检查已登录的指示器
            for i, indicator in enumerate(logged_in_indicators):
                try:
                    element = await page.wait_for_selector(indicator, timeout=1500)
                    if element and await element.is_visible():
                        logger.debug(f"发现已登录指示器 {i+1}: {indicator}")
                        # 验证是用户相关元素
                        text = await element.inner_text()
                        if any(keyword in text for keyword in ['退出', '用户', '个人', '头像']):
                            logger.info(f"发现用户界面元素: {text}")
                            return True  # 已登录
                except:
                    continue

            # 通过检查页面内容和URL判断
            current_url = page.url
            if 'passport' in current_url or 'login' in current_url:
                logger.info("当前在登录页面，说明未登录")
                return False

            # 通过页面内容关键词判断
            content = await page.content()
            login_keywords = ['立即登录', '免费注册', '使用手机号登录', '账号密码登录', '短信登录']
            logged_in_keywords = ['个人中心', '我的关注', '我的股票', '退出登录', '我的自选', '用户设置']

            login_found = any(keyword in content for keyword in login_keywords)
            logged_in_found = any(keyword in content for keyword in logged_in_keywords)

            if logged_in_found and not login_found:
                logger.info("页面内容显示已登录")
                return True
            elif login_found and not logged_in_found:
                logger.info("页面内容显示未登录")
                return False

            # 检查cookies作为最后手段
            cookies = await page.context.cookies()
            xueqiu_cookies = [c for c in cookies if 'xueqiu.com' in c.get('domain', '')]

            # 检查关键cookie
            key_cookies = ['u', 's', 'token', 'userid', 'xq_a_token']
            for cookie in xueqiu_cookies:
                if any(key in cookie.get('name', '').lower() for key in key_cookies):
                    if cookie.get('value'):  # 有值的cookie
                        logger.info(f"发现登录cookie: {cookie['name']}")
                        return True

            logger.info("无法确定登录状态，默认为未登录")
            return False  # 默认认为未登录

        except Exception as e:
            logger.debug(f"检查登录状态失败: {e}")
            return False

    async def _load_xueqiu_cookies(self, page) -> bool:
        """加载保存的雪球cookies"""
        try:
            import os
            if not os.path.exists(self._xueqiu_cookies_file):
                return False

            import json
            with open(self._xueqiu_cookies_file, 'r', encoding='utf-8') as f:
                cookies_data = json.load(f)

            # 检查cookies是否过期（24小时）
            import time
            if time.time() - cookies_data.get('timestamp', 0) > 86400:  # 24小时
                logger.info("雪球cookies已过期")
                return False

            # 先访问雪球域名
            await page.goto("https://xueqiu.com", timeout=10000)

            # 加载cookies
            cookies = cookies_data.get('cookies', [])
            for cookie in cookies:
                try:
                    await page.context.add_cookies([{
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'domain': cookie.get('domain', '.xueqiu.com'),
                        'path': cookie.get('path', '/'),
                        'httpOnly': cookie.get('httpOnly', False),
                        'secure': cookie.get('secure', True),
                        'sameSite': cookie.get('sameSite', 'Lax')
                    }])
                except Exception as e:
                    logger.debug(f"加载cookie失败: {e}")
                    continue

            # 验证登录状态
            await asyncio.sleep(2)
            return await self._check_xueqiu_login_status(page)

        except Exception as e:
            logger.debug(f"加载雪球cookies失败: {e}")
            return False

    async def _save_xueqiu_cookies(self, page) -> bool:
        """保存雪球cookies"""
        try:
            # 获取cookies
            cookies = await page.context.cookies()

            # 过滤雪球相关的cookies
            xueqiu_cookies = [
                cookie for cookie in cookies
                if 'xueqiu.com' in cookie.get('domain', '')
            ]

            cookies_data = {
                'cookies': xueqiu_cookies,
                'timestamp': int(time.time()),
                'user_agent': await page.evaluate("navigator.userAgent")
            }

            import json
            with open(self._xueqiu_cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies_data, f, indent=2, ensure_ascii=False)

            logger.info(f"雪球cookies已保存到 {self._xueqiu_cookies_file}")
            return True

        except Exception as e:
            logger.error(f"保存雪球cookies失败: {e}")
            return False

    async def _login_xueqiu(self, page, phone: str, password: str) -> bool:
        """执行雪球登录"""
        try:
            logger.info("开始雪球登录流程")

            # 设置更真实的浏览器环境
            await page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            })

            # 访问登录页面
            await page.goto("https://xueqiu.com", timeout=20000)
            await asyncio.sleep(3)

            # 检查是否已经登录
            if await self._check_xueqiu_login_status(page):
                logger.info("已经登录，无需重复登录")
                return True

            # 查找登录按钮并点击（更新选择器以适应最新页面结构）
            login_selectors = [
                # 2025年雪球最新选择器
                "//a[contains(@href, 'passport')]",
                "//a[contains(@href, 'login')]",
                "//button[contains(text(), '登录')]",
                "//span[contains(text(), '登录')]",
                "[class*='login'] a",
                "[class*='auth'] a",
                "[class*='user'] a:has-text('登录')",
                "#app a[href*='login']",
                ".navigation__login",
                ".header-login",
                "//div[contains(@class, 'header')]//a[contains(text(), '登录')]",
                # 兼容旧版本
                "#login-button",
                "[class*='login']"
            ]

            login_button = None
            logger.info("查找登录按钮...")
            for i, selector in enumerate(login_selectors):
                try:
                    logger.debug(f"尝试选择器 {i+1}: {selector}")
                    login_button = await page.wait_for_selector(selector, timeout=2000)
                    if login_button:
                        # 检查元素是否可见和可点击
                        is_visible = await login_button.is_visible()
                        if is_visible:
                            logger.info(f"找到登录按钮: {selector}")
                            break
                        else:
                            login_button = None
                except Exception as e:
                    logger.debug(f"选择器 {i+1} 失败: {e}")
                    continue

            if login_button:
                try:
                    # 尝试不同的点击方式
                    await login_button.click()
                    logger.info("点击登录按钮成功")
                except Exception as e:
                    logger.warning(f"普通点击失败，尝试JavaScript点击: {e}")
                    await page.evaluate("(element) => element.click()", login_button)

                await asyncio.sleep(4)  # 等待登录页面加载

            # 填写手机号（更新选择器以适应最新页面结构）
            phone_selectors = [
                # 2025年雪球最新选择器
                "input[placeholder*='手机号']",
                "input[placeholder*='手机']",
                "input[name='username']",
                "input[name='phone']",
                "input[placeholder*='用户名']",
                "input[placeholder*='账号']",
                "#phone",
                "#username",
                "#phone-input",
                "#username-input",
                "[class*='phone'] input",
                "[class*='username'] input",
                "[class*='mobile'] input",
                "[class*='form'] input[type='text']",
                "[class*='input'] input[placeholder*='手机']",
                "[class*='input'] input[placeholder*='用户']",
                # 兼容旧版本
                "input[placeholder*='账号']",
                "[class*='phone'] input"
            ]

            phone_input = None
            logger.info("查找手机号输入框...")
            for i, selector in enumerate(phone_selectors):
                try:
                    logger.debug(f"尝试手机号输入框选择器 {i+1}: {selector}")
                    phone_input = await page.wait_for_selector(selector, timeout=2000)
                    if phone_input:
                        # 检查元素是否可见和可编辑
                        is_visible = await phone_input.is_visible()
                        if is_visible:
                            logger.info(f"找到手机号输入框: {selector}")
                            break
                        else:
                            phone_input = None
                except Exception as e:
                    logger.debug(f"手机号选择器 {i+1} 失败: {e}")
                    continue

            if phone_input:
                # 清空并填写手机号
                await phone_input.fill('')  # 清空输入框
                await phone_input.type(phone, delay=100)  # 模拟人工输入
                await asyncio.sleep(1)
                logger.info("手机号填写完成")
            else:
                logger.warning("未找到手机号输入框，可能登录界面结构已变化")

            # 填写密码（更新选择器以适应最新页面结构）
            password_selectors = [
                # 2025年雪球最新选择器
                "input[placeholder*='密码']",
                "input[type='password']",
                "input[name='password']",
                "#password",
                "#password-input",
                "[class*='password'] input",
                "[class*='form'] input[type='password']",
                "[class*='input'] input[type='password']",
                "[class*='pwd'] input"
            ]

            password_input = None
            logger.info("查找密码输入框...")
            for i, selector in enumerate(password_selectors):
                try:
                    logger.debug(f"尝试密码输入框选择器 {i+1}: {selector}")
                    password_input = await page.wait_for_selector(selector, timeout=2000)
                    if password_input:
                        # 检查元素是否可见和可编辑
                        is_visible = await password_input.is_visible()
                        if is_visible:
                            logger.info(f"找到密码输入框: {selector}")
                            break
                        else:
                            password_input = None
                except Exception as e:
                    logger.debug(f"密码选择器 {i+1} 失败: {e}")
                    continue

            if password_input:
                # 清空并填写密码
                await password_input.fill('')  # 清空输入框
                await password_input.type(password, delay=100)  # 模拟人工输入
                await asyncio.sleep(1)
                logger.info("密码填写完成")
            else:
                logger.warning("未找到密码输入框，可能登录界面结构已变化")

            # 点击登录按钮（更新选择器以适应最新页面结构）
            submit_selectors = [
                # 2025年雪球最新选择器
                "//button[contains(text(), '登录')]",
                "//button[contains(text(), '立即登录')]",
                "//span[contains(text(), '登录')]/parent::button",
                "//div[contains(@class, 'login')]//button",
                "//div[contains(@class, 'form')]//button",
                "button[type='submit']",
                "#login-submit",
                "#submit",
                ".login__submit",
                ".form__submit",
                "[class*='login'] button",
                "[class*='submit'] button",
                "//button[@type='submit']",
                "[class*='btn'] button:has-text('登录')"
            ]

            submit_button = None
            logger.info("查找提交按钮...")
            for i, selector in enumerate(submit_selectors):
                try:
                    logger.debug(f"尝试提交按钮选择器 {i+1}: {selector}")
                    submit_button = await page.wait_for_selector(selector, timeout=2000)
                    if submit_button:
                        # 检查元素是否可见和可点击
                        is_visible = await submit_button.is_visible()
                        if is_visible:
                            logger.info(f"找到提交按钮: {selector}")
                            break
                        else:
                            submit_button = None
                except Exception as e:
                    logger.debug(f"提交按钮选择器 {i+1} 失败: {e}")
                    continue

            if submit_button:
                try:
                    # 尝试不同的点击方式
                    await submit_button.click()
                    logger.info("点击提交按钮成功")
                except Exception as e:
                    logger.warning(f"普通点击失败，尝试JavaScript点击: {e}")
                    await page.evaluate("(element) => element.click()", submit_button)

                await asyncio.sleep(8)  # 等待登录处理和页面跳转

            # 检查是否登录成功
            if await self._check_xueqiu_login_status(page):
                logger.info("雪球登录成功")
                # 保存cookies
                await self._save_xueqiu_cookies(page)
                self._xueqiu_logged_in = True
                return True
            else:
                logger.warning("雪球登录失败")
                return False

        except Exception as e:
            logger.error(f"雪球登录过程出错: {e}")
            return False

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
            # 检查配置中是否启用雪球讨论
            from config.config_manager import get_config
            config = get_config()
            web_config = config.get('analysis_settings.web_scraping', {})
            xueqiu_enabled = web_config.get('xueqiu_discussions', True)

            # 并行抓取新闻和讨论（如果启用）
            tasks = [scraper.scrape_eastmoney_news(symbol, max_news=10)]

            if xueqiu_enabled:
                logger.info("雪球讨论已启用，开始抓取...")
                tasks.append(scraper.scrape_xueqiu_discussions(symbol, max_items=15))
            else:
                logger.info("雪球讨论已禁用（需要登录态），跳过抓取")
                # 添加一个虚拟任务，保持异步处理的一致性
                async def empty_discussions():
                    return []
                tasks.append(empty_discussions())

            results = await asyncio.gather(*tasks, return_exceptions=True)

            news = results[0] if len(results) > 0 else []
            discussions = results[1] if len(results) > 1 else []

            # 处理异常
            if isinstance(news, Exception):
                logger.error(f"新闻抓取失败: {news}")
                news = []
            if isinstance(discussions, Exception):
                logger.error(f"讨论抓取失败: {discussions}")
                discussions = []

            # 如果是禁用状态，添加说明
            if not xueqiu_enabled:
                logger.info("雪球讨论功能已禁用，原因：雪球讨论区需要登录态才能访问")

            return {
                "news": news,
                "discussions": discussions,
                "total_items": len(news) + len(discussions),
                "timestamp": datetime.now().isoformat(),
                "xueqiu_enabled": xueqiu_enabled
            }

    except Exception as e:
        logger.error(f"综合数据抓取失败: {e}")
        return {"news": [], "discussions": []}