# -*- coding: utf-8 -*-
"""
数据源基础类
提供通用的数据处理和错误处理逻辑
"""

import re
import logging
from abc import ABC
from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime, timedelta

try:
    from ..interfaces import (
        IDataSource, DataRequest, DataSourceInfo, DataSourceType,
        TimeFrame, StockInfo, InvalidSymbolException, DataNotFoundException
    )
except ImportError:
    from data.interfaces import (
        IDataSource, DataRequest, DataSourceInfo, DataSourceType,
        TimeFrame, StockInfo, InvalidSymbolException, DataNotFoundException
    )

logger = logging.getLogger(__name__)


class BaseDataSource(IDataSource, ABC):
    """数据源基础类"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self._is_initialized = False
        self._initialization_error = None

    def is_available(self) -> bool:
        """检查数据源是否可用"""
        if not self._is_initialized:
            try:
                self._initialize()
                self._is_initialized = True
                self._initialization_error = None
                return True
            except Exception as e:
                self._initialization_error = e
                logger.error(f"数据源初始化失败: {e}")
                return False
        return self._initialization_error is None

    def _initialize(self):
        """子类实现具体的初始化逻辑"""
        pass

    def get_data(self, request: DataRequest) -> pd.DataFrame:
        """获取股票数据"""
        if not self.is_available():
            raise DataNotFoundException(f"数据源不可用: {self._initialization_error}")

        # 验证请求参数
        self._validate_request(request)

        try:
            # 根据时间框架选择合适的方法
            if request.timeframe == TimeFrame.DAILY:
                return self._get_daily_data(request)
            elif request.timeframe in [TimeFrame.MINUTE_1, TimeFrame.MINUTE_5,
                                     TimeFrame.MINUTE_15, TimeFrame.MINUTE_30]:
                return self._get_minute_data(request)
            else:
                raise ValueError(f"不支持的时间框架: {request.timeframe}")

        except Exception as e:
            logger.error(f"获取数据失败 {request.symbol}: {e}")
            raise DataNotFoundException(f"获取数据失败: {e}")

    def _validate_request(self, request: DataRequest):
        """验证请求参数"""
        if not request.symbol:
            raise InvalidSymbolException("股票代码不能为空")

        if not self.supports_timeframe(request.timeframe):
            raise ValueError(f"不支持的时间框架: {request.timeframe}")

        # 验证日期格式
        if request.start_date:
            self._validate_date_format(request.start_date)
        if request.end_date:
            self._validate_date_format(request.end_date)

    def _validate_date_format(self, date_str: str):
        """验证日期格式"""
        try:
            if '-' in date_str:
                datetime.strptime(date_str, '%Y-%m-%d')
            else:
                datetime.strptime(date_str, '%Y%m%d')
        except ValueError:
            raise ValueError(f"无效的日期格式: {date_str}")

    def _get_daily_data(self, request: DataRequest) -> pd.DataFrame:
        """获取日线数据（子类实现）"""
        raise NotImplementedError

    def _get_minute_data(self, request: DataRequest) -> pd.DataFrame:
        """获取分钟数据（子类实现）"""
        raise NotImplementedError

    def _standardize_data_format(self, data: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """标准化数据格式"""
        if data.empty:
            return data

        # 确保有必需的列
        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_columns = [col for col in required_columns if col not in data.columns]

        if missing_columns:
            logger.warning(f"数据缺少必需列 {symbol}: {missing_columns}")

        # 确保数值类型
        for col in required_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')

        # 确保索引是时间类型
        if not isinstance(data.index, pd.DatetimeIndex):
            if 'Date' in data.columns:
                data['Date'] = pd.to_datetime(data['Date'])
                data.set_index('Date', inplace=True)
            else:
                logger.warning(f"无法设置时间索引: {symbol}")

        # 按时间排序
        data.sort_index(inplace=True)

        # 移除无效数据
        data.dropna(subset=['Close'], inplace=True)

        return data

    def normalize_symbol(self, symbol: str) -> Optional[str]:
        """标准化股票代码（基础实现）"""
        if not symbol:
            return None

        symbol = symbol.strip().upper()

        # 过滤B股
        if self._is_b_share(symbol):
            return None

        return symbol

    def _is_b_share(self, symbol: str) -> bool:
        """判断是否为B股"""
        # 提取数字部分
        code_match = re.search(r'\d{6}', symbol)
        if not code_match:
            return False

        code = code_match.group()
        # B股代码通常以20或90开头
        return code.startswith('20') or code.startswith('90')

    def _convert_period_to_dates(self, period: str) -> tuple[str, str]:
        """将period转换为开始和结束日期"""
        end_date = datetime.now()

        period_mapping = {
            "1d": 1,
            "5d": 5,
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
            "2y": 730,
            "5y": 1825
        }

        days = period_mapping.get(period, 365)
        start_date = end_date - timedelta(days=days)

        return start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d')

    def _convert_date_format(self, date_str: str, target_format: str = 'YYYYMMDD') -> str:
        """转换日期格式"""
        if not date_str:
            return date_str

        # 检测当前格式
        if '-' in date_str:
            # YYYY-MM-DD format
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            # YYYYMMDD format
            date_obj = datetime.strptime(date_str, '%Y%m%d')

        if target_format == 'YYYYMMDD':
            return date_obj.strftime('%Y%m%d')
        elif target_format == 'YYYY-MM-DD':
            return date_obj.strftime('%Y-%m-%d')
        else:
            raise ValueError(f"不支持的日期格式: {target_format}")

    def get_stock_info(self, symbol: str) -> StockInfo:
        """获取股票基本信息（基础实现）"""
        return StockInfo(symbol=symbol)

    def supports_timeframe(self, timeframe: TimeFrame) -> bool:
        """检查是否支持指定时间框架（基础实现）"""
        supported = self.get_info().supported_timeframes
        return timeframe in supported