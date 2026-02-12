# -*- coding: utf-8 -*-
"""
Qlib数据源实现
支持日线和5分钟数据，使用Qlib的高性能本地存储（.bin格式）
"""

import pandas as pd
import numpy as np
from typing import Optional, List
import logging
import re
import os
from datetime import datetime, timedelta

try:
    from ..interfaces import (
        IDataSource, DataRequest, DataSourceInfo, DataSourceType,
        TimeFrame, StockInfo, DataNotFoundException, InvalidSymbolException
    )
    from .base_source import BaseDataSource
except ImportError:
    from data.interfaces import (
        IDataSource, DataRequest, DataSourceInfo, DataSourceType,
        TimeFrame, StockInfo, DataNotFoundException, InvalidSymbolException
    )
    from data.sources.base_source import BaseDataSource

logger = logging.getLogger(__name__)


class QlibDataProvider(BaseDataSource):
    """Qlib数据源提供者（支持日线和5分钟数据）"""

    def __init__(self, qlib_dir: str = "./qlib_data", config: dict = None):
        """
        初始化Qlib数据源

        Args:
            qlib_dir: Qlib数据目录路径
            config: 配置字典
        """
        super().__init__(config)
        self.qlib_dir = qlib_dir
        self.initialized = False
        self._qlib_instance = None

        # 尝试初始化Qlib
        self._initialize()

    def _initialize(self):
        """初始化Qlib"""
        if self.initialized:
            return

        try:
            import qlib
            from qlib.data import D

            # 检查数据目录是否存在
            if not os.path.exists(self.qlib_dir):
                logger.warning(f"Qlib数据目录不存在: {self.qlib_dir}")
                raise DataNotFoundException(f"Qlib数据目录不存在: {self.qlib_dir}")

            # 初始化Qlib
            qlib.init(
                provider_uri=self.qlib_dir,
                region='cn',
                expression_cache=None,  # 禁用表达式缓存避免内存问题
                dataset_cache=None,  # 禁用数据集缓存
            )

            self._qlib_instance = D
            self.initialized = True
            logger.info(f"Qlib数据源初始化成功: {self.qlib_dir}")

        except ImportError as e:
            logger.error(f"Qlib未安装: {e}")
            raise ImportError("Qlib library not installed. Install with: pip install qlib")
        except Exception as e:
            logger.error(f"Qlib初始化失败: {e}")
            raise

    def get_info(self) -> DataSourceInfo:
        """获取数据源信息"""
        return DataSourceInfo(
            source_type=DataSourceType.QLIB,
            name="Qlib",
            is_available=self.is_available(),
            supported_timeframes=[TimeFrame.DAILY, TimeFrame.MINUTE_5],
            rate_limit=0,  # 本地数据，无速率限制
            description="Qlib本地高性能数据源（.bin格式），支持日线和5分钟数据"
        )

    def is_available(self) -> bool:
        """检查Qlib数据源是否可用"""
        return self.initialized

    def normalize_symbol(self, symbol: str) -> Optional[str]:
        """
        标准化股票代码：000001.SZ → SZ000001（Qlib格式）

        Args:
            symbol: 标准股票代码（如 000001.SZ, 600519.SH）

        Returns:
            Qlib格式股票代码（如 SZ000001, SH600519）
        """
        if not symbol:
            return None

        symbol = symbol.strip().upper()

        # 提取代码和市场
        match = re.match(r'(\d{6})\.(SZ|SH)', symbol)
        if not match:
            logger.warning(f"无效的股票代码格式: {symbol}")
            return None

        code, market = match.groups()

        # 转换为Qlib格式：市场+代码
        qlib_symbol = f"{market}{code}"
        return qlib_symbol

    def _to_standard_symbol(self, qlib_symbol: str) -> str:
        """
        Qlib格式转标准格式：SZ000001 → 000001.SZ

        Args:
            qlib_symbol: Qlib格式股票代码

        Returns:
            标准股票代码
        """
        match = re.match(r'(SZ|SH)(\d{6})', qlib_symbol)
        if not match:
            return qlib_symbol

        market, code = match.groups()
        return f"{code}.{market}"

    def supports_timeframe(self, timeframe: TimeFrame) -> bool:
        """检查是否支持指定时间框架"""
        return timeframe in [TimeFrame.DAILY, TimeFrame.MINUTE_5]

    def _get_daily_data(self, request: DataRequest) -> pd.DataFrame:
        """获取日线数据"""
        return self._get_qlib_data(request, freq='day')

    def _get_minute_data(self, request: DataRequest) -> pd.DataFrame:
        """获取分钟数据"""
        if request.timeframe == TimeFrame.MINUTE_5:
            return self._get_qlib_data(request, freq='5min')
        else:
            raise ValueError(f"不支持的分钟级时间框架: {request.timeframe}")

    def _get_qlib_data(self, request: DataRequest, freq: str) -> pd.DataFrame:
        """
        从Qlib获取数据

        Args:
            request: 数据请求对象
            freq: 时间频率（'day' 或 '5min'）

        Returns:
            标准化的DataFrame
        """
        if not self.initialized:
            raise DataNotFoundException("Qlib数据源未初始化")

        # 标准化股票代码
        qlib_symbol = self.normalize_symbol(request.symbol)
        if not qlib_symbol:
            raise InvalidSymbolException(f"无效的股票代码: {request.symbol}")

        # 确定日期范围
        if request.start_date and request.end_date:
            start_date = request.start_date
            end_date = request.end_date
        elif request.period:
            start_date, end_date = self._convert_period_to_dates(request.period)
        else:
            # 默认1年数据
            start_date, end_date = self._convert_period_to_dates("1y")

        # 转换日期格式为YYYY-MM-DD
        start_date = self._convert_date_format(start_date, 'YYYY-MM-DD')
        end_date = self._convert_date_format(end_date, 'YYYY-MM-DD')

        try:
            # 使用Qlib的D.features接口批量获取数据
            fields = ['$open', '$high', '$low', '$close', '$volume']

            data = self._qlib_instance.features(
                instruments=[qlib_symbol],
                fields=fields,
                start_time=start_date,
                end_time=end_date,
                freq=freq
            )

            if data is None or data.empty:
                logger.warning(f"Qlib未返回数据: {request.symbol}, freq={freq}")
                return pd.DataFrame()

            # 提取该股票的数据（去掉MultiIndex的第一层）
            if isinstance(data.index, pd.MultiIndex):
                data = data.xs(qlib_symbol, level=0)

            # 重命名列为标准格式
            data.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

            # 标准化数据格式
            data = self._standardize_data_format(data, request.symbol)

            # 添加元数据
            data.attrs['source'] = 'qlib'
            data.attrs['symbol'] = request.symbol
            data.attrs['timeframe'] = freq

            logger.debug(f"Qlib获取数据成功: {request.symbol}, freq={freq}, records={len(data)}")
            return data

        except Exception as e:
            logger.error(f"Qlib获取数据失败 {request.symbol}: {e}")
            raise DataNotFoundException(f"Qlib获取数据失败: {e}")

    def get_stock_info(self, symbol: str) -> StockInfo:
        """获取股票基本信息（Qlib版本简化）"""
        # Qlib主要提供价格数据，基本信息需要从其他源获取
        # 这里返回基础信息
        return StockInfo(
            symbol=symbol,
            name="",
            industry="",
            market_cap=0.0,
            additional_data={'source': 'qlib'}
        )
