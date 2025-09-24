# -*- coding: utf-8 -*-
"""
股票标签管理器
为股票提供板块、行业、概念等标签信息，用于扩展新闻搜索范围
"""

import logging
import pandas as pd
from typing import Dict, List, Optional, Set
import requests
import time
from datetime import datetime, timedelta
import json
import os

logger = logging.getLogger(__name__)

class StockTagManager:
    """股票标签管理器"""

    def __init__(self):
        self.tag_cache = {}  # 股票标签缓存
        self.cache_duration = 24 * 3600  # 24小时缓存
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # 预定义的A股行业分类映射
        self.industry_mapping = {
            # 科技类
            '软件开发': ['科技', '软件', 'IT', '人工智能'],
            '电子设备': ['科技', '电子', '硬件', '芯片'],
            '计算机应用': ['科技', '计算机', '互联网'],
            '通信设备': ['科技', '通信', '5G', '网络'],

            # 金融类
            '银行': ['金融', '银行业', '资金'],
            '保险': ['金融', '保险业', '投资'],
            '证券': ['金融', '券商', '投资'],

            # 医药类
            '化学制药': ['医药', '制药', '生物医药', '健康'],
            '医疗器械': ['医药', '医疗', '器械', '健康'],
            '中药': ['医药', '中医药', '健康'],

            # 消费类
            '食品饮料': ['消费', '食品', '饮料', '快消品'],
            '纺织服装': ['消费', '纺织', '服装', '时尚'],
            '家用电器': ['消费', '家电', '电器'],

            # 工业类
            '机械设备': ['工业', '机械', '制造业', '设备'],
            '电力设备': ['工业', '电力', '能源设备'],
            '汽车': ['汽车', '交通运输', '新能源汽车'],

            # 能源类
            '石油石化': ['能源', '石油', '化工'],
            '煤炭': ['能源', '煤炭', '传统能源'],
            '电力': ['能源', '电力', '公用事业'],

            # 地产类
            '房地产': ['地产', '房地产', '建筑'],
            '建筑装饰': ['地产', '建筑', '装饰', '基建'],

            # 材料类
            '钢铁': ['材料', '钢铁', '金属'],
            '有色金属': ['材料', '有色金属', '金属'],
            '化工': ['材料', '化工', '化学'],

            # 其他
            '农林牧渔': ['农业', '农林牧渔', '食品安全'],
            '交通运输': ['交通', '物流', '运输'],
            '商业贸易': ['商贸', '零售', '批发']
        }

        # 概念板块映射
        self.concept_mapping = {
            '人工智能': ['AI', '机器学习', '算法', '智能'],
            '新能源': ['电动车', '锂电池', '光伏', '风电'],
            '芯片': ['半导体', '集成电路', 'IC', '芯片设计'],
            '5G': ['通信', '网络', '基站', '物联网'],
            '医疗': ['生物医药', '医疗器械', '疫苗', 'CXO'],
            '消费': ['白酒', '食品', '零售', '品牌'],
            '新基建': ['数据中心', '云计算', '工业互联网'],
            '碳中和': ['环保', '节能减排', '清洁能源'],
            '军工': ['国防', '航空航天', '军用装备'],
            '金融科技': ['数字货币', 'fintech', '移动支付']
        }

    def get_stock_tags(self, symbol: str, company_name: str = "") -> Dict[str, List[str]]:
        """
        获取股票的标签信息

        Args:
            symbol: 股票代码
            company_name: 公司名称

        Returns:
            包含各类标签的字典
        """
        # 检查缓存
        cache_key = f"{symbol}_{company_name}"
        if self._is_cache_valid(cache_key):
            return self.tag_cache[cache_key]['data']

        # 获取股票标签
        tags = self._fetch_stock_tags(symbol, company_name)

        # 缓存结果
        self.tag_cache[cache_key] = {
            'data': tags,
            'timestamp': time.time()
        }

        return tags

    def _fetch_stock_tags(self, symbol: str, company_name: str) -> Dict[str, List[str]]:
        """获取股票标签信息"""
        tags = {
            'industry': [],      # 行业标签
            'sector': [],        # 板块标签
            'concept': [],       # 概念标签
            'keywords': []       # 关键词标签
        }

        try:
            # 尝试从多个来源获取标签
            self._fetch_from_akshare(symbol, tags)
            self._enrich_tags_by_name(company_name, tags)
            self._generate_search_keywords(symbol, company_name, tags)

            logger.info(f"获取股票标签完成 {symbol}: {len(tags['keywords'])} 个关键词")

        except Exception as e:
            logger.error(f"获取股票标签失败 {symbol}: {e}")
            # 使用基础标签
            tags = self._get_fallback_tags(symbol, company_name)

        return tags

    def _fetch_from_akshare(self, symbol: str, tags: Dict[str, List[str]]):
        """从AkShare获取股票分类信息"""
        try:
            import akshare as ak

            # 提取纯股票代码
            clean_symbol = symbol.replace('.SZ', '').replace('.SH', '').replace('.BJ', '')

            # 获取股票基本信息
            stock_info = ak.stock_individual_info_em(symbol=clean_symbol)
            if not stock_info.empty:
                for _, row in stock_info.iterrows():
                    item = str(row.get('item', ''))
                    value = str(row.get('value', ''))

                    if '行业' in item and value and value != 'nan':
                        industry = value.strip()
                        tags['industry'].append(industry)

                        # 根据行业映射添加相关标签
                        if industry in self.industry_mapping:
                            tags['sector'].extend(self.industry_mapping[industry])

                    elif '板块' in item and value and value != 'nan':
                        tags['sector'].append(value.strip())

            # 获取概念板块信息
            try:
                concept_info = ak.stock_board_concept_cons_em(symbol=clean_symbol)
                if not concept_info.empty:
                    for concept in concept_info['板块名称'].head(5):  # 取前5个概念
                        if concept and str(concept) != 'nan':
                            concept_name = str(concept).strip()
                            tags['concept'].append(concept_name)

                            # 根据概念映射添加关键词
                            for key_concept, keywords in self.concept_mapping.items():
                                if key_concept in concept_name:
                                    tags['keywords'].extend(keywords)
            except:
                pass

        except Exception as e:
            logger.debug(f"AkShare获取标签失败 {symbol}: {e}")

    def _enrich_tags_by_name(self, company_name: str, tags: Dict[str, List[str]]):
        """根据公司名称丰富标签"""
        if not company_name:
            return

        name = company_name.lower()

        # 科技类关键词
        if any(word in name for word in ['科技', '软件', '信息', '数据', '网络', '智能']):
            tags['sector'].extend(['科技股', 'IT'])
            tags['keywords'].extend(['科技', '创新', '数字化'])

        # 医药类关键词
        if any(word in name for word in ['医药', '生物', '制药', '医疗', '健康']):
            tags['sector'].extend(['医药股', '生物医药'])
            tags['keywords'].extend(['医药', '健康', '医疗'])

        # 金融类关键词
        if any(word in name for word in ['银行', '证券', '保险', '信托', '基金']):
            tags['sector'].extend(['金融股'])
            tags['keywords'].extend(['金融', '银行', '资本'])

        # 新能源关键词
        if any(word in name for word in ['新能源', '电池', '光伏', '风电', '充电']):
            tags['concept'].extend(['新能源', '清洁能源'])
            tags['keywords'].extend(['新能源', '电池', '清洁能源'])

        # 消费类关键词
        if any(word in name for word in ['食品', '饮料', '零售', '商贸', '消费']):
            tags['sector'].extend(['消费股'])
            tags['keywords'].extend(['消费', '品牌', '零售'])

    def _generate_search_keywords(self, symbol: str, company_name: str, tags: Dict[str, List[str]]):
        """生成搜索关键词"""
        keywords = set()

        # 添加公司名称和股票代码
        if company_name:
            keywords.add(company_name)
            # 提取公司名称中的关键词
            for word in ['集团', '股份', '有限', '公司']:
                company_name = company_name.replace(word, '')
            if len(company_name) >= 2:
                keywords.add(company_name)

        keywords.add(symbol.replace('.SZ', '').replace('.SH', '').replace('.BJ', ''))

        # 添加所有标签作为关键词
        for tag_list in tags.values():
            keywords.update(tag_list)

        # 清理和去重
        cleaned_keywords = []
        for keyword in keywords:
            keyword = str(keyword).strip()
            if keyword and len(keyword) >= 2 and keyword not in ['nan', 'None']:
                cleaned_keywords.append(keyword)

        tags['keywords'] = list(set(cleaned_keywords))[:15]  # 限制关键词数量

    def _get_fallback_tags(self, symbol: str, company_name: str) -> Dict[str, List[str]]:
        """获取备用标签（当主要方法失败时）"""
        tags = {
            'industry': ['未知行业'],
            'sector': ['A股'],
            'concept': [],
            'keywords': []
        }

        # 基于股票代码推断
        clean_symbol = symbol.replace('.SZ', '').replace('.SH', '').replace('.BJ', '')

        if clean_symbol.startswith('00'):
            tags['sector'].append('主板')
        elif clean_symbol.startswith('30'):
            tags['sector'].append('创业板')
        elif clean_symbol.startswith('60'):
            tags['sector'].append('沪市主板')
        elif clean_symbol.startswith('68'):
            tags['sector'].append('科创板')
            tags['keywords'].extend(['科技', '创新'])

        # 添加基础关键词
        keywords = [clean_symbol]
        if company_name:
            keywords.append(company_name)

        tags['keywords'] = keywords

        return tags

    def get_related_keywords_for_news(self, symbol: str, company_name: str = "") -> List[str]:
        """获取用于新闻搜索的相关关键词"""
        tags = self.get_stock_tags(symbol, company_name)

        # 构建搜索关键词列表，按重要性排序
        search_keywords = []

        # 1. 公司名称最重要
        if company_name:
            search_keywords.append(company_name)

        # 2. 主要行业和概念标签
        search_keywords.extend(tags.get('concept', [])[:3])  # 最多3个概念
        search_keywords.extend(tags.get('industry', [])[:2])  # 最多2个行业

        # 3. 板块标签
        search_keywords.extend(tags.get('sector', [])[:2])   # 最多2个板块

        # 4. 其他关键词
        search_keywords.extend(tags.get('keywords', [])[:5])  # 最多5个关键词

        # 去重并限制数量
        unique_keywords = []
        seen = set()
        for keyword in search_keywords:
            if keyword and keyword not in seen and len(keyword) >= 2:
                unique_keywords.append(keyword)
                seen.add(keyword)
                if len(unique_keywords) >= 8:  # 限制总数量
                    break

        return unique_keywords

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.tag_cache:
            return False

        cache_time = self.tag_cache[cache_key]['timestamp']
        return (time.time() - cache_time) < self.cache_duration

    def clear_cache(self):
        """清理缓存"""
        self.tag_cache.clear()
        logger.info("股票标签缓存已清理")

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        valid_count = 0
        expired_count = 0

        current_time = time.time()
        for key, item in self.tag_cache.items():
            if (current_time - item['timestamp']) < self.cache_duration:
                valid_count += 1
            else:
                expired_count += 1

        return {
            'total_cached': len(self.tag_cache),
            'valid_cached': valid_count,
            'expired_cached': expired_count,
            'cache_duration_hours': self.cache_duration / 3600
        }


# 全局实例
_stock_tag_manager = None

def get_stock_tag_manager() -> StockTagManager:
    """获取股票标签管理器单例"""
    global _stock_tag_manager
    if _stock_tag_manager is None:
        _stock_tag_manager = StockTagManager()
    return _stock_tag_manager

def get_stock_related_keywords(symbol: str, company_name: str = "") -> List[str]:
    """快捷函数：获取股票相关关键词用于新闻搜索"""
    return get_stock_tag_manager().get_related_keywords_for_news(symbol, company_name)