# -*- coding: utf-8 -*-
"""
YFinance数据源实现
"""

import logging
from typing import Dict, Optional
import pandas as pd

try:
    from ..interfaces import (
        DataRequest, DataSourceInfo, DataSourceType, TimeFrame, StockInfo,
        InvalidSymbolException, DataNotFoundException
    )
except ImportError:
    from data.interfaces import (
        DataRequest, DataSourceInfo, DataSourceType, TimeFrame, StockInfo,
        InvalidSymbolException, DataNotFoundException
    )
from .base_source import BaseDataSource

logger = logging.getLogger(__name__)


class YFinanceSource(BaseDataSource):
    """YFinance数据源实现"""

    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.yf = None

    def _initialize(self):
        """初始化YFinance"""
        try:
            import yfinance as yf
            self.yf = yf
            logger.debug("YFinance模块导入成功")
        except ImportError:
            raise ImportError("yfinance未安装，请运行: pip install yfinance")

    def get_info(self) -> DataSourceInfo:
        """获取数据源信息"""
        return DataSourceInfo(
            source_type=DataSourceType.YFINANCE,
            name="YFinance数据源",
            is_available=self.is_available(),
            supported_timeframes=[
                TimeFrame.DAILY,
                TimeFrame.MINUTE_1,
                TimeFrame.MINUTE_5,
                TimeFrame.MINUTE_15,
                TimeFrame.MINUTE_30,
                TimeFrame.HOUR_1
            ],
            rate_limit=1,  # YFinance相对较慢
            description="Yahoo Finance提供的全球股票数据"
        )

    def normalize_symbol(self, symbol: str) -> Optional[str]:
        """标准化股票代码为YFinance格式"""
        normalized = super().normalize_symbol(symbol)
        if normalized is None:
            return None

        # YFinance格式: 600519.SS (上海), 000001.SZ (深圳)
        # 处理混合格式
        if symbol.startswith('SH') and symbol.endswith('.SZ'):
            code_part = symbol[2:8]
            if code_part.isdigit():
                return f"{code_part}.SS"
        elif symbol.startswith('SZ') and symbol.endswith('.SS'):
            code_part = symbol[2:8]
            if code_part.isdigit():
                return f"{code_part}.SZ"

        # 处理.SH后缀（Tushare格式）
        if symbol.endswith('.SH'):
            return symbol.replace('.SH', '.SS')

        # 处理带前缀但无后缀的情况
        if symbol.startswith('SH') and '.' not in symbol:
            code_part = symbol[2:]
            if code_part.isdigit() and len(code_part) == 6:
                return f"{code_part}.SS"
        elif symbol.startswith('SZ') and '.' not in symbol:
            code_part = symbol[2:]
            if code_part.isdigit() and len(code_part) == 6:
                return f"{code_part}.SZ"

        # 如果是纯数字，需要判断交易所
        if symbol.isdigit() and len(symbol) == 6:
            if symbol.startswith('6'):
                return f"{symbol}.SS"  # 上海
            elif symbol.startswith(('0', '3')):
                return f"{symbol}.SZ"  # 深圳

        return normalized

    def _get_daily_data(self, request: DataRequest) -> pd.DataFrame:
        """获取日线数据"""
        try:
            symbol = self.normalize_symbol(request.symbol)
            if symbol is None:
                raise InvalidSymbolException(f"无效股票代码: {request.symbol}")

            ticker = self.yf.Ticker(symbol)

            # 根据请求类型获取数据
            if request.start_date and request.end_date:
                start_date = self._convert_date_format(request.start_date, 'YYYY-MM-DD')
                end_date = self._convert_date_format(request.end_date, 'YYYY-MM-DD')
                data = ticker.history(start=start_date, end=end_date)
            else:
                period = request.period or "1y"
                data = ticker.history(period=period)

            if data.empty:
                raise DataNotFoundException(f"YFinance未返回数据: {symbol}")

            logger.debug(f"YFinance获取日线数据成功: {symbol}, {len(data)} 条记录")
            return self._standardize_data_format(data, request.symbol)

        except Exception as e:
            logger.error(f"YFinance获取日线数据失败 {request.symbol}: {e}")
            raise DataNotFoundException(f"获取日线数据失败: {e}")

    def _get_minute_data(self, request: DataRequest) -> pd.DataFrame:
        """获取分钟数据"""
        try:
            symbol = self.normalize_symbol(request.symbol)
            if symbol is None:
                raise InvalidSymbolException(f"无效股票代码: {request.symbol}")

            ticker = self.yf.Ticker(symbol)

            # 转换时间框架
            period_map = {
                TimeFrame.MINUTE_1: "1m",
                TimeFrame.MINUTE_5: "5m",
                TimeFrame.MINUTE_15: "15m",
                TimeFrame.MINUTE_30: "30m",
                TimeFrame.HOUR_1: "1h"
            }

            interval = period_map.get(request.timeframe, "5m")
            period = "7d"  # YFinance分钟数据通常限制在7天内

            logger.debug(f"YFinance获取{interval}数据: {symbol}")

            data = ticker.history(period=period, interval=interval)

            if data.empty:
                raise DataNotFoundException(f"YFinance未返回分钟数据: {symbol}")

            logger.debug(f"YFinance获取分钟数据成功: {symbol}, {len(data)} 条记录")
            return self._standardize_data_format(data, request.symbol)

        except Exception as e:
            logger.error(f"YFinance获取分钟数据失败 {request.symbol}: {e}")
            raise DataNotFoundException(f"获取分钟数据失败: {e}")

    def get_stock_info(self, symbol: str) -> StockInfo:
        """获取股票基本信息"""
        try:
            yf_symbol = self.normalize_symbol(symbol)
            if yf_symbol is None:
                return StockInfo(symbol=symbol)

            ticker = self.yf.Ticker(yf_symbol)
            info = ticker.info

            if not info:
                return StockInfo(symbol=symbol)

            stock_info = StockInfo(
                symbol=symbol,
                name=info.get('longName', info.get('shortName', '')),
                industry=info.get('industry', ''),
                market_cap=info.get('marketCap', 0),
                pe_ratio=info.get('trailingPE', 0),
                pb_ratio=info.get('priceToBook', 0),
                shares_outstanding=info.get('sharesOutstanding', 0),
                region=info.get('country', ''),
                additional_data=info
            )

            return stock_info

        except Exception as e:
            logger.error(f"YFinance获取股票信息失败 {symbol}: {e}")
            return StockInfo(symbol=symbol)