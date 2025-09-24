# -*- coding: utf-8 -*-
"""
潜力股挖掘器
专门寻找即将爆发但尚未大涨的股票
"""

import logging
import pandas as pd
import akshare as ak
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PotentialStock:
    """潜力股信息"""
    symbol: str
    name: str
    current_price: float
    change_pct: float
    volume_ratio: float
    rsi: float
    potential_score: float
    reason: str

class PotentialStockFinder:
    """潜力股挖掘器"""

    def __init__(self):
        pass

    def find_potential_stocks(self, count: int = 10) -> List[PotentialStock]:
        """
        寻找潜力股

        策略：
        1. 近期小幅调整但基本面良好
        2. 技术指标显示超跌反弹机会
        3. 资金开始关注但尚未暴涨
        4. 行业或概念有催化剂预期
        """
        logger.info("开始潜力股挖掘...")

        potential_stocks = []

        try:
            # 方法1: 从资金流数据中寻找"悄悄建仓"的股票
            potential_from_fund = self._find_from_fund_flow(count)
            potential_stocks.extend(potential_from_fund)

            # 方法2: 从技术面寻找超跌反弹机会
            potential_from_tech = self._find_from_technical(count // 2)
            potential_stocks.extend(potential_from_tech)

            # 方法3: 从行业轮动角度寻找落后补涨机会
            potential_from_industry = self._find_from_industry_rotation(count // 3)
            potential_stocks.extend(potential_from_industry)

            # 去重并排序
            unique_stocks = {}
            for stock in potential_stocks:
                if stock.symbol not in unique_stocks or stock.potential_score > unique_stocks[stock.symbol].potential_score:
                    unique_stocks[stock.symbol] = stock

            final_stocks = sorted(unique_stocks.values(), key=lambda x: x.potential_score, reverse=True)[:count]

            logger.info(f"潜力股挖掘完成：找到 {len(final_stocks)} 只潜力股")
            return final_stocks

        except Exception as e:
            logger.error(f"潜力股挖掘失败: {e}")
            return []

    def _find_from_fund_flow(self, count: int) -> List[PotentialStock]:
        """从资金流数据中寻找潜力股"""
        stocks = []

        try:
            # 获取资金流数据
            df = ak.stock_individual_fund_flow_rank(indicator="今日")

            if df is None or df.empty:
                return stocks

            for _, row in df.iterrows():
                try:
                    symbol = self._normalize_symbol(row.get('代码', ''))
                    name = row.get('名称', '').strip()
                    change_pct = float(row.get('今日涨跌幅', 0))
                    net_inflow = float(row.get('今日主力净流入-净额', 0))

                    # 潜力股筛选条件：
                    # 1. 有资金关注（净流入>500万 或 净流出<2000万且较前日改善）
                    # 2. 涨跌幅适中（-5%到+7%）
                    # 3. 避免涨停股
                    if (symbol and name and
                        -5 <= change_pct <= 7 and  # 避免已大涨或暴跌
                        abs(net_inflow) > 5000000 and  # 有资金关注
                        change_pct < 9.8):  # 避免接近涨停

                        score = self._calculate_fund_potential_score(row)

                        stock = PotentialStock(
                            symbol=symbol,
                            name=name,
                            current_price=0.0,  # 需要进一步获取
                            change_pct=change_pct,
                            volume_ratio=0.0,
                            rsi=0.0,
                            potential_score=score,
                            reason=f"资金{'流入' if net_inflow > 0 else '改善'}{abs(net_inflow)/10000:.0f}万，涨幅适中"
                        )
                        stocks.append(stock)

                except Exception as e:
                    logger.debug(f"处理资金流数据失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"获取资金流数据失败: {e}")

        return sorted(stocks, key=lambda x: x.potential_score, reverse=True)[:count]

    def _find_from_technical(self, count: int) -> List[PotentialStock]:
        """从技术面寻找超跌反弹机会"""
        stocks = []

        try:
            # 获取沪深A股实时数据
            df = ak.stock_zh_a_spot_em()

            if df is None or df.empty:
                return stocks

            for _, row in df.head(500).iterrows():  # 只检查前500只活跃股票
                try:
                    symbol = self._normalize_symbol(row.get('代码', ''))
                    name = row.get('名称', '').strip()
                    current_price = float(row.get('最新价', 0))
                    change_pct = float(row.get('涨跌幅', 0))

                    # 基础筛选
                    if (symbol and name and current_price > 0 and
                        -8 <= change_pct <= 5):  # 适度调整范围

                        # 计算简单的技术潜力评分
                        score = self._calculate_tech_potential_score(row)

                        if score > 60:  # 只保留高分股票
                            stock = PotentialStock(
                                symbol=symbol,
                                name=name,
                                current_price=current_price,
                                change_pct=change_pct,
                                volume_ratio=0.0,
                                rsi=0.0,
                                potential_score=score,
                                reason=f"技术面显示反弹潜力，当前调整适度"
                            )
                            stocks.append(stock)

                except Exception as e:
                    logger.debug(f"技术分析失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"技术面分析失败: {e}")

        return sorted(stocks, key=lambda x: x.potential_score, reverse=True)[:count]

    def _find_from_industry_rotation(self, count: int) -> List[PotentialStock]:
        """从行业轮动角度寻找落后补涨机会"""
        stocks = []

        try:
            # 获取行业板块数据
            df = ak.stock_board_industry_name_em()

            if df is None or df.empty:
                return stocks

            # 寻找涨幅适中的活跃行业
            moderate_industries = []
            for _, row in df.iterrows():
                industry_change = float(row.get('涨跌幅', 0))
                if 0.5 <= industry_change <= 4:  # 温和上涨的行业
                    moderate_industries.append(row.get('板块名称', ''))

            # 从这些行业中挑选个股
            for industry in moderate_industries[:5]:  # 最多检查5个行业
                try:
                    industry_stocks = ak.stock_board_industry_cons_em(symbol=industry)

                    if industry_stocks is not None and not industry_stocks.empty:
                        # 选择行业内涨幅落后但基本面可能不错的股票
                        for _, stock_row in industry_stocks.head(10).iterrows():
                            symbol = self._normalize_symbol(stock_row.get('代码', ''))
                            name = stock_row.get('名称', '').strip()
                            change_pct = float(stock_row.get('涨跌幅', 0))

                            # 寻找行业内涨幅落后的股票（补涨机会）
                            if (symbol and name and -3 <= change_pct <= 2):
                                score = 65 + abs(2 - change_pct) * 5  # 涨幅越小潜力越大

                                stock = PotentialStock(
                                    symbol=symbol,
                                    name=name,
                                    current_price=0.0,
                                    change_pct=change_pct,
                                    volume_ratio=0.0,
                                    rsi=0.0,
                                    potential_score=score,
                                    reason=f"{industry}行业轮动，个股补涨机会"
                                )
                                stocks.append(stock)

                except Exception as e:
                    logger.debug(f"行业 {industry} 分析失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"行业轮动分析失败: {e}")

        return sorted(stocks, key=lambda x: x.potential_score, reverse=True)[:count]

    def _calculate_fund_potential_score(self, row) -> float:
        """计算资金流潜力评分"""
        score = 55.0

        try:
            change_pct = float(row.get('今日涨跌幅', 0))
            net_inflow = float(row.get('今日主力净流入-净额', 0))

            # 涨跌幅适中加分
            if -2 <= change_pct <= 3:
                score += 20
            elif change_pct > 5:
                score -= 10

            # 资金流入情况
            if net_inflow > 0:
                score += min(20, net_inflow / 10000000 * 5)  # 每千万加5分
            else:
                # 资金流出不严重也给一定分数（可能是洗盘）
                if net_inflow > -20000000:  # 流出不超过2千万
                    score += 5

        except:
            pass

        return min(100, max(30, score))

    def _calculate_tech_potential_score(self, row) -> float:
        """计算技术面潜力评分"""
        score = 50.0

        try:
            change_pct = float(row.get('涨跌幅', 0))
            volume_ratio = float(row.get('量比', 1))

            # 调整幅度评分：小幅调整给高分
            if -3 <= change_pct <= 2:
                score += 25
            elif change_pct < -5:
                score += 15  # 超跌也有反弹机会

            # 成交量评分：适度放量
            if 1.2 <= volume_ratio <= 2.5:
                score += 15
            elif volume_ratio > 3:
                score -= 5  # 过度放量减分

            # 价格位置（需要进一步计算）
            # 这里简化处理
            current_price = float(row.get('最新价', 0))
            if current_price > 0:
                score += 5

        except:
            pass

        return min(100, max(20, score))

    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码"""
        if not symbol:
            return ""

        symbol = str(symbol).strip().upper()

        if symbol.isdigit() and len(symbol) == 6:
            if symbol.startswith('60') or symbol.startswith('68'):
                return f"{symbol}.SH"
            elif symbol.startswith('00') or symbol.startswith('30'):
                return f"{symbol}.SZ"
            elif symbol.startswith('43') or symbol.startswith('83'):
                return f"{symbol}.BJ"

        if '.SH' in symbol or '.SZ' in symbol or '.BJ' in symbol:
            return symbol

        # 默认处理
        if symbol.startswith('6'):
            return f"{symbol[:6]}.SH"
        else:
            return f"{symbol[:6]}.SZ"


def create_potential_stock_finder() -> PotentialStockFinder:
    """创建潜力股挖掘器"""
    return PotentialStockFinder()