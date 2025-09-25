# -*- coding: utf-8 -*-
"""
数据提供者接口定义
遵循SOLID原则的抽象接口设计
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import pandas as pd
from dataclasses import dataclass
from enum import Enum


class DataSourceType(Enum):
    """数据源类型枚举"""
    AKSHARE = "akshare"
    TUSHARE = "tushare"
    YFINANCE = "yfinance"


class TimeFrame(Enum):
    """时间框架枚举"""
    MINUTE_1 = "1min"
    MINUTE_5 = "5min"
    MINUTE_15 = "15min"
    MINUTE_30 = "30min"
    HOUR_1 = "1h"
    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1M"


@dataclass
class DataRequest:
    """数据请求对象"""
    symbol: str
    timeframe: TimeFrame
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    period: Optional[str] = None
    limit: Optional[int] = None


@dataclass
class StockInfo:
    """标准化股票信息"""
    symbol: str
    name: str = ""
    industry: str = ""
    market_cap: float = 0.0
    pe_ratio: float = 0.0
    pb_ratio: float = 0.0
    shares_outstanding: int = 0
    region: str = ""
    list_date: str = ""
    additional_data: Dict = None

    def __post_init__(self):
        if self.additional_data is None:
            self.additional_data = {}


@dataclass
class DataSourceInfo:
    """数据源信息"""
    source_type: DataSourceType
    name: str
    is_available: bool
    supported_timeframes: List[TimeFrame]
    rate_limit: int = 0  # 每秒请求限制
    description: str = ""


class IDataSource(ABC):
    """数据源接口"""

    @abstractmethod
    def get_info(self) -> DataSourceInfo:
        """获取数据源信息"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        pass

    @abstractmethod
    def get_data(self, request: DataRequest) -> pd.DataFrame:
        """获取股票数据"""
        pass

    @abstractmethod
    def get_stock_info(self, symbol: str) -> StockInfo:
        """获取股票基本信息"""
        pass

    @abstractmethod
    def normalize_symbol(self, symbol: str) -> Optional[str]:
        """标准化股票代码"""
        pass

    @abstractmethod
    def supports_timeframe(self, timeframe: TimeFrame) -> bool:
        """检查是否支持指定时间框架"""
        pass


class IDataSourceManager(ABC):
    """数据源管理器接口"""

    @abstractmethod
    def register_source(self, source: IDataSource) -> None:
        """注册数据源"""
        pass

    @abstractmethod
    def get_available_sources(self) -> List[DataSourceInfo]:
        """获取可用数据源列表"""
        pass

    @abstractmethod
    def set_primary_source(self, source_type: DataSourceType) -> None:
        """设置主数据源"""
        pass

    @abstractmethod
    def get_data_with_fallback(self, request: DataRequest) -> Tuple[pd.DataFrame, DataSourceType]:
        """使用故障转移获取数据"""
        pass


class IIndicatorCalculator(ABC):
    """技术指标计算器接口"""

    @abstractmethod
    def calculate_indicators(self, data: pd.DataFrame, stock_info: StockInfo = None) -> Dict:
        """计算技术指标"""
        pass

    @abstractmethod
    def get_supported_indicators(self) -> List[str]:
        """获取支持的指标列表"""
        pass


class IDataProvider(ABC):
    """数据提供者接口（高层接口）"""

    @abstractmethod
    def get_stock_data(
        self,
        symbol: str,
        timeframe: TimeFrame = TimeFrame.DAILY,
        start_date: str = None,
        end_date: str = None,
        period: str = "1y"
    ) -> pd.DataFrame:
        """获取股票数据"""
        pass

    @abstractmethod
    def get_complete_stock_data(
        self,
        symbol: str,
        timeframe: TimeFrame = TimeFrame.DAILY,
        start_date: str = None,
        end_date: str = None,
        period: str = "1y"
    ) -> Tuple[pd.DataFrame, StockInfo, Dict, Dict]:
        """获取完整股票数据（数据+信息+指标+价格信息）"""
        pass

    @abstractmethod
    def get_stock_info(self, symbol: str) -> StockInfo:
        """获取股票基本信息"""
        pass


class DataSourceException(Exception):
    """数据源异常基类"""
    def __init__(self, message: str, source_type: DataSourceType = None):
        super().__init__(message)
        self.source_type = source_type


class DataSourceUnavailableException(DataSourceException):
    """数据源不可用异常"""
    pass


class DataNotFoundException(DataSourceException):
    """数据未找到异常"""
    pass


class RateLimitException(DataSourceException):
    """请求频率限制异常"""
    pass


class InvalidSymbolException(DataSourceException):
    """无效股票代码异常"""
    pass