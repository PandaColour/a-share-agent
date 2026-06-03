# -*- coding: utf-8 -*-
"""
AkShare数据源实现
"""

import logging
from typing import Dict, List, Optional
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


class AkShareSource(BaseDataSource):
    """AkShare数据源实现"""

    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.ak = None

    def _initialize(self):
        """初始化AkShare"""
        try:
            import akshare as ak
            self.ak = ak
            logger.debug("AkShare模块导入成功")
        except ImportError:
            raise ImportError("AkShare未安装，请运行: pip install akshare")

    def get_info(self) -> DataSourceInfo:
        """获取数据源信息"""
        return DataSourceInfo(
            source_type=DataSourceType.AKSHARE,
            name="AkShare数据源",
            is_available=self.is_available(),
            supported_timeframes=[
                TimeFrame.DAILY,
                TimeFrame.MINUTE_1,
                TimeFrame.MINUTE_5,
                TimeFrame.MINUTE_15,
                TimeFrame.MINUTE_30
            ],
            rate_limit=10,  # 每秒10个请求
            description="AkShare提供的免费A股数据"
        )

    def normalize_symbol(self, symbol: str) -> Optional[str]:
        """标准化股票代码为AkShare格式"""
        normalized = super().normalize_symbol(symbol)
        if normalized is None:
            return None

        # 去掉后缀，AkShare使用纯数字代码
        symbol_clean = normalized.replace('.SH', '').replace('.SS', '').replace('.SZ', '')

        # 处理前缀
        if symbol_clean.startswith('SH') or symbol_clean.startswith('SZ'):
            symbol_clean = symbol_clean[2:]

        # 验证是否为6位数字
        if not symbol_clean.isdigit() or len(symbol_clean) != 6:
            return None

        return symbol_clean

    def _get_daily_data(self, request: DataRequest) -> pd.DataFrame:
        """获取日线数据"""
        try:
            symbol = self.normalize_symbol(request.symbol)
            if symbol is None:
                raise InvalidSymbolException(f"无效股票代码: {request.symbol}")

            # 确定日期范围
            if request.start_date and request.end_date:
                start_date = self._convert_date_format(request.start_date, 'YYYYMMDD')
                end_date = self._convert_date_format(request.end_date, 'YYYYMMDD')
            else:
                start_date, end_date = self._convert_period_to_dates(request.period or "1y")

            logger.debug(f"AkShare获取日线数据: {symbol}, {start_date} - {end_date}")

            # 获取数据
            data = self.ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"  # 前复权
            )

            if data.empty:
                raise DataNotFoundException(f"AkShare未返回数据: {symbol}")

            return self._standardize_akshare_data(data, request.symbol)

        except Exception as e:
            logger.error(f"AkShare获取日线数据失败 {request.symbol}: {e}")
            raise DataNotFoundException(f"获取日线数据失败: {e}")

    def _get_minute_data(self, request: DataRequest) -> pd.DataFrame:
        """获取分钟数据"""
        try:
            symbol = self.normalize_symbol(request.symbol)
            if symbol is None:
                raise InvalidSymbolException(f"无效股票代码: {request.symbol}")

            # 转换时间框架
            period_map = {
                TimeFrame.MINUTE_1: "1",
                TimeFrame.MINUTE_5: "5",
                TimeFrame.MINUTE_15: "15",
                TimeFrame.MINUTE_30: "30"
            }

            period = period_map.get(request.timeframe, "5")

            # 默认获取最近3天的分钟数据
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)  # 多获取一些天数确保有足够交易日数据

            logger.debug(f"AkShare获取{period}分钟数据: {symbol}")

            # 获取分钟数据
            data = self.ak.stock_zh_a_hist_min_em(
                symbol=symbol,
                period=period,
                start_date=start_date.strftime('%Y-%m-%d %H:%M:%S'),
                end_date=end_date.strftime('%Y-%m-%d %H:%M:%S')
            )

            if data.empty:
                raise DataNotFoundException(f"AkShare未返回分钟数据: {symbol}")

            return self._standardize_akshare_minute_data(data, request.symbol)

        except Exception as e:
            logger.error(f"AkShare获取分钟数据失败 {request.symbol}: {e}")
            raise DataNotFoundException(f"获取分钟数据失败: {e}")

    def _standardize_akshare_data(self, data: pd.DataFrame, original_symbol: str) -> pd.DataFrame:
        """标准化AkShare日线数据格式"""
        if data.empty:
            return pd.DataFrame()

        # AkShare日线数据列名映射
        column_mapping = {
            '日期': 'Date',
            '开盘': 'Open',
            '收盘': 'Close',
            '最高': 'High',
            '最低': 'Low',
            '成交量': 'Volume',
            '成交额': 'Amount'
        }

        # 重命名列
        data = data.rename(columns=column_mapping)

        # 设置日期索引
        if 'Date' in data.columns:
            data['Date'] = pd.to_datetime(data['Date'])
            data.set_index('Date', inplace=True)

        return self._standardize_data_format(data, original_symbol)

    def _standardize_akshare_minute_data(self, data: pd.DataFrame, original_symbol: str) -> pd.DataFrame:
        """标准化AkShare分钟数据格式"""
        if data.empty:
            return pd.DataFrame()

        # AkShare分钟数据列名映射
        column_mapping = {
            '时间': 'Date',
            '开盘': 'Open',
            '收盘': 'Close',
            '最高': 'High',
            '最低': 'Low',
            '成交量': 'Volume',
            '成交额': 'Amount'
        }

        # 重命名列
        data = data.rename(columns=column_mapping)

        # 设置时间索引
        if 'Date' in data.columns:
            data['Date'] = pd.to_datetime(data['Date'])
            data.set_index('Date', inplace=True)

        return self._standardize_data_format(data, original_symbol)

    def get_stock_info(self, symbol: str) -> StockInfo:
        """获取股票基本信息"""
        try:
            ak_symbol = self.normalize_symbol(symbol)
            if ak_symbol is None:
                return StockInfo(symbol=symbol)

            # 获取股票基本信息
            info_data = self.ak.stock_individual_info_em(symbol=ak_symbol)

            if info_data is None or info_data.empty:
                return StockInfo(symbol=symbol)

            # 解析信息
            info_dict = {}
            if isinstance(info_data, pd.DataFrame):
                for _, row in info_data.iterrows():
                    if 'item' in row and 'value' in row:
                        info_dict[row['item']] = row['value']

            # 映射到标准格式
            stock_info = StockInfo(
                symbol=symbol,
                name=info_dict.get('股票简称', ''),
                industry=info_dict.get('所属行业', ''),
                market_cap=self._parse_numeric(info_dict.get('总市值', 0)),
                pe_ratio=self._parse_numeric(info_dict.get('市盈率', 0)),
                shares_outstanding=self._parse_numeric(info_dict.get('总股本', 0)),
                region=info_dict.get('所属地域', ''),
                additional_data=info_dict
            )

            return stock_info

        except Exception as e:
            logger.error(f"AkShare获取股票信息失败 {symbol}: {e}")
            return StockInfo(symbol=symbol)

    def _parse_numeric(self, value) -> float:
        """解析数值"""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                # 移除单位和特殊字符
                clean_value = value.replace('万', '').replace('亿', '').replace('-', '0')
                return float(clean_value) if clean_value else 0.0
            return 0.0
        except (ValueError, TypeError):
            return 0.0