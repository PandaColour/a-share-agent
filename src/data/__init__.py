# -*- coding: utf-8 -*-
"""
重构后的数据提供模块
遵循SOLID原则的模块化设计
"""

# 新架构的主要组件
from .unified_data_provider import UnifiedDataProvider
from .interfaces import (
    IDataSource, IDataProvider, IDataSourceManager, IIndicatorCalculator,
    DataSourceType, TimeFrame, DataRequest, StockInfo, DataSourceInfo
)
from .source_manager import DataSourceManager
from .source_factory import DataSourceFactory
from .indicators import TechnicalIndicatorCalculator

# 向后兼容性别名
from .data_provider import AShareDataProvider  # 旧的实现
from .multi_source_data_provider import MultiSourceDataProvider  # 旧的多源实现

# 默认数据提供者 - 推荐使用新架构
DataProvider = UnifiedDataProvider

__all__ = [
    # 新架构组件
    'UnifiedDataProvider',
    'DataSourceManager',
    'DataSourceFactory',
    'TechnicalIndicatorCalculator',

    # 接口和类型
    'IDataSource',
    'IDataProvider',
    'IDataSourceManager',
    'IIndicatorCalculator',
    'DataSourceType',
    'TimeFrame',
    'DataRequest',
    'StockInfo',
    'DataSourceInfo',

    # 向后兼容
    'AShareDataProvider',
    'MultiSourceDataProvider',
    'DataProvider',
]

# 版本信息
__version__ = "2.0.0"
__description__ = "重构后的数据提供模块，采用SOLID原则设计"
