# -*- coding: utf-8 -*-
"""
板块轮动选股器
根据板块热度动态选择头部股票
"""

import logging
import time
import pandas as pd
import akshare as ak
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

# 导入网络辅助工具
try:
    from ..utils.network_helper import safe_akshare_call, retry_on_connection_error
except ImportError:
    from utils.network_helper import safe_akshare_call, retry_on_connection_error

logger = logging.getLogger(__name__)


@dataclass
class SectorInfo:
    """板块信息"""
    name: str                    # 板块名称
    code: str                    # 板块代码
    change_pct: float           # 涨跌幅
    total_market_cap: float     # 总市值（亿元）
    turnover_rate: float        # 换手率
    rising_count: int           # 上涨股票数
    falling_count: int          # 下跌股票数
    heat_score: float          # 热度评分
    rank: int = 0              # 热度排名


@dataclass
class SectorStock:
    """板块内股票信息"""
    symbol: str                 # 股票代码
    name: str                   # 股票名称
    sector: str                 # 所属板块
    price: float               # 最新价
    change_pct: float          # 涨跌幅
    market_cap: float          # 市值（亿元）
    turnover_rate: float       # 换手率
    volume: float              # 成交量
    amount: float              # 成交额（万元）
    amplitude: float           # 振幅
    stock_score: float         # 个股评分


class SectorRotationPicker:
    """板块轮动选股器"""

    def __init__(self, config: Dict):
        """
        初始化板块轮动选股器

        Args:
            config: 配置字典，包含板块轮动相关配置
        """
        self.config = config

        # 获取板块轮动配置
        rotation_config = config.get('stock_selection', {}).get('sector_rotation', {})

        # 核心参数
        self.hot_sector_count = rotation_config.get('hot_sector_count', 5)
        self.stocks_per_sector = rotation_config.get('stocks_per_sector', 3)
        self.total_sector_stocks = rotation_config.get('total_sector_stocks', 15)
        self.lookback_days = rotation_config.get('lookback_days', 5)
        self.min_sector_change = rotation_config.get('min_sector_change', 1.0)
        self.exclude_small_sectors = rotation_config.get('exclude_small_sectors', True)

        # 评分权重
        weights = rotation_config.get('weights', {})
        self.weight_change_pct = weights.get('change_pct', 0.40)
        self.weight_fund_flow = weights.get('fund_flow', 0.30)
        self.weight_volume = weights.get('volume_change', 0.20)
        self.weight_active = weights.get('active_ratio', 0.10)

        # 个股选择权重
        stock_weights = rotation_config.get('stock_selection_weights', {})
        self.stock_weight_market_cap = stock_weights.get('market_cap', 0.30)
        self.stock_weight_return = stock_weights.get('recent_return', 0.25)
        self.stock_weight_fund_flow = stock_weights.get('fund_flow', 0.25)
        self.stock_weight_technical = stock_weights.get('technical', 0.20)

        # 缓存
        self.cache = {}
        self.cache_timeout = 3600  # 1小时缓存

        logger.info(f"板块轮动选股器初始化: 选择{self.hot_sector_count}个热门板块，每板块{self.stocks_per_sector}只股票")

    def get_sector_rotation_stocks(self) -> List[Dict]:
        """
        获取板块轮动股票

        Returns:
            List[Dict]: 股票列表，每个元素包含 symbol, name, sector, score, reason
        """
        logger.info("开始板块轮动选股...")

        try:
            # 1. 获取所有板块数据
            sectors = self._fetch_all_sectors()
            if not sectors:
                logger.warning("未获取到板块数据")
                return []

            logger.info(f"获取到{len(sectors)}个板块数据")

            # 2. 计算板块热度并排序
            hot_sectors = self._rank_hot_sectors(sectors)
            if not hot_sectors:
                logger.warning("未找到符合条件的热门板块")
                return []

            logger.info(f"识别到{len(hot_sectors)}个热门板块")

            # 3. 从每个热门板块选择头部股票
            all_stocks = []
            for sector in hot_sectors[:self.hot_sector_count]:
                try:
                    sector_stocks = self._select_top_stocks_from_sector(sector)
                    all_stocks.extend(sector_stocks)
                    logger.info(f"板块[{sector.name}]选入{len(sector_stocks)}只股票")

                    # 限制总数量
                    if len(all_stocks) >= self.total_sector_stocks:
                        break

                    time.sleep(0.3)  # 避免请求过快

                except Exception as e:
                    logger.warning(f"处理板块{sector.name}失败: {e}")
                    continue

            # 4. 按评分排序并限制总数
            all_stocks.sort(key=lambda x: x['score'], reverse=True)
            final_stocks = all_stocks[:self.total_sector_stocks]

            logger.info(f"板块轮动选股完成: 共选出{len(final_stocks)}只股票")

            # 输出详细信息
            self._log_selection_summary(final_stocks, hot_sectors)

            return final_stocks

        except Exception as e:
            logger.error(f"板块轮动选股失败: {e}")
            return []

    @retry_on_connection_error(max_retries=2, delay=2.0)
    def _fetch_all_sectors(self) -> List[SectorInfo]:
        """
        获取所有板块数据

        Returns:
            List[SectorInfo]: 板块信息列表
        """
        cache_key = f"sectors_{datetime.now().strftime('%Y%m%d_%H')}"

        # 检查缓存
        if self._is_cache_valid(cache_key):
            logger.info("使用板块数据缓存")
            return self.cache[cache_key]['data']

        try:
            # 获取概念板块数据
            logger.info("获取概念板块数据...")
            df = safe_akshare_call("stock_board_concept_name_em")

            if df is None or df.empty:
                logger.warning("获取概念板块数据为空")
                return []

            logger.info(f"获取到{len(df)}个概念板块")

            sectors = []
            for _, row in df.iterrows():
                try:
                    # 提取板块信息
                    name = row.get('板块名称', '').strip()
                    code = row.get('板块代码', '').strip()
                    change_pct = float(row.get('涨跌幅', 0))

                    # 可选字段
                    total_market_cap = float(row.get('总市值', 0)) / 100000000  # 转为亿元
                    turnover_rate = float(row.get('换手率', 0))
                    rising_count = int(row.get('上涨家数', 0))
                    falling_count = int(row.get('下跌家数', 0))

                    if not name or not code:
                        continue

                    # 过滤条件
                    if self.exclude_small_sectors:
                        total_stocks = rising_count + falling_count
                        if total_stocks < 5:  # 成分股少于5只的板块
                            logger.debug(f"过滤小板块: {name} (仅{total_stocks}只股票)")
                            continue

                    # 创建板块信息
                    sector = SectorInfo(
                        name=name,
                        code=code,
                        change_pct=change_pct,
                        total_market_cap=total_market_cap,
                        turnover_rate=turnover_rate,
                        rising_count=rising_count,
                        falling_count=falling_count,
                        heat_score=0.0  # 稍后计算
                    )

                    sectors.append(sector)

                except Exception as e:
                    logger.debug(f"处理板块数据失败: {e}")
                    continue

            # 缓存结果
            self.cache[cache_key] = {
                'data': sectors,
                'timestamp': time.time()
            }

            return sectors

        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")
            return []

    def _calculate_sector_heat_score(self, sector: SectorInfo) -> float:
        """
        计算板块热度评分

        板块热度 = 涨跌幅(40%) + 资金流(30%) + 成交量变化(20%) + 活跃度(10%)

        Args:
            sector: 板块信息

        Returns:
            float: 热度评分 (0-100)
        """
        score = 0.0

        try:
            # 1. 涨跌幅评分 (40%)
            # 涨跌幅范围通常在 -10% 到 +10%，映射到 0-40 分
            change_score = min(40, max(0, (sector.change_pct + 10) * 2))
            score += change_score * self.weight_change_pct / 0.40

            # 2. 资金流评分 (30%) - 使用换手率和市值作为代理
            # 高换手率 + 高市值 = 资金活跃
            turnover_score = min(30, sector.turnover_rate * 3)
            market_cap_factor = min(1.5, sector.total_market_cap / 1000)  # 千亿以上满分
            fund_flow_score = turnover_score * market_cap_factor
            score += fund_flow_score * self.weight_fund_flow / 0.30

            # 3. 成交量变化评分 (20%) - 使用换手率作为代理
            volume_score = min(20, sector.turnover_rate * 2)
            score += volume_score * self.weight_volume / 0.20

            # 4. 活跃度评分 (10%) - 上涨股票占比
            total_stocks = sector.rising_count + sector.falling_count
            if total_stocks > 0:
                active_ratio = sector.rising_count / total_stocks
                active_score = active_ratio * 10
                score += active_score * self.weight_active / 0.10

            logger.debug(f"板块{sector.name}热度评分: {score:.2f} (涨跌{sector.change_pct:.2f}%, "
                        f"换手{sector.turnover_rate:.2f}%, 上涨{sector.rising_count}/{total_stocks})")

        except Exception as e:
            logger.debug(f"计算板块热度失败: {e}")
            score = 0.0

        return min(100, max(0, score))

    def _rank_hot_sectors(self, sectors: List[SectorInfo]) -> List[SectorInfo]:
        """
        排序并选择热门板块

        Args:
            sectors: 板块列表

        Returns:
            List[SectorInfo]: 排序后的热门板块列表
        """
        # 计算每个板块的热度评分
        for sector in sectors:
            sector.heat_score = self._calculate_sector_heat_score(sector)

        # 过滤涨幅过低的板块
        filtered_sectors = [
            s for s in sectors
            if s.change_pct >= self.min_sector_change
        ]

        logger.info(f"过滤后剩余{len(filtered_sectors)}个板块（最低涨幅{self.min_sector_change}%）")

        # 按热度评分排序
        filtered_sectors.sort(key=lambda x: x.heat_score, reverse=True)

        # 添加排名
        for i, sector in enumerate(filtered_sectors, 1):
            sector.rank = i

        return filtered_sectors

    @retry_on_connection_error(max_retries=2, delay=2.0)
    def _get_sector_constituents(self, sector: SectorInfo) -> List[SectorStock]:
        """
        获取板块成分股

        Args:
            sector: 板块信息

        Returns:
            List[SectorStock]: 板块内股票列表
        """
        cache_key = f"constituents_{sector.code}_{datetime.now().strftime('%Y%m%d_%H')}"

        # 检查缓存
        if self._is_cache_valid(cache_key):
            logger.debug(f"使用板块{sector.name}成分股缓存")
            return self.cache[cache_key]['data']

        try:
            logger.debug(f"获取板块{sector.name}的成分股...")
            df = safe_akshare_call("stock_board_concept_cons_em", symbol=sector.name)

            if df is None or df.empty:
                logger.warning(f"板块{sector.name}无成分股数据")
                return []

            stocks = []
            for _, row in df.iterrows():
                try:
                    # 提取股票信息
                    code = str(row.get('代码', '')).strip()
                    name = row.get('名称', '').strip()
                    price = float(row.get('最新价', 0))
                    change_pct = float(row.get('涨跌幅', 0))

                    # 标准化股票代码
                    symbol = self._normalize_stock_symbol(code)
                    if not symbol or not name:
                        continue

                    # 可选字段
                    turnover_rate = float(row.get('换手率', 0))
                    volume = float(row.get('成交量', 0))
                    amount = float(row.get('成交额', 0))
                    amplitude = float(row.get('振幅', 0))

                    # 估算市值（使用成交额和换手率）
                    market_cap = 0.0
                    if turnover_rate > 0:
                        market_cap = (amount * 10000) / (turnover_rate / 100) / 100000000  # 转为亿元

                    stock = SectorStock(
                        symbol=symbol,
                        name=name,
                        sector=sector.name,
                        price=price,
                        change_pct=change_pct,
                        market_cap=market_cap,
                        turnover_rate=turnover_rate,
                        volume=volume,
                        amount=amount,
                        amplitude=amplitude,
                        stock_score=0.0  # 稍后计算
                    )

                    stocks.append(stock)

                except Exception as e:
                    logger.debug(f"处理成分股数据失败: {e}")
                    continue

            # 缓存结果
            self.cache[cache_key] = {
                'data': stocks,
                'timestamp': time.time()
            }

            logger.debug(f"板块{sector.name}获取到{len(stocks)}只成分股")
            return stocks

        except Exception as e:
            logger.warning(f"获取板块{sector.name}成分股失败: {e}")
            return []

    def _calculate_stock_score_in_sector(
        self,
        stock: SectorStock,
        all_stocks: List[SectorStock]
    ) -> float:
        """
        计算板块内个股评分

        评分模型：
        - 市值排名 (30%)
        - 近期涨幅 (25%)
        - 资金流入强度 (25%) - 使用换手率和成交额作为代理
        - 技术指标 (20%) - 使用振幅和量价关系

        Args:
            stock: 股票信息
            all_stocks: 板块内所有股票列表

        Returns:
            float: 个股评分 (0-100)
        """
        score = 0.0

        try:
            # 1. 市值排名评分 (30%)
            sorted_by_cap = sorted(all_stocks, key=lambda x: x.market_cap, reverse=True)
            cap_rank = next((i for i, s in enumerate(sorted_by_cap, 1) if s.symbol == stock.symbol), len(sorted_by_cap))
            cap_percentile = 1 - (cap_rank - 1) / len(all_stocks)  # 排名越高，百分位越高
            cap_score = cap_percentile * 30
            score += cap_score * self.stock_weight_market_cap / 0.30

            # 2. 近期涨幅评分 (25%)
            # 涨幅范围 -10% 到 +10%，映射到 0-25 分
            return_score = min(25, max(0, (stock.change_pct + 10) * 1.25))
            score += return_score * self.stock_weight_return / 0.25

            # 3. 资金流入评分 (25%) - 换手率 * 成交额
            fund_activity = stock.turnover_rate * (stock.amount / 100000)  # 归一化
            fund_score = min(25, fund_activity * 0.5)
            score += fund_score * self.stock_weight_fund_flow / 0.25

            # 4. 技术指标评分 (20%)
            # 使用振幅作为活跃度指标
            technical_score = min(20, stock.amplitude)
            # 如果涨幅为正且有成交量，加分
            if stock.change_pct > 0 and stock.volume > 0:
                technical_score = min(20, technical_score * 1.2)
            score += technical_score * self.stock_weight_technical / 0.20

            logger.debug(f"股票{stock.name}评分: {score:.2f} (市值{cap_percentile:.2f}, "
                        f"涨幅{stock.change_pct:.2f}%, 换手{stock.turnover_rate:.2f}%)")

        except Exception as e:
            logger.debug(f"计算个股评分失败: {e}")
            score = 50.0  # 默认中等分数

        return min(100, max(0, score))

    def _select_top_stocks_from_sector(self, sector: SectorInfo) -> List[Dict]:
        """
        从板块中选择头部股票

        Args:
            sector: 板块信息

        Returns:
            List[Dict]: 股票列表
        """
        # 获取板块成分股
        stocks = self._get_sector_constituents(sector)

        if not stocks:
            return []

        # 计算每只股票的评分
        for stock in stocks:
            stock.stock_score = self._calculate_stock_score_in_sector(stock, stocks)

        # 按评分排序
        stocks.sort(key=lambda x: x.stock_score, reverse=True)

        # 选择前N只
        top_stocks = stocks[:self.stocks_per_sector]

        # 转换为返回格式
        result = []
        for stock in top_stocks:
            result.append({
                'symbol': stock.symbol,
                'name': stock.name,
                'sector': sector.name,
                'score': stock.stock_score,
                'reason': f"热门板块[{sector.name}]第{sector.rank}名, 板块涨幅{sector.change_pct:.2f}%",
                'sector_rank': sector.rank,
                'sector_heat': sector.heat_score,
                'change_pct': stock.change_pct,
                'market_cap': stock.market_cap
            })

        return result

    def _normalize_stock_symbol(self, code: str) -> Optional[str]:
        """
        标准化股票代码

        Args:
            code: 原始股票代码

        Returns:
            str: 标准化后的代码（如 000001.SZ）
        """
        if not code:
            return None

        code = str(code).strip()

        # 如果已经有后缀，直接返回
        if '.SH' in code or '.SZ' in code or '.BJ' in code:
            return code

        # 处理纯数字代码
        if code.isdigit() and len(code) == 6:
            # 过滤B股代码
            if code.startswith('90') or code.startswith('20'):
                return None
            elif code.startswith('60') or code.startswith('68'):
                return f"{code}.SH"
            elif code.startswith('00') or code.startswith('30'):
                return f"{code}.SZ"
            elif code.startswith('43') or code.startswith('83'):
                return f"{code}.BJ"

        # 默认深圳
        return f"{code[:6]}.SZ" if len(code) >= 6 else None

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.cache:
            return False

        cache_age = time.time() - self.cache[cache_key]['timestamp']
        return cache_age < self.cache_timeout

    def _log_selection_summary(self, stocks: List[Dict], hot_sectors: List[SectorInfo]):
        """输出选股摘要"""
        if not stocks:
            return

        logger.info(f"\n{'='*60}")
        logger.info("板块轮动选股摘要")
        logger.info(f"{'='*60}")

        # 热门板块列表
        logger.info(f"\n🔥 热门板块 Top {min(5, len(hot_sectors))}:")
        for sector in hot_sectors[:5]:
            logger.info(f"  {sector.rank}. {sector.name:20s} | "
                       f"涨幅:{sector.change_pct:>6.2f}% | "
                       f"热度:{sector.heat_score:>6.2f} | "
                       f"上涨:{sector.rising_count}/{sector.rising_count + sector.falling_count}")

        # 按板块分组统计
        sector_groups = {}
        for stock in stocks:
            sector = stock['sector']
            if sector not in sector_groups:
                sector_groups[sector] = []
            sector_groups[sector].append(stock)

        logger.info(f"\n📊 选股分布 (共{len(stocks)}只):")
        for sector, sector_stocks in sector_groups.items():
            logger.info(f"\n  板块: {sector}")
            for stock in sector_stocks:
                logger.info(f"    - {stock['name']}({stock['symbol']}) | "
                           f"评分:{stock['score']:.1f} | "
                           f"涨幅:{stock['change_pct']:.2f}%")

        logger.info(f"\n{'='*60}\n")


def create_sector_rotation_picker(config: Dict) -> SectorRotationPicker:
    """创建板块轮动选股器"""
    return SectorRotationPicker(config)
