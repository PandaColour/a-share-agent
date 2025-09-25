# -*- coding: utf-8 -*-
"""
数据源管理器实现
遵循SOLID原则，支持动态注册和故障转移
"""

import logging
from typing import Dict, List, Tuple, Optional
import pandas as pd
from .interfaces import (
    IDataSource, IDataSourceManager, DataRequest, DataSourceType,
    DataSourceInfo, TimeFrame, DataSourceUnavailableException,
    DataNotFoundException, InvalidSymbolException
)

logger = logging.getLogger(__name__)


class DataSourceManager(IDataSourceManager):
    """数据源管理器实现"""

    def __init__(self):
        self._sources: Dict[DataSourceType, IDataSource] = {}
        self._primary_source: Optional[DataSourceType] = None
        self._fallback_order: List[DataSourceType] = []

    def register_source(self, source: IDataSource) -> None:
        """注册数据源"""
        source_info = source.get_info()
        self._sources[source_info.source_type] = source

        # 如果是第一个注册的源，设为主数据源
        if self._primary_source is None:
            self._primary_source = source_info.source_type

        # 添加到故障转移列表
        if source_info.source_type not in self._fallback_order:
            self._fallback_order.append(source_info.source_type)

        logger.info(f"已注册数据源: {source_info.name} ({source_info.source_type.value})")

    def get_available_sources(self) -> List[DataSourceInfo]:
        """获取可用数据源列表"""
        return [source.get_info() for source in self._sources.values() if source.is_available()]

    def set_primary_source(self, source_type: DataSourceType) -> None:
        """设置主数据源"""
        if source_type not in self._sources:
            raise ValueError(f"数据源 {source_type.value} 未注册")

        if not self._sources[source_type].is_available():
            raise DataSourceUnavailableException(f"数据源 {source_type.value} 不可用", source_type)

        self._primary_source = source_type

        # 重新排序故障转移列表，将主数据源放在首位
        if source_type in self._fallback_order:
            self._fallback_order.remove(source_type)
        self._fallback_order.insert(0, source_type)

        logger.info(f"已设置主数据源: {source_type.value}")

    def get_data_with_fallback(self, request: DataRequest) -> Tuple[pd.DataFrame, DataSourceType]:
        """使用故障转移获取数据"""
        if not self._sources:
            raise DataSourceUnavailableException("无可用数据源")

        # 确定尝试顺序
        try_order = self._fallback_order.copy()
        if self._primary_source and self._primary_source not in try_order:
            try_order.insert(0, self._primary_source)

        last_error = None

        for source_type in try_order:
            if source_type not in self._sources:
                continue

            source = self._sources[source_type]

            # 检查数据源是否可用
            if not source.is_available():
                logger.debug(f"数据源 {source_type.value} 不可用，跳过")
                continue

            # 检查是否支持请求的时间框架
            if not source.supports_timeframe(request.timeframe):
                logger.debug(f"数据源 {source_type.value} 不支持时间框架 {request.timeframe.value}")
                continue

            # 标准化股票代码
            normalized_symbol = source.normalize_symbol(request.symbol)
            if normalized_symbol is None:
                logger.debug(f"数据源 {source_type.value} 不支持股票代码 {request.symbol}")
                continue

            # 创建新请求对象
            normalized_request = DataRequest(
                symbol=normalized_symbol,
                timeframe=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                period=request.period,
                limit=request.limit
            )

            try:
                logger.debug(f"尝试从 {source_type.value} 获取 {request.symbol} 数据")
                data = source.get_data(normalized_request)

                if data is not None and not data.empty:
                    logger.debug(f"✅ 从 {source_type.value} 成功获取数据: {len(data)} 条记录")
                    return data, source_type
                else:
                    logger.debug(f"⚠️ {source_type.value} 返回空数据")

            except InvalidSymbolException as e:
                logger.debug(f"❌ {source_type.value} 不支持股票代码: {e}")
                last_error = e
                continue
            except Exception as e:
                logger.warning(f"❌ 从 {source_type.value} 获取数据失败: {e}")
                last_error = e
                continue

        # 所有数据源都失败
        error_msg = f"所有数据源都无法获取 {request.symbol} 的数据"
        if last_error:
            error_msg += f"，最后错误: {last_error}"
        raise DataNotFoundException(error_msg)

    def get_source(self, source_type: DataSourceType) -> Optional[IDataSource]:
        """获取指定类型的数据源"""
        return self._sources.get(source_type)

    def unregister_source(self, source_type: DataSourceType) -> None:
        """注销数据源"""
        if source_type in self._sources:
            del self._sources[source_type]

        if source_type in self._fallback_order:
            self._fallback_order.remove(source_type)

        if self._primary_source == source_type:
            # 选择新的主数据源
            if self._fallback_order:
                self._primary_source = self._fallback_order[0]
            else:
                self._primary_source = None

        logger.info(f"已注销数据源: {source_type.value}")

    def set_fallback_order(self, order: List[DataSourceType]) -> None:
        """设置故障转移顺序"""
        # 验证所有数据源都已注册
        for source_type in order:
            if source_type not in self._sources:
                raise ValueError(f"数据源 {source_type.value} 未注册")

        self._fallback_order = order.copy()
        logger.info(f"已设置故障转移顺序: {[st.value for st in order]}")

    def get_stats(self) -> Dict:
        """获取数据源统计信息"""
        stats = {
            "total_sources": len(self._sources),
            "available_sources": len(self.get_available_sources()),
            "primary_source": self._primary_source.value if self._primary_source else None,
            "fallback_order": [st.value for st in self._fallback_order],
            "sources": {}
        }

        for source_type, source in self._sources.items():
            source_info = source.get_info()
            stats["sources"][source_type.value] = {
                "name": source_info.name,
                "available": source_info.is_available,
                "supported_timeframes": [tf.value for tf in source_info.supported_timeframes],
                "rate_limit": source_info.rate_limit
            }

        return stats