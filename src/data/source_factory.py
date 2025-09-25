# -*- coding: utf-8 -*-
"""
数据源工厂实现
负责创建和配置各种数据源
"""

import logging
from typing import Dict, Any, Optional
from .interfaces import IDataSource, DataSourceType, DataSourceUnavailableException

logger = logging.getLogger(__name__)


class DataSourceFactory:
    """数据源工厂"""

    @staticmethod
    def create_source(source_type: DataSourceType, config: Dict[str, Any] = None) -> IDataSource:
        """
        创建数据源实例

        Args:
            source_type: 数据源类型
            config: 配置参数

        Returns:
            数据源实例

        Raises:
            DataSourceUnavailableException: 当数据源无法创建时
        """
        if config is None:
            config = {}

        try:
            if source_type == DataSourceType.AKSHARE:
                return DataSourceFactory._create_akshare_source(config)
            elif source_type == DataSourceType.TUSHARE:
                return DataSourceFactory._create_tushare_source(config)
            elif source_type == DataSourceType.YFINANCE:
                return DataSourceFactory._create_yfinance_source(config)
            else:
                raise ValueError(f"不支持的数据源类型: {source_type.value}")

        except Exception as e:
            logger.error(f"创建数据源失败 {source_type.value}: {e}")
            raise DataSourceUnavailableException(f"无法创建数据源 {source_type.value}: {e}", source_type)

    @staticmethod
    def _create_akshare_source(config: Dict[str, Any]) -> IDataSource:
        """创建AkShare数据源"""
        from .sources.akshare_source import AkShareSource
        return AkShareSource(config)

    @staticmethod
    def _create_tushare_source(config: Dict[str, Any]) -> IDataSource:
        """创建Tushare数据源"""
        from .sources.tushare_source import TushareSource

        token = config.get('token')
        if not token:
            raise ValueError("Tushare数据源需要token配置")

        return TushareSource(token, config)

    @staticmethod
    def _create_yfinance_source(config: Dict[str, Any]) -> IDataSource:
        """创建YFinance数据源"""
        from .sources.yfinance_source import YFinanceSource
        return YFinanceSource(config)

    @staticmethod
    def create_from_config(data_sources_config: Dict[str, Any]) -> Dict[DataSourceType, IDataSource]:
        """
        从配置创建多个数据源

        Args:
            data_sources_config: 数据源配置字典

        Returns:
            数据源实例字典
        """
        sources = {}

        for source_name, source_config in data_sources_config.items():
            if not source_config.get('enabled', False):
                logger.debug(f"数据源 {source_name} 未启用，跳过创建")
                continue

            try:
                source_type = DataSourceType(source_name.lower())
                source = DataSourceFactory.create_source(source_type, source_config)
                sources[source_type] = source
                logger.info(f"✅ 数据源 {source_name} 创建成功")
            except ValueError:
                logger.warning(f"⚠️ 未知数据源类型: {source_name}")
            except DataSourceUnavailableException as e:
                logger.error(f"❌ 数据源 {source_name} 创建失败: {e}")

        return sources

    @staticmethod
    def get_available_source_types() -> list[DataSourceType]:
        """获取所有可用的数据源类型"""
        return list(DataSourceType)

    @staticmethod
    def validate_config(source_type: DataSourceType, config: Dict[str, Any]) -> bool:
        """
        验证数据源配置

        Args:
            source_type: 数据源类型
            config: 配置参数

        Returns:
            配置是否有效
        """
        try:
            if source_type == DataSourceType.TUSHARE:
                return bool(config.get('token'))
            elif source_type in [DataSourceType.AKSHARE, DataSourceType.YFINANCE]:
                return True  # 这些数据源不需要特殊配置
            else:
                return False
        except Exception:
            return False