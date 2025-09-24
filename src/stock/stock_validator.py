# -*- coding: utf-8 -*-
"""
股票代码验证工具
验证股票代码有效性，过滤退市股票
"""

import re
import logging
from typing import List, Dict, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class StockValidator:
    """股票代码验证器"""
    
    def __init__(self):
        # 已知的退市股票代码（可以扩展）
        self.delisted_stocks = {
            '600941.SH',  # 已退市
            '601318.SH',  # 可能有问题的代码
            # 可以添加更多已知退市股票
        }
        
        # 有效的股票代码格式
        self.valid_patterns = {
            'A股上海': re.compile(r'^60[0-9]{4}\.SH$'),      # 600xxx.SH
            'A股深圳主板': re.compile(r'^00[0-9]{4}\.SZ$'),   # 000xxx.SZ  
            'A股深圳中小板': re.compile(r'^00[2-9]{1}[0-9]{3}\.SZ$'), # 002xxx.SZ
            'A股深圳创业板': re.compile(r'^30[0-9]{4}\.SZ$'),   # 300xxx.SZ
            'A股北交所': re.compile(r'^(8[0-9]{5}|4[0-9]{5})\.BJ$'), # 8xxxxx.BJ, 4xxxxx.BJ
            '港股': re.compile(r'^[0-9]{5}$'),               # 5位数字
            'ETF基金上海': re.compile(r'^51[0-9]{4}\.SH$'),    # 510xxx.SH
            'ETF基金深圳': re.compile(r'^15[0-9]{4}\.SZ$'),    # 150xxx.SZ
        }
        
        # 特殊股票代码（指数等）
        self.special_codes = {
            '000001.SH',  # 上证指数
            '399001.SZ',  # 深证成指
            '399006.SZ',  # 创业板指
            '000300.SH',  # 沪深300
            '000905.SH',  # 中证500
            '000016.SH',  # 上证50
            '000688.SH',  # 科创50
            '510300.SH',  # 沪深300ETF
            '510050.SH',  # 上证50ETF
            '159915.SZ',  # 创业板ETF
            '159928.SZ',  # 消费ETF
            '588000.SH',  # 科创50ETF
            '510500.SH',  # 中证500ETF
            '510230.SH',  # 金融ETF
            '515000.SH',  # 科技ETF
            '510660.SH',  # 医药ETF
        }
    
    def is_valid_stock_code(self, symbol: str) -> bool:
        """检查股票代码是否有效"""
        if not symbol or not isinstance(symbol, str):
            return False
        
        symbol = symbol.strip().upper()
        
        # 检查是否在退市列表中
        if symbol in self.delisted_stocks:
            logger.debug(f"股票代码 {symbol} 在退市列表中")
            return False
        
        # 检查特殊代码
        if symbol in self.special_codes:
            return True
        
        # 检查格式是否匹配
        for market_type, pattern in self.valid_patterns.items():
            if pattern.match(symbol):
                logger.debug(f"股票代码 {symbol} 匹配 {market_type} 格式")
                return True
        
        logger.debug(f"股票代码 {symbol} 格式无效")
        return False
    
    def filter_valid_stocks(self, symbols: List[str]) -> List[str]:
        """过滤出有效的股票代码"""
        if not symbols:
            return []
        
        valid_symbols = []
        invalid_symbols = []
        
        for symbol in symbols:
            if self.is_valid_stock_code(symbol):
                valid_symbols.append(symbol)
            else:
                invalid_symbols.append(symbol)
        
        if invalid_symbols:
            logger.warning(f"发现无效股票代码: {invalid_symbols}")
        
        logger.info(f"股票代码验证: {len(symbols)}个 -> {len(valid_symbols)}个有效")
        return valid_symbols
    
    def get_market_type(self, symbol: str) -> str:
        """获取股票所属市场类型"""
        if not self.is_valid_stock_code(symbol):
            return "无效代码"
        
        symbol = symbol.strip().upper()
        
        if symbol in self.special_codes:
            return "指数/特殊代码"
        
        for market_type, pattern in self.valid_patterns.items():
            if pattern.match(symbol):
                return market_type
        
        return "未知市场"
    
    def validate_recommendations(self, recommendations: List[Dict]) -> List[Dict]:
        """验证推荐列表中的股票代码"""
        if not recommendations:
            return []
        
        valid_recommendations = []
        invalid_count = 0
        
        for rec in recommendations:
            symbol = rec.get('symbol', '')
            if self.is_valid_stock_code(symbol):
                valid_recommendations.append(rec)
            else:
                invalid_count += 1
                logger.debug(f"跳过无效股票推荐: {symbol} - {rec.get('stock_name', 'N/A')}")
        
        if invalid_count > 0:
            logger.warning(f"过滤掉 {invalid_count} 个无效股票推荐")
        
        logger.info(f"推荐验证: {len(recommendations)}个 -> {len(valid_recommendations)}个有效")
        return valid_recommendations
    
    def add_delisted_stock(self, symbol: str):
        """添加退市股票到黑名单"""
        if symbol and isinstance(symbol, str):
            self.delisted_stocks.add(symbol.strip().upper())
            logger.info(f"添加退市股票: {symbol}")
    
    def remove_delisted_stock(self, symbol: str):
        """从退市股票黑名单中移除"""
        if symbol and isinstance(symbol, str):
            symbol = symbol.strip().upper()
            if symbol in self.delisted_stocks:
                self.delisted_stocks.remove(symbol)
                logger.info(f"移除退市股票: {symbol}")
    
    def get_validation_stats(self, symbols: List[str]) -> Dict:
        """获取验证统计信息"""
        if not symbols:
            return {"total": 0, "valid": 0, "invalid": 0, "delisted": 0}
        
        stats = {
            "total": len(symbols),
            "valid": 0,
            "invalid": 0,
            "delisted": 0,
            "market_breakdown": {}
        }
        
        for symbol in symbols:
            if symbol in self.delisted_stocks:
                stats["delisted"] += 1
            elif self.is_valid_stock_code(symbol):
                stats["valid"] += 1
                market_type = self.get_market_type(symbol)
                stats["market_breakdown"][market_type] = stats["market_breakdown"].get(market_type, 0) + 1
            else:
                stats["invalid"] += 1
        
        return stats

# 创建全局验证器实例
stock_validator = StockValidator()

def validate_stock_symbol(symbol: str) -> bool:
    """快捷函数：验证单个股票代码"""
    return stock_validator.is_valid_stock_code(symbol)

def filter_valid_stock_symbols(symbols: List[str]) -> List[str]:
    """快捷函数：过滤有效股票代码"""
    return stock_validator.filter_valid_stocks(symbols)