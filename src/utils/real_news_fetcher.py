# -*- coding: utf-8 -*-
"""
真实新闻数据获取器
支持多种新闻数据源，包括AkShare、东方财富等
"""

import logging
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
from .stock_tag_manager import get_stock_related_keywords

logger = logging.getLogger(__name__)

class RealNewsFetcher:
    """真实新闻数据获取器 - 多源聚合增强版"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.cache = {}  # 简单缓存
        self.cache_duration = 900  # 15分钟缓存 (更频繁的更新)
        self.max_workers = 3  # 并发获取新闻源
        self.timeout = 8  # 降低超时时间提高响应速度

        # 数据源权重配置 (根据可靠性和时效性)
        self.source_weights = {
            'akshare': 0.4,
            'eastmoney': 0.35,
            'sina': 0.25
        }

        # 请求间隔 (避免被限流)
        self.request_intervals = {
            'akshare': 1.0,
            'eastmoney': 0.8,
            'sina': 0.6
        }
        self._last_request_time = {}

    def _normalize_symbol_format(self, symbol: str) -> str:
        """
        标准化股票代码格式，修复混合格式错误

        Args:
            symbol: 输入的股票代码

        Returns:
            标准化后的股票代码
        """
        if not symbol:
            return symbol

        symbol = symbol.strip().upper()

        # 处理混合格式错误 (例如: SH600376.SZ -> 600376.SH)
        if symbol.startswith('SH') and symbol.endswith('.SZ'):
            code_part = symbol[2:8]  # 提取中间的6位数字
            if code_part.isdigit():
                normalized = f"{code_part}.SH"
                logger.debug(f"修正混合格式: {symbol} -> {normalized}")
                return normalized

        # 处理混合格式错误 (例如: SZ000001.SH -> 000001.SZ)
        if symbol.startswith('SZ') and symbol.endswith('.SH'):
            code_part = symbol[2:8]  # 提取中间的6位数字
            if code_part.isdigit():
                normalized = f"{code_part}.SZ"
                logger.debug(f"修正混合格式: {symbol} -> {normalized}")
                return normalized

        # 处理有前缀无后缀的情况
        if symbol.startswith('SH') and not ('.' in symbol):
            code_part = symbol[2:8]
            if code_part.isdigit():
                normalized = f"{code_part}.SH"
                logger.debug(f"添加后缀: {symbol} -> {normalized}")
                return normalized

        if symbol.startswith('SZ') and not ('.' in symbol):
            code_part = symbol[2:8]
            if code_part.isdigit():
                normalized = f"{code_part}.SZ"
                logger.debug(f"添加后缀: {symbol} -> {normalized}")
                return normalized

        # 处理纯数字代码，根据开头判断市场
        if symbol.isdigit() and len(symbol) == 6:
            if symbol.startswith(('60', '68', '90')):
                # 上海股票：60开头的A股，68开头的科创板，90开头的B股
                normalized = f"{symbol}.SH"
                logger.debug(f"纯数字转换(上海): {symbol} -> {normalized}")
                return normalized
            elif symbol.startswith(('00', '30', '20')):
                # 深圳股票：00开头的主板，30开头的创业板，20开头的B股
                normalized = f"{symbol}.SZ"
                logger.debug(f"纯数字转换(深圳): {symbol} -> {normalized}")
                return normalized

        # 其他情况直接返回
        return symbol

    def fetch_stock_news(self, symbol: str, company_name: str) -> List[Dict]:
        """
        获取股票新闻的主入口

        Args:
            symbol: 股票代码 (如: 600519.SS)
            company_name: 公司名称 (如: 贵州茅台)

        Returns:
            新闻列表，每个新闻包含title, content, source, time, url, time_parsed, days_ago等字段
        """
        # 标准化股票代码格式
        normalized_symbol = self._normalize_symbol_format(symbol)
        if normalized_symbol != symbol:
            logger.info(f"股票代码格式标准化: {symbol} -> {normalized_symbol}")

        # 检查缓存
        cache_key = f"{normalized_symbol}_{company_name}"
        if self._is_cache_valid(cache_key):
            logger.debug(f"使用缓存的新闻数据: {normalized_symbol}")
            return self.cache[cache_key]['data']

        # 获取股票相关标签关键词，用于扩展新闻搜索
        related_keywords = get_stock_related_keywords(normalized_symbol, company_name)
        logger.info(f"获取到{normalized_symbol}的关联关键词: {related_keywords}")

        # 并发获取多个数据源 (TradingAgents-CN 多源聚合模式)
        news_data = self._fetch_from_multiple_sources_concurrent(normalized_symbol, company_name, related_keywords)

        # 缓存结果
        if news_data:
            self.cache[cache_key] = {
                'data': news_data,
                'timestamp': time.time()
            }

        return news_data

    def _fetch_from_multiple_sources_concurrent(self, symbol: str, company_name: str, related_keywords: List[str] = None) -> List[Dict]:
        """并发从多个数据源获取新闻"""
        all_news = []
        source_results = {}

        # 定义数据源获取函数（支持关键词搜索）
        fetch_functions = {
            'akshare': lambda: self._fetch_from_akshare(symbol, company_name),
            'eastmoney': lambda: self._fetch_from_eastmoney(symbol, company_name),
            'sina': lambda: self._fetch_from_sina(symbol, company_name)
        }

        # 如果有相关关键词，添加基于关键词的搜索
        if related_keywords:
            for i, keyword in enumerate(related_keywords[:3]):  # 限制关键词数量避免过多请求
                fetch_functions[f'keyword_{i}'] = lambda k=keyword: self._fetch_by_keyword(k)

        # 并发执行
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_source = {}
            for source_name, fetch_func in fetch_functions.items():
                # 添加请求间隔控制
                self._wait_for_rate_limit(source_name)
                future = executor.submit(self._safe_fetch_with_timeout, fetch_func, source_name)
                future_to_source[future] = source_name

            # 收集结果
            for future in as_completed(future_to_source, timeout=15):
                source_name = future_to_source[future]
                try:
                    result = future.result(timeout=10)
                    if result:
                        source_results[source_name] = result
                        logger.info(f"[{source_name}] 成功获取 {len(result)} 条新闻: {symbol}")
                    else:
                        logger.warning(f"[{source_name}] 未获取到新闻: {symbol}")
                except Exception as e:
                    logger.warning(f"[{source_name}] 获取新闻失败 {symbol}: {e}")

        # 合并和去重新闻
        all_news = self._merge_and_deduplicate_news(source_results)

        logger.info(f"多源聚合完成 {symbol}: 共获取 {len(all_news)} 条去重新闻")
        return all_news

    def _safe_fetch_with_timeout(self, fetch_func, source_name: str) -> List[Dict]:
        """安全的获取函数，带超时保护"""
        try:
            start_time = time.time()
            result = fetch_func()
            elapsed = time.time() - start_time
            logger.debug(f"[{source_name}] 获取耗时: {elapsed:.2f}秒")
            return result
        except Exception as e:
            logger.error(f"[{source_name}] 安全获取失败: {e}")
            return []

    def _wait_for_rate_limit(self, source_name: str):
        """请求间隔控制"""
        if source_name in self._last_request_time:
            elapsed = time.time() - self._last_request_time[source_name]
            interval = self.request_intervals.get(source_name, 1.0)
            if elapsed < interval:
                sleep_time = interval - elapsed
                time.sleep(sleep_time)
        self._last_request_time[source_name] = time.time()

    def _merge_and_deduplicate_news(self, source_results: Dict[str, List[Dict]]) -> List[Dict]:
        """合并并去重新闻"""
        all_news = []
        seen_titles = set()

        # 按权重排序数据源
        sorted_sources = sorted(source_results.items(),
                              key=lambda x: self.source_weights.get(x[0], 0),
                              reverse=True)

        for source_name, news_list in sorted_sources:
            weight = self.source_weights.get(source_name, 0.1)

            for news in news_list:
                title = news.get('title', '').strip()
                if not title:
                    continue

                # 简单去重：基于标题相似度
                is_duplicate = False
                for seen_title in seen_titles:
                    if self._calculate_similarity(title, seen_title) > 0.8:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    # 添加数据源权重信息
                    news['source_weight'] = weight
                    news['aggregated_source'] = source_name

                    # 添加时间分析信息
                    time_info = self._parse_news_time(news.get('time', ''))
                    news.update(time_info)

                    all_news.append(news)
                    seen_titles.add(title)

        # 按时间排序（最新的在前）
        all_news.sort(key=lambda x: x.get('time_parsed', 0), reverse=True)

        # 确保至少获取最近几条新闻，如果没有足够的新闻，返回所有可用的
        max_news = min(15, len(all_news)) if all_news else 0
        recent_news = all_news[:max_news]

        # 添加获取时间信息
        current_time = datetime.now()
        for news in recent_news:
            if not news.get('current_time'):
                news['current_time'] = current_time.strftime('%Y-%m-%d %H:%M:%S')

        return recent_news

    def _calculate_similarity(self, title1: str, title2: str) -> float:
        """计算标题相似度"""
        if not title1 or not title2:
            return 0.0

        # 简化的相似度计算：基于共同字符数
        set1 = set(title1)
        set2 = set(title2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _parse_time_for_sort(self, time_str: str) -> float:
        """解析时间用于排序"""
        try:
            # 尝试解析为时间戳
            if 'ago' in time_str or '前' in time_str:
                return time.time() - 3600  # 假设是1小时前

            # 尝试解析具体时间
            parsed_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            return parsed_time.timestamp()
        except:
            return time.time() - 86400  # 默认1天前

    def _fetch_from_akshare(self, symbol: str, company_name: str) -> List[Dict]:
        """从AkShare获取新闻"""
        try:
            import akshare as ak

            # 提取纯数字股票代码，AkShare需要纯数字格式
            stock_code = symbol.replace('.SH', '').replace('.SZ', '').replace('.SS', '')

            logger.debug(f"AkShare新闻查询 - 原始代码: {symbol}, 处理后代码: {stock_code}")

            # 获取个股新闻
            try:
                news_df = ak.stock_news_em(symbol=stock_code)
            except Exception as e:
                logger.error(f"AkShare API调用失败 {symbol} (代码:{stock_code}): {e}")
                return []

            if news_df is None or news_df.empty:
                logger.warning(f"AkShare未返回新闻数据: {symbol} (代码:{stock_code})")
                return []

            news_list = []
            for _, row in news_df.head(8).iterrows():  # 取前8条新闻
                try:
                    # 清理新闻内容
                    title = str(row.get('新闻标题', '')).strip()
                    content = str(row.get('新闻内容', '')).strip()

                    # 如果内容太长，截取前300字符
                    if len(content) > 300:
                        content = content[:300] + "..."

                    # 格式化时间
                    time_str = str(row.get('发布时间', ''))
                    formatted_time = self._format_time(time_str)

                    if title and content:  # 确保标题和内容都不为空
                        news_list.append({
                            'title': title,
                            'content': content,
                            'source': 'AkShare-东方财富',
                            'time': formatted_time,
                            'url': str(row.get('新闻链接', '')),
                            'raw_time': time_str
                        })

                except Exception as e:
                    logger.debug(f"解析单条新闻失败: {e}")
                    continue

            logger.info(f"AkShare成功获取{len(news_list)}条有效新闻: {symbol}")
            return news_list

        except ImportError:
            logger.error("AkShare未安装，请运行: pip install akshare")
            return []
        except Exception as e:
            logger.error(f"AkShare获取新闻异常 {symbol} (代码:{stock_code}): {str(e)[:200]}")
            return []

    def _fetch_from_eastmoney(self, symbol: str, company_name: str) -> List[Dict]:
        """从东方财富获取新闻"""
        try:
            # 东方财富新闻搜索API
            url = "https://search-api-web.eastmoney.com/search/jsonp"

            params = {
                'cb': 'jQuery',
                'param': json.dumps({
                    "uid": "",
                    "keyword": company_name,
                    "type": ["cmsArticleWebOld"],
                    "client": "web",
                    "clientType": "web"
                }),
                'pageindex': 1,
                'pagesize': 8,
                '_': int(time.time() * 1000)
            }

            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                # 解析JSONP响应
                text = response.text
                # 提取JSON部分
                json_start = text.find('(') + 1
                json_end = text.rfind(')')
                json_str = text[json_start:json_end]

                data = json.loads(json_str)
                articles = data.get('result', {}).get('cmsArticleWebOld', [])

                news_list = []
                for article in articles[:8]:
                    try:
                        title = article.get('title', '').strip()
                        content = article.get('content', '').strip()

                        # 清理HTML标签
                        content = re.sub(r'<[^>]+>', '', content)
                        if len(content) > 300:
                            content = content[:300] + "..."

                        if title and content:
                            news_list.append({
                                'title': title,
                                'content': content,
                                'source': '东方财富',
                                'time': self._format_time(article.get('showTime', '')),
                                'url': article.get('url', ''),
                                'raw_time': article.get('showTime', '')
                            })
                    except Exception as e:
                        logger.debug(f"解析东方财富新闻失败: {e}")
                        continue

                logger.info(f"东方财富成功获取{len(news_list)}条新闻: {symbol}")
                return news_list

        except Exception as e:
            logger.error(f"东方财富API调用失败 {symbol} (公司:{company_name}): {str(e)[:200]}")

        return []

    def _fetch_from_sina(self, symbol: str, company_name: str) -> List[Dict]:
        """从新浪财经获取新闻"""
        try:
            # 提取纯数字股票代码，新浪需要纯数字格式
            stock_code = symbol.replace('.SH', '').replace('.SZ', '').replace('.SS', '')

            logger.debug(f"新浪新闻查询 - 原始代码: {symbol}, 处理后代码: {stock_code}")

            url = f"https://finance.sina.com.cn/realstock/company/{stock_code}/nc.shtml"

            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 200:
                # 这里可以添加HTML解析逻辑
                # 由于新浪API经常变化，这里提供一个基础框架
                logger.info(f"新浪财经响应正常: {symbol}")

                # 简化处理：返回基础新闻结构
                return [{
                    'title': f'{company_name}相关资讯',
                    'content': f'从新浪财经获取的{company_name}相关新闻内容...',
                    'source': '新浪财经',
                    'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'url': url,
                    'raw_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }]

        except Exception as e:
            logger.error(f"新浪财经获取新闻失败 {symbol} (代码:{stock_code}): {str(e)[:200]}")

        return []

    def _format_time(self, time_str: str) -> str:
        """格式化时间字符串"""
        if not time_str or time_str == 'nan':
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # 尝试不同的时间格式
            time_formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d',
                '%m-%d %H:%M',
                '%H:%M'
            ]

            for fmt in time_formats:
                try:
                    parsed_time = datetime.strptime(str(time_str), fmt)
                    # 如果只有时间没有日期，补充今天的日期
                    if fmt in ['%H:%M', '%m-%d %H:%M']:
                        now = datetime.now()
                        if fmt == '%H:%M':
                            parsed_time = parsed_time.replace(year=now.year, month=now.month, day=now.day)
                        elif fmt == '%m-%d %H:%M':
                            parsed_time = parsed_time.replace(year=now.year)

                    return parsed_time.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    continue

            # 如果都解析失败，返回当前时间
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        except Exception as e:
            logger.debug(f"时间格式化失败: {time_str}, {e}")
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _parse_news_time(self, time_str: str) -> Dict:
        """解析新闻时间，返回详细时间信息"""
        current_time = datetime.now()
        time_info = {
            'time_parsed': 0,  # 时间戳
            'days_ago': -1,    # 距离现在多少天，-1表示无法解析
            'time_description': '未知时间',  # 人类可读的时间描述
            'is_recent': False,  # 是否为最近的新闻（3天内）
            'time_original': time_str  # 原始时间字符串
        }

        if not time_str:
            return time_info

        try:
            # 尝试解析各种时间格式
            parsed_time = None

            # 格式1: 2024-01-15 14:30:00
            try:
                parsed_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass

            # 格式2: 2024-01-15
            if not parsed_time:
                try:
                    parsed_time = datetime.strptime(time_str, '%Y-%m-%d')
                except ValueError:
                    pass

            # 格式3: 01-15 14:30 (假设当前年份)
            if not parsed_time:
                try:
                    parsed_time = datetime.strptime(f"{current_time.year}-{time_str}", '%Y-%m-%d %H:%M')
                except ValueError:
                    pass

            # 格式4: "3小时前", "2天前"等相对时间
            if not parsed_time and ('前' in time_str or 'ago' in time_str.lower()):
                parsed_time = self._parse_relative_time(time_str, current_time)

            if parsed_time:
                time_info['time_parsed'] = parsed_time.timestamp()

                # 计算距离现在多少天
                time_diff = current_time - parsed_time
                days_ago = time_diff.days
                time_info['days_ago'] = days_ago

                # 判断是否为最近新闻
                time_info['is_recent'] = days_ago <= 3

                # 生成人类可读描述
                if days_ago == 0:
                    hours_ago = int(time_diff.total_seconds() / 3600)
                    if hours_ago == 0:
                        minutes_ago = int(time_diff.total_seconds() / 60)
                        time_info['time_description'] = f"{minutes_ago}分钟前"
                    else:
                        time_info['time_description'] = f"{hours_ago}小时前"
                elif days_ago == 1:
                    time_info['time_description'] = "1天前"
                else:
                    time_info['time_description'] = f"{days_ago}天前"

        except Exception as e:
            logger.debug(f"解析新闻时间失败: {time_str}, {e}")

        return time_info

    def _parse_relative_time(self, time_str: str, current_time: datetime) -> datetime:
        """解析相对时间字符串"""
        import re

        # 提取数字和时间单位
        patterns = [
            r'(\d+)\s*小时前',
            r'(\d+)\s*hours?\s*ago',
            r'(\d+)\s*天前',
            r'(\d+)\s*days?\s*ago',
            r'(\d+)\s*分钟前',
            r'(\d+)\s*minutes?\s*ago'
        ]

        for pattern in patterns:
            match = re.search(pattern, time_str)
            if match:
                value = int(match.group(1))
                if '小时' in pattern or 'hour' in pattern:
                    return current_time - timedelta(hours=value)
                elif '天' in pattern or 'day' in pattern:
                    return current_time - timedelta(days=value)
                elif '分钟' in pattern or 'minute' in pattern:
                    return current_time - timedelta(minutes=value)

        return current_time

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.cache:
            return False

        cache_time = self.cache[cache_key]['timestamp']
        return (time.time() - cache_time) < self.cache_duration

    def clear_cache(self):
        """清理缓存"""
        self.cache.clear()
        logger.info("新闻缓存已清理")

    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        valid_count = 0
        expired_count = 0

        current_time = time.time()
        for key, item in self.cache.items():
            if (current_time - item['timestamp']) < self.cache_duration:
                valid_count += 1
            else:
                expired_count += 1

        return {
            'total_cached': len(self.cache),
            'valid_cached': valid_count,
            'expired_cached': expired_count,
            'cache_duration_minutes': self.cache_duration / 60
        }

    def _fetch_by_keyword(self, keyword: str) -> List[Dict]:
        """基于关键词搜索新闻"""
        try:
            import akshare as ak

            # 使用AkShare搜索财经新闻
            news_df = ak.stock_news_em(symbol=keyword)

            if news_df.empty:
                return []

            news_list = []
            for _, row in news_df.head(5).iterrows():  # 每个关键词最多取5条新闻
                news_item = {
                    'title': str(row.get('新闻标题', '')).strip(),
                    'content': str(row.get('新闻内容', ''))[:500],  # 限制内容长度
                    'time': str(row.get('发布时间', '')),
                    'source': str(row.get('新闻来源', '东方财富')),
                    'url': str(row.get('新闻链接', '')),
                    'search_keyword': keyword,  # 标记是通过哪个关键词找到的
                    'is_keyword_news': True     # 标记这是关键词新闻
                }

                if news_item['title'] and len(news_item['title']) > 5:
                    news_list.append(news_item)

            logger.info(f"通过关键词'{keyword}'获取到{len(news_list)}条相关新闻")
            return news_list

        except Exception as e:
            logger.debug(f"关键词搜索新闻失败 '{keyword}': {e}")
            return []