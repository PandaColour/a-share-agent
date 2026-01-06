# -*- coding: utf-8 -*-
"""
动态股票选择器
支持多种股票来源：配置文件、龙虎榜、社交媒体热门股票
"""

import random
import logging
import requests
import pandas as pd
import akshare as ak
from typing import List, Tuple, Dict, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import time
import re

# 导入网络辅助工具
try:
    from ..utils.network_helper import safe_akshare_call, retry_on_connection_error, network_helper
except ImportError:
    from utils.network_helper import safe_akshare_call, retry_on_connection_error, network_helper

logger = logging.getLogger(__name__)

class StockSource(Enum):
    """股票来源类型"""
    CONFIG = "config"              # 配置文件固定股票
    LONGHU_BANG = "longhu_bang"    # 龙虎榜
    SOCIAL_MEDIA = "social_media"  # 社交媒体热门
    AUTO_DISCOVERY = "auto_discovery"  # 自动发现

@dataclass
class StockCandidate:
    """候选股票信息"""
    symbol: str
    name: str
    source: StockSource
    score: float  # 热度评分 0-100
    reason: str   # 入选原因
    market_cap: float = 0.0  # 市值（亿元）
    price: float = 0.0       # 当前价格
    change_pct: float = 0.0  # 涨跌幅
    volume_ratio: float = 1.0 # 量比
    
class DynamicStockSelector:
    """动态股票选择器"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        # 使用网络辅助工具的session，已配置重试和超时
        self.session = network_helper.session
        
        # 缓存，避免重复请求
        self.cache = {}
        self.cache_timeout = 300  # 5分钟缓存
        
    def select_stocks(self) -> Tuple[List[Tuple[str, str]], Dict]:
        """
        根据配置动态选择股票

        Returns:
            Tuple[List[Tuple[str, str]], Dict]: (股票代码和名称的列表, 详细统计数据)
        """
        logger.info("开始动态股票选择...")
        
        # 获取配置
        selection_config = self._get_selection_config()
        
        # 收集各种来源的候选股票 - 调整优先级顺序
        all_candidates = []

        # 第一优先级：配置文件固定股票（稳定基础）
        config_stocks = self._get_config_stocks(selection_config.get('config_count', 5))
        all_candidates.extend(config_stocks)
        logger.info(f"📊 配置文件股票: {len(config_stocks)} 只 (第一优先级)")

        # 第二优先级：潜力股挖掘（寻找机会）
        if selection_config.get('enable_potential', False):
            try:
                potential_stocks = self._get_potential_stocks(selection_config.get('potential_count', 5))
                all_candidates.extend(potential_stocks)
                logger.info(f"🔍 潜力股挖掘: {len(potential_stocks)} 只 (第二优先级)")
            except Exception as e:
                logger.warning(f"潜力股挖掘失败: {e}")

        # 第三优先级：龙虎榜股票（适量热门）
        if selection_config.get('enable_longhu', True):
            try:
                longhu_stocks = self._get_longhu_bang_stocks(selection_config.get('longhu_count', 3))
                all_candidates.extend(longhu_stocks)
                logger.info(f"🏆 龙虎榜股票: {len(longhu_stocks)} 只 (第三优先级)")
            except Exception as e:
                logger.warning(f"龙虎榜股票获取失败: {e}")

        # 第四优先级：社交媒体热门股票（少量热门）
        if selection_config.get('enable_social', True):
            try:
                social_stocks = self._get_social_media_stocks(selection_config.get('social_count', 2))
                all_candidates.extend(social_stocks)
                logger.info(f"📱 社交媒体股票: {len(social_stocks)} 只 (第四优先级)")
            except Exception as e:
                logger.warning(f"社交媒体股票获取失败: {e}")
        
        # 4. 去重并按评分排序
        unique_candidates = self._deduplicate_and_rank(all_candidates)
        
        # 5. 应用过滤器（除了价格限制）
        filtered_candidates = self._apply_filters(unique_candidates)
        
        # 6. 选择最终股票
        max_stocks = selection_config.get('max_total_stocks', 20)
        final_stocks = self._select_final_stocks(filtered_candidates, max_stocks)
        
        # 生成详细统计数据
        source_stats = self._generate_source_statistics(final_stocks)

        logger.info(f"动态选择完成: 共选择 {len(final_stocks)} 只股票")
        self._log_selection_summary(final_stocks)

        # 转换为 (symbol, name) 格式
        stock_tuples = [(stock.symbol, stock.name) for stock in final_stocks]

        return stock_tuples, source_stats
    
    def _get_selection_config(self) -> Dict:
        """获取股票选择配置"""
        if self.config_manager:
            return self.config_manager.get('stock_selection', {
                'config_count': 8,      # 配置文件固定股票数量
                'longhu_count': 5,      # 龙虎榜股票数量
                'social_count': 3,      # 社交媒体热门股票数量
                'max_total_stocks': 20, # 总股票数量上限
                'enable_longhu': True,  # 是否启用龙虎榜
                'enable_social': True,  # 是否启用社交媒体
                'score_threshold': 30   # 最低评分阈值
            })
        else:
            # 默认配置
            return {
                'config_count': 8,
                'longhu_count': 5,
                'social_count': 3,
                'max_total_stocks': 20,
                'enable_longhu': True,
                'enable_social': True,
                'score_threshold': 30
            }
    
    def _get_config_stocks(self, count: int) -> List[StockCandidate]:
        """
        获取配置文件中的所有持仓股票

        注意：count 参数保留用于向后兼容，但实际上会返回所有 hold_stock.json 中的股票。
        这样确保所有持仓股票都参与分析，buy_flag 只影响持仓分析结果。
        """
        try:
            from src.stock import get_all_stocks
            all_config_stocks = get_all_stocks()

            # 返回所有配置股票，不进行随机采样
            # 这样确保所有 hold_stock.json 中的股票都能被分析
            candidates = []
            for symbol, name in all_config_stocks:
                candidate = StockCandidate(
                    symbol=symbol,
                    name=name,
                    source=StockSource.CONFIG,
                    score=70.0,  # 配置股票给固定高分
                    reason="持仓股票池"
                )
                candidates.append(candidate)

            logger.info(f"加载所有持仓股票: {len(candidates)} 只（忽略 config_count 配置）")
            return candidates

        except Exception as e:
            logger.error(f"获取配置股票失败: {e}")
            return []
    
    @retry_on_connection_error(max_retries=0, delay=2.0)
    def _get_longhu_bang_stocks(self, count: int) -> List[StockCandidate]:
        """获取龙虎榜和资金流活跃股票"""
        cache_key = f"longhu_bang_{datetime.now().strftime('%Y%m%d')}"
        
        # 检查缓存
        if self._is_cache_valid(cache_key):
            logger.info("使用龙虎榜缓存数据")
            return self.cache[cache_key]['data']
        
        candidates = []
        
        try:
            # 方法1: 获取资金流排名数据（更可靠）
            logger.info("获取主力资金流排名数据...")
            fund_flow_df = safe_akshare_call("stock_individual_fund_flow_rank", indicator="今日")
            
            if fund_flow_df is not None and not fund_flow_df.empty:
                logger.info(f"获取到资金流数据: {len(fund_flow_df)} 只股票")
                
                # 筛选主力净流入较大的股票
                for _, row in fund_flow_df.head(count * 3).iterrows():
                    try:
                        symbol = self._normalize_stock_symbol(row.get('代码', ''))
                        if symbol is None:  # 过滤掉B股等不支持的代码
                            continue
                        name = row.get('名称', '').strip()
                        change_pct = float(row.get('今日涨跌幅', 0))
                        net_inflow = float(row.get('今日主力净流入-净额', 0))
                        
                        if symbol and name and abs(net_inflow) > 1000000:  # 净流入超过100万
                            # 基于资金流计算评分
                            score = self._calculate_fund_flow_score(row)
                            
                            candidate = StockCandidate(
                                symbol=symbol,
                                name=name,
                                source=StockSource.LONGHU_BANG,
                                score=score,
                                reason=f"主力资金{'流入' if net_inflow > 0 else '流出'}{abs(net_inflow)/10000:.0f}万",
                                change_pct=change_pct
                            )
                            candidates.append(candidate)
                            
                    except Exception as e:
                        logger.debug(f"处理资金流数据失败: {e}")
                        continue
            
            # 方法2: 尝试获取龙虎榜详情数据
            try:
                logger.info("尝试获取龙虎榜详情数据...")
                end_date = datetime.now()
                start_date = end_date - timedelta(days=2)
                
                lhb_df = safe_akshare_call("stock_lhb_detail_em",
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d')
                )
                
                if lhb_df is not None and not lhb_df.empty:
                    logger.info(f"获取到龙虎榜数据: {len(lhb_df)} 条")
                    
                    for _, row in lhb_df.head(count * 2).iterrows():
                        try:
                            symbol = self._normalize_stock_symbol(row.get('代码', ''))
                            if symbol is None:  # 过滤掉B股等不支持的代码
                                continue
                            name = row.get('名称', '').strip()
                            change_pct = float(row.get('涨跌幅', 0))
                            
                            if symbol and name:
                                score = self._calculate_longhu_score(row)
                                
                                candidate = StockCandidate(
                                    symbol=symbol,
                                    name=name,
                                    source=StockSource.LONGHU_BANG,
                                    score=score,
                                    reason=f"龙虎榜活跃",
                                    change_pct=change_pct
                                )
                                candidates.append(candidate)
                                
                        except Exception as e:
                            logger.debug(f"处理龙虎榜数据失败: {e}")
                            continue
                            
            except Exception as e:
                logger.debug(f"龙虎榜详情数据获取失败: {e}")
            
            # 去重并选择评分最高的
            unique_candidates = {}
            for candidate in candidates:
                if candidate.symbol not in unique_candidates or candidate.score > unique_candidates[candidate.symbol].score:
                    unique_candidates[candidate.symbol] = candidate
            
            final_candidates = sorted(unique_candidates.values(), key=lambda x: x.score, reverse=True)[:count]
            
            # 缓存结果
            self.cache[cache_key] = {
                'data': final_candidates,
                'timestamp': time.time()
            }
            
            logger.info(f"龙虎榜股票获取成功: {len(final_candidates)} 只")
            return final_candidates
            
        except Exception as e:
            logger.error(f"龙虎榜数据获取失败: {e}")
            return []
    
    @retry_on_connection_error(max_retries=0, delay=2.0)
    def _get_social_media_stocks(self, count: int) -> List[StockCandidate]:
        """获取社交媒体热门股票"""
        cache_key = f"social_media_{datetime.now().strftime('%Y%m%d_%H')}"
        
        # 检查缓存
        if self._is_cache_valid(cache_key):
            logger.info("使用社交媒体缓存数据")
            return self.cache[cache_key]['data']
        
        candidates = []
        
        try:
            # 方法1: 获取东方财富热门股票
            hot_stocks = self._get_eastmoney_hot_stocks(count)
            candidates.extend(hot_stocks)
            
            # 方法2: 获取同花顺热门概念股票
            concept_stocks = self._get_concept_hot_stocks(count // 2)
            candidates.extend(concept_stocks)
            
            # 去重并选择最好的
            unique_candidates = {}
            for candidate in candidates:
                if candidate.symbol not in unique_candidates or candidate.score > unique_candidates[candidate.symbol].score:
                    unique_candidates[candidate.symbol] = candidate
            
            final_candidates = sorted(unique_candidates.values(), key=lambda x: x.score, reverse=True)[:count]
            
            # 缓存结果
            self.cache[cache_key] = {
                'data': final_candidates,
                'timestamp': time.time()
            }
            
            logger.info(f"社交媒体股票获取成功: {len(final_candidates)} 只")
            return final_candidates
            
        except Exception as e:
            logger.error(f"社交媒体数据获取失败: {e}")
            return []
    
    @retry_on_connection_error(max_retries=0, delay=2.0)
    def _get_eastmoney_hot_stocks(self, count: int) -> List[StockCandidate]:
        """获取东方财富热门股票"""
        candidates = []
        
        try:
            # 获取热门股票数据
            df = safe_akshare_call("stock_hot_rank_em")
            
            if df is not None and not df.empty:
                logger.info(f"获取到东方财富热门股票: {len(df)} 只")
                
                for _, row in df.head(count * 2).iterrows():
                    try:
                        # 检查实际的列名
                        available_columns = list(row.index)
                        
                        # 尝试不同的列名组合
                        symbol_key = None
                        name_key = None
                        rank_key = None
                        
                        for col in available_columns:
                            if '代码' in col:
                                symbol_key = col
                            elif '名称' in col or '股票名称' in col:
                                name_key = col
                            elif '排名' in col or '当前排名' in col:
                                rank_key = col
                        
                        if not symbol_key or not name_key:
                            continue
                            
                        symbol = self._normalize_stock_symbol(row.get(symbol_key, ''))
                        if symbol is None:  # 过滤掉B股等不支持的代码
                            continue
                        name = row.get(name_key, '').strip()

                        if symbol and name:
                            # 基于排名和其他信息计算评分
                            if rank_key:
                                rank = int(row.get(rank_key, 999))
                            else:
                                rank = 999
                            score = max(20, 100 - rank * 2)  # 排名越靠前评分越高
                            
                            candidate = StockCandidate(
                                symbol=symbol,
                                name=name,
                                source=StockSource.SOCIAL_MEDIA,
                                score=score,
                                reason=f"东方财富热榜第{rank}名"
                            )
                            candidates.append(candidate)
                            
                    except Exception as e:
                        logger.debug(f"处理热门股票单条数据失败: {e}")
                        continue
            
        except Exception as e:
            logger.debug(f"获取东方财富热门股票失败: {e}")
        
        return candidates
    
    @retry_on_connection_error(max_retries=0, delay=2.0)
    def _get_concept_hot_stocks(self, count: int) -> List[StockCandidate]:
        """获取概念热门股票"""
        candidates = []
        
        try:
            # 获取概念板块数据
            df = safe_akshare_call("stock_board_concept_name_em")
            
            if df is not None and not df.empty:
                # 选择涨幅较大的概念
                hot_concepts = df.head(5)['板块名称'].tolist()
                
                for concept in hot_concepts:
                    try:
                        # 获取概念内的股票
                        concept_stocks = safe_akshare_call("stock_board_concept_cons_em", symbol=concept)
                        
                        if concept_stocks is not None and not concept_stocks.empty:
                            # 选择概念内涨幅最大的股票
                            for _, row in concept_stocks.head(2).iterrows():
                                symbol = self._normalize_stock_symbol(row.get('代码', ''))
                                if symbol is None:  # 过滤掉B股等不支持的代码
                                    continue
                                name = row.get('名称', '').strip()
                                change_pct = float(row.get('涨跌幅', 0))
                                
                                if symbol and name:
                                    score = 60 + min(30, abs(change_pct) * 3)  # 基于涨跌幅计算评分
                                    
                                    candidate = StockCandidate(
                                        symbol=symbol,
                                        name=name,
                                        source=StockSource.SOCIAL_MEDIA,
                                        score=score,
                                        reason=f"{concept}概念热门",
                                        change_pct=change_pct
                                    )
                                    candidates.append(candidate)
                        
                        time.sleep(0.3)  # 避免请求过快
                        
                    except Exception as e:
                        logger.debug(f"获取概念 {concept} 股票失败: {e}")
                        continue
        
        except Exception as e:
            logger.debug(f"获取概念热门股票失败: {e}")
        
        return candidates[:count]

    def _get_potential_stocks(self, count: int) -> List[StockCandidate]:
        """获取潜力股票"""
        try:
            from .potential_stock_finder import create_potential_stock_finder

            finder = create_potential_stock_finder()
            potential_stocks = finder.find_potential_stocks(count)

            candidates = []
            for stock in potential_stocks:
                candidate = StockCandidate(
                    symbol=stock.symbol,
                    name=stock.name,
                    source=StockSource.AUTO_DISCOVERY,
                    score=stock.potential_score,
                    reason=stock.reason,
                    change_pct=stock.change_pct
                )
                candidates.append(candidate)

            logger.info(f"潜力股获取成功: {len(candidates)} 只")
            return candidates

        except Exception as e:
            logger.error(f"潜力股获取失败: {e}")
            return []
    
    def _normalize_stock_symbol(self, symbol: str) -> str:
        """标准化股票代码"""
        if not symbol:
            return ""

        # 清理股票代码
        symbol = str(symbol).strip().upper()

        # 处理带前缀的情况 (如 SH600376, SZ000001)
        if symbol.startswith('SH') and len(symbol) >= 8:
            # 提取数字部分 SH600376 -> 600376
            code_part = symbol[2:]
            if code_part.isdigit() and len(code_part) == 6:
                return f"{code_part}.SH"  # 上海交易所使用.SH后缀
        elif symbol.startswith('SZ') and len(symbol) >= 8:
            # 提取数字部分 SZ000001 -> 000001
            code_part = symbol[2:]
            if code_part.isdigit() and len(code_part) == 6:
                return f"{code_part}.SZ"  # 深圳交易所使用.SZ后缀

        # 如果已经有标准后缀，检查格式并标准化
        if '.SH' in symbol or '.SZ' in symbol or '.BJ' in symbol:
            # 移除可能的前缀 (如 SH600376.SZ -> 600376.SH)
            if symbol.startswith('SH') and symbol.endswith('.SZ'):
                code_part = symbol[2:8]  # 提取中间6位数字
                if code_part.isdigit():
                    return f"{code_part}.SH"  # 上海股票应该用.SH后缀
            elif symbol.startswith('SZ') and symbol.endswith('.SH'):
                code_part = symbol[2:8]  # 提取中间6位数字
                if code_part.isdigit():
                    return f"{code_part}.SZ"  # 深圳股票应该用.SZ后缀
            else:
                return symbol  # 格式正确，直接返回

        # 处理纯数字代码，根据开头数字确定市场
        if symbol.isdigit() and len(symbol) == 6:
            # 过滤B股代码
            if symbol.startswith('90') or symbol.startswith('20'):
                logger.debug(f"过滤B股代码: {symbol}")
                return None  # 返回None表示过滤掉此代码
            elif symbol.startswith('60') or symbol.startswith('68'):
                return f"{symbol}.SH"  # 上海交易所
            elif symbol.startswith('00') or symbol.startswith('30'):
                return f"{symbol}.SZ"  # 深圳交易所
            elif symbol.startswith('43') or symbol.startswith('83'):
                return f"{symbol}.BJ"  # 北京交易所

        # 默认处理 - 记录警告
        logger.warning(f"无法标准化股票代码: {symbol}，使用默认处理")
        if symbol.startswith('6'):
            return f"{symbol[:6]}.SH"
        else:
            return f"{symbol[:6]}.SZ"
    
    def _calculate_longhu_score(self, row) -> float:
        """计算龙虎榜股票的热度评分"""
        score = 50.0  # 基础分
        
        try:
            # 涨跌幅影响
            change_pct = float(row.get('涨跌幅', 0))
            score += min(20, abs(change_pct) * 2)
            
            # 换手率影响
            turnover = float(row.get('换手率', 0))
            score += min(15, turnover)
            
            # 净买入额影响（如果有的话）
            net_amount = row.get('净买入额', 0)
            if net_amount and float(net_amount) > 0:
                score += 10
            
            # 上榜次数影响（如果有的话）
            times = row.get('上榜次数', 0)
            if times and int(times) > 1:
                score += min(5, int(times))
            
        except Exception as e:
            logger.debug(f"计算龙虎榜评分失败: {e}")
        
        return min(100, max(20, score))
    
    def _calculate_fund_flow_score(self, row) -> float:
        """计算资金流股票的热度评分"""
        score = 60.0  # 基础分
        
        try:
            # 主力净流入影响
            net_inflow = float(row.get('今日主力净流入-净额', 0))
            net_ratio = float(row.get('今日主力净流入-净占比', 0))
            
            # 资金流入越大评分越高
            if net_inflow > 0:
                score += min(25, net_inflow / 1000000 * 2)  # 每1000万加2分，最多25分
            else:
                score += min(15, abs(net_inflow) / 1000000 * 1.5)  # 流出也有一定热度
            
            # 净占比影响
            score += min(10, abs(net_ratio) * 0.5)
            
            # 涨跌幅影响
            change_pct = float(row.get('今日涨跌幅', 0))
            score += min(15, abs(change_pct) * 2)
            
        except Exception as e:
            logger.debug(f"计算资金流评分失败: {e}")
        
        return min(100, max(30, score))
    
    def _deduplicate_and_rank(self, candidates: List[StockCandidate]) -> List[StockCandidate]:
        """去重并按评分排序"""
        unique_stocks = {}
        
        for candidate in candidates:
            symbol = candidate.symbol
            
            if symbol not in unique_stocks:
                unique_stocks[symbol] = candidate
            else:
                # 如果已存在，保留评分更高的或者来源更优的
                existing = unique_stocks[symbol]
                
                # 来源优先级: CONFIG > AUTO_DISCOVERY(潜力股) > LONGHU_BANG > SOCIAL_MEDIA
                source_priority = {
                    StockSource.CONFIG: 4,           # 最高优先级
                    StockSource.AUTO_DISCOVERY: 3,   # 潜力股第二优先级
                    StockSource.LONGHU_BANG: 2,      # 龙虎榜第三优先级
                    StockSource.SOCIAL_MEDIA: 1      # 社交媒体最低优先级
                }
                
                # 综合评分：原评分 + 来源优先级加分
                candidate_score = candidate.score + source_priority.get(candidate.source, 0) * 5
                existing_score = existing.score + source_priority.get(existing.source, 0) * 5
                
                if candidate_score > existing_score:
                    # 合并原因
                    candidate.reason += f"; 同时来自: {existing.reason}"
                    unique_stocks[symbol] = candidate
                else:
                    existing.reason += f"; 同时来自: {candidate.reason}"
        
        # 按来源优先级+评分排序（保持我们设置的优先级顺序）
        def sort_key(candidate):
            source_priority = {
                StockSource.CONFIG: 4,           # 最高优先级
                StockSource.AUTO_DISCOVERY: 3,   # 潜力股第二优先级
                StockSource.LONGHU_BANG: 2,      # 龙虎榜第三优先级
                StockSource.SOCIAL_MEDIA: 1      # 社交媒体最低优先级
            }
            # 优先级权重更高，确保来源顺序优于评分
            priority_weight = source_priority.get(candidate.source, 0) * 100
            return priority_weight + candidate.score

        return sorted(unique_stocks.values(), key=sort_key, reverse=True)
    
    def _apply_filters(self, candidates: List[StockCandidate]) -> List[StockCandidate]:
        """
        应用过滤条件
        - analysis_settings.filters: 应用到所有股票（基础市场准入门槛）
        - stock_selection.filters: 仅应用到潜力股（技术指标筛选）
        """
        filtered = []
        selection_config = self._get_selection_config()

        # 获取两套过滤器配置
        potential_filters = selection_config.get('filters', {})  # stock_selection.filters - 仅潜力股
        global_filters = {}
        if self.config_manager:
            global_filters = self.config_manager.get('analysis_settings.filters', {})  # 全局基础过滤器

        for candidate in candidates:
            # 基本检查
            if not candidate.symbol or not candidate.name:
                continue

            # === 全局基础过滤器（应用到所有股票） ===

            # ST股票过滤（全局）
            exclude_st = global_filters.get('exclude_st', True)
            if exclude_st and ('ST' in candidate.name or '*ST' in candidate.name):
                logger.debug(f"过滤ST股票: {candidate.name}")
                continue

            # 科创板和创业板过滤（全局）
            exclude_chinext = global_filters.get('exclude_chinext', True)
            if exclude_chinext and candidate.symbol.startswith('30'):
                logger.debug(f"过滤创业板股票: {candidate.name}")
                continue

            # 价格限制（全局）
            if global_filters.get('enable_price_limits', False):
                price_min = global_filters.get('price_limit_min', 0.0)
                price_max = global_filters.get('price_limit_max', 100000.0)
                if candidate.price > 0:  # 只有当有价格数据时才应用
                    if candidate.price < price_min or candidate.price > price_max:
                        logger.debug(f"过滤价格超限股票: {candidate.name} (价格: {candidate.price}元)")
                        continue

            # === 潜力股专用技术过滤器（仅应用到潜力股） ===
            if candidate.source == StockSource.AUTO_DISCOVERY:
                # 涨跌幅过滤（避免已大涨或暴跌的潜力股）
                max_change = potential_filters.get('max_daily_change', 8)
                min_change = potential_filters.get('min_daily_change', -8)
                if candidate.change_pct > max_change or candidate.change_pct < min_change:
                    logger.debug(f"过滤极端波动潜力股: {candidate.name} (涨跌幅: {candidate.change_pct}%)")
                    continue

                # RSI过滤（避免超买的潜力股）
                max_rsi = potential_filters.get('max_rsi', 75)
                if hasattr(candidate, 'rsi') and candidate.rsi and candidate.rsi > max_rsi:
                    logger.debug(f"过滤超买潜力股: {candidate.name} (RSI: {candidate.rsi})")
                    continue

                # 量比过滤（潜力股需要适度的成交量）
                min_volume_ratio = potential_filters.get('min_volume_ratio', 0.8)
                max_volume_ratio = potential_filters.get('max_volume_ratio', 8)
                if candidate.volume_ratio < min_volume_ratio or candidate.volume_ratio > max_volume_ratio:
                    logger.debug(f"过滤量比异常潜力股: {candidate.name} (量比: {candidate.volume_ratio})")
                    continue

            # 评分阈值过滤（应用到所有股票）
            score_threshold = selection_config.get('score_threshold', 30)
            if candidate.score < score_threshold:
                logger.debug(f"过滤低评分股票: {candidate.name} (评分: {candidate.score})")
                continue

            filtered.append(candidate)

        logger.info(f"过滤后剩余候选股票: {len(filtered)} 只")
        return filtered
    
    def _select_final_stocks(self, candidates: List[StockCandidate], max_count: int) -> List[StockCandidate]:
        """选择最终的股票列表"""
        if len(candidates) <= max_count:
            return candidates
        
        # 按新的优先级顺序分层选择
        config_stocks = [c for c in candidates if c.source == StockSource.CONFIG]
        potential_stocks = [c for c in candidates if c.source == StockSource.AUTO_DISCOVERY]
        longhu_stocks = [c for c in candidates if c.source == StockSource.LONGHU_BANG]
        social_stocks = [c for c in candidates if c.source == StockSource.SOCIAL_MEDIA]

        final_stocks = []

        # 第一优先级：保证配置股票（最多占40%）
        config_count = min(len(config_stocks), int(max_count * 0.4))
        final_stocks.extend(config_stocks[:config_count])
        logger.info(f"✅ 选入配置股票: {config_count} 只")

        remaining_slots = max_count - len(final_stocks)

        # 第二优先级：潜力股票（占剩余的50%）
        potential_count = min(len(potential_stocks), int(remaining_slots * 0.5))
        final_stocks.extend(potential_stocks[:potential_count])
        logger.info(f"🔍 选入潜力股票: {potential_count} 只")

        remaining_slots = max_count - len(final_stocks)

        # 第三优先级：龙虎榜股票（占剩余的60%）
        longhu_count = min(len(longhu_stocks), int(remaining_slots * 0.6))
        final_stocks.extend(longhu_stocks[:longhu_count])
        logger.info(f"🏆 选入龙虎榜股票: {longhu_count} 只")

        remaining_slots = max_count - len(final_stocks)

        # 第四优先级：社交媒体股票（填满剩余位置）
        social_count = min(len(social_stocks), remaining_slots)
        final_stocks.extend(social_stocks[:social_count])
        logger.info(f"📱 选入社交媒体股票: {social_count} 只")
        
        return final_stocks

    def _generate_source_statistics(self, final_stocks: List[StockCandidate]) -> Dict:
        """
        生成详细的来源统计数据

        Args:
            final_stocks: 最终选择的股票列表

        Returns:
            包含详细统计信息的字典
        """
        from datetime import datetime

        # 按来源统计
        source_counts = {}
        source_details = {}

        for stock in final_stocks:
            source = stock.source.value

            # 统计数量
            source_counts[source] = source_counts.get(source, 0) + 1

            # 收集详细信息
            if source not in source_details:
                source_details[source] = []

            source_details[source].append({
                'symbol': stock.symbol,
                'name': stock.name,
                'score': stock.score,
                'reason': stock.reason,
                'change_pct': stock.change_pct
            })

        # 构建统计数据
        stats = {
            'selection_method': 'dynamic',
            'total_selected': len(final_stocks),
            'selection_time': datetime.now().isoformat(),
            'sources': source_counts,
            'source_details': source_details,
            'summary': {
                'config': source_counts.get('config', 0),
                'longhu_bang': source_counts.get('longhu_bang', 0),
                'social_media': source_counts.get('social_media', 0),
                'auto_discovery': source_counts.get('auto_discovery', 0)
            }
        }

        return stats

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.cache:
            return False
        
        cache_age = time.time() - self.cache[cache_key]['timestamp']
        return cache_age < self.cache_timeout
    
    def _log_selection_summary(self, final_stocks: List[StockCandidate]):
        """记录选择结果摘要"""
        if not final_stocks:
            logger.warning("未选择到任何股票")
            return
        
        # 按来源统计
        source_stats = {}
        for stock in final_stocks:
            source = stock.source.value
            source_stats[source] = source_stats.get(source, 0) + 1
        
        logger.info("股票来源分布:")
        for source, count in source_stats.items():
            logger.info(f"  {source}: {count} 只")
        
        # 显示所有选择的股票
        logger.info("最终选择的股票:")
        for i, stock in enumerate(final_stocks, 1):
            logger.info(f"  {i:2d}. {stock.name}({stock.symbol}) - "
                       f"{stock.source.value} - 评分:{stock.score:.1f} - {stock.reason}")

# 便捷函数
def create_dynamic_stock_selector(config_manager=None) -> DynamicStockSelector:
    """创建动态股票选择器"""
    return DynamicStockSelector(config_manager)

def get_dynamic_stock_list(config_manager=None) -> List[Tuple[str, str]]:
    """获取动态股票列表（兼容旧接口）"""
    selector = create_dynamic_stock_selector(config_manager)
    stock_list, _ = selector.select_stocks()  # 只返回股票列表，丢弃统计数据
    return stock_list

def get_dynamic_stock_list_with_stats(config_manager=None) -> Tuple[List[Tuple[str, str]], Dict]:
    """获取动态股票列表和详细统计数据"""
    selector = create_dynamic_stock_selector(config_manager)
    return selector.select_stocks()