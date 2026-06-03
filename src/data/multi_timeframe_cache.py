# -*- coding: utf-8 -*-
"""
多时间框架数据缓存管理器
提供高效的多时间框架数据缓存、LRU淘汰和内存管理
"""

import logging
import pandas as pd
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
import threading
import psutil
import os

try:
    from .interfaces import TimeFrame
except ImportError:
    from data.interfaces import TimeFrame

logger = logging.getLogger(__name__)


class CacheEntry:
    """缓存条目"""

    def __init__(self, data: pd.DataFrame, timeframe: TimeFrame, ttl: int):
        self.data = data
        self.timeframe = timeframe
        self.timestamp = datetime.now()
        self.ttl = ttl  # 生存时间（秒）
        self.access_count = 0
        self.last_access = self.timestamp

    def is_expired(self) -> bool:
        """检查是否过期"""
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl

    def update_access(self):
        """更新访问信息"""
        self.access_count += 1
        self.last_access = datetime.now()

    def get_memory_size(self) -> int:
        """获取内存大小（字节）"""
        return self.data.memory_usage(deep=True).sum()


class MultiTimeframeDataCache:
    """多时间框架数据缓存管理器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 配置参数
        self.max_symbols = self.config.get('max_symbols', 50)
        self.max_memory_mb = self.config.get('max_memory_mb', 500)
        self.eviction_policy = self.config.get('eviction_policy', 'LRU')

        # TTL配置（秒）
        self.ttl_config = {
            TimeFrame.DAILY: self.config.get('daily_ttl', 3600),      # 1小时
            TimeFrame.MINUTE_5: self.config.get('minute_5_ttl', 300),  # 5分钟
            TimeFrame.MINUTE_15: self.config.get('minute_15_ttl', 900), # 15分钟
            TimeFrame.MINUTE_30: self.config.get('minute_30_ttl', 1800), # 30分钟
            TimeFrame.HOUR_1: self.config.get('hour_1_ttl', 3600)     # 1小时
        }

        # 缓存存储 {symbol: {timeframe: CacheEntry}}
        self.cache: OrderedDict[str, Dict[TimeFrame, CacheEntry]] = OrderedDict()

        # 线程锁
        self.lock = threading.Lock()

        # 统计信息
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expired': 0
        }

        logger.info(f"多时间框架缓存初始化: 最大{self.max_symbols}只股票, {self.max_memory_mb}MB内存")

    def get(
        self,
        symbol: str,
        timeframe: TimeFrame
    ) -> Optional[pd.DataFrame]:
        """
        获取缓存数据

        Args:
            symbol: 股票代码
            timeframe: 时间框架

        Returns:
            数据DataFrame，如果未命中或过期则返回None
        """
        with self.lock:
            # 检查symbol是否存在
            if symbol not in self.cache:
                self.stats['misses'] += 1
                return None

            # 检查timeframe是否存在
            if timeframe not in self.cache[symbol]:
                self.stats['misses'] += 1
                return None

            entry = self.cache[symbol][timeframe]

            # 检查是否过期
            if entry.is_expired():
                logger.debug(f"缓存过期: {symbol} {timeframe.value}")
                del self.cache[symbol][timeframe]
                if not self.cache[symbol]:
                    del self.cache[symbol]
                self.stats['expired'] += 1
                self.stats['misses'] += 1
                return None

            # 更新访问信息
            entry.update_access()

            # LRU: 移动到末尾
            self.cache.move_to_end(symbol)

            self.stats['hits'] += 1
            logger.debug(f"缓存命中: {symbol} {timeframe.value}")

            return entry.data.copy()

    def put(
        self,
        symbol: str,
        timeframe: TimeFrame,
        data: pd.DataFrame
    ) -> bool:
        """
        存入缓存数据

        Args:
            symbol: 股票代码
            timeframe: 时间框架
            data: 数据DataFrame

        Returns:
            是否成功
        """
        if data is None or data.empty:
            logger.warning(f"尝试缓存空数据: {symbol} {timeframe.value}")
            return False

        with self.lock:
            try:
                # 获取TTL
                ttl = self.ttl_config.get(timeframe, 3600)

                # 创建缓存条目
                entry = CacheEntry(data.copy(), timeframe, ttl)

                # 检查内存限制
                if not self._check_memory_limit(entry):
                    # 尝试淘汰
                    self._evict_if_needed(entry.get_memory_size())

                # 存入缓存
                if symbol not in self.cache:
                    self.cache[symbol] = {}

                self.cache[symbol][timeframe] = entry

                # 移动到末尾（最新）
                self.cache.move_to_end(symbol)

                # 检查股票数量限制
                if len(self.cache) > self.max_symbols:
                    self._evict_oldest_symbol()

                logger.debug(f"缓存存入: {symbol} {timeframe.value}, 数据量: {len(data)}")
                return True

            except Exception as e:
                logger.error(f"缓存存入失败 {symbol} {timeframe.value}: {e}")
                return False

    def get_multi_timeframe(
        self,
        symbol: str,
        timeframes: list[TimeFrame]
    ) -> Dict[TimeFrame, Optional[pd.DataFrame]]:
        """
        获取多个时间框架的数据

        Args:
            symbol: 股票代码
            timeframes: 时间框架列表

        Returns:
            时间框架到数据的映射
        """
        result = {}

        for timeframe in timeframes:
            data = self.get(symbol, timeframe)
            result[timeframe] = data

        return result

    def put_multi_timeframe(
        self,
        symbol: str,
        data_dict: Dict[TimeFrame, pd.DataFrame]
    ) -> Dict[TimeFrame, bool]:
        """
        存入多个时间框架的数据

        Args:
            symbol: 股票代码
            data_dict: 时间框架到数据的映射

        Returns:
            时间框架到成功状态的映射
        """
        result = {}

        for timeframe, data in data_dict.items():
            success = self.put(symbol, timeframe, data)
            result[timeframe] = success

        return result

    def invalidate(self, symbol: str, timeframe: TimeFrame = None):
        """
        使缓存失效

        Args:
            symbol: 股票代码
            timeframe: 时间框架，如果为None则清空该股票所有时间框架
        """
        with self.lock:
            if symbol not in self.cache:
                return

            if timeframe is None:
                # 清空该股票所有时间框架
                del self.cache[symbol]
                logger.debug(f"清空缓存: {symbol} (所有时间框架)")
            else:
                # 清空指定时间框架
                if timeframe in self.cache[symbol]:
                    del self.cache[symbol][timeframe]
                    logger.debug(f"清空缓存: {symbol} {timeframe.value}")

                # 如果该股票没有任何时间框架数据了，删除股票
                if not self.cache[symbol]:
                    del self.cache[symbol]

    def clear(self):
        """清空所有缓存"""
        with self.lock:
            self.cache.clear()
            self.stats = {'hits': 0, 'misses': 0, 'evictions': 0, 'expired': 0}
            logger.info("缓存已清空")

    def cleanup_expired(self) -> int:
        """
        清理过期缓存

        Returns:
            清理的条目数量
        """
        with self.lock:
            expired_count = 0
            symbols_to_remove = []

            for symbol, timeframes in list(self.cache.items()):
                expired_timeframes = []

                for timeframe, entry in timeframes.items():
                    if entry.is_expired():
                        expired_timeframes.append(timeframe)
                        expired_count += 1

                # 删除过期的时间框架
                for tf in expired_timeframes:
                    del timeframes[tf]

                # 如果该股票没有任何时间框架数据了，标记删除
                if not timeframes:
                    symbols_to_remove.append(symbol)

            # 删除空股票
            for symbol in symbols_to_remove:
                del self.cache[symbol]

            if expired_count > 0:
                logger.info(f"清理过期缓存: {expired_count}个条目")

            self.stats['expired'] += expired_count

            return expired_count

    def _check_memory_limit(self, new_entry: CacheEntry) -> bool:
        """检查内存限制"""
        current_memory_mb = self.get_memory_usage_mb()
        new_entry_mb = new_entry.get_memory_size() / (1024 * 1024)

        return (current_memory_mb + new_entry_mb) <= self.max_memory_mb

    def _evict_if_needed(self, required_bytes: int):
        """如果需要则淘汰缓存"""
        max_bytes = self.max_memory_mb * 1024 * 1024
        current_bytes = self.get_memory_usage_mb() * 1024 * 1024

        while current_bytes + required_bytes > max_bytes and self.cache:
            if self.eviction_policy == 'LRU':
                self._evict_lru()
            elif self.eviction_policy == 'LFU':
                self._evict_lfu()
            else:
                self._evict_oldest()

            current_bytes = self.get_memory_usage_mb() * 1024 * 1024

    def _evict_lru(self):
        """LRU淘汰：删除最久未使用的"""
        if not self.cache:
            return

        # OrderedDict的第一个是最久未使用的
        symbol = next(iter(self.cache))
        timeframes = self.cache[symbol]

        # 找到最久未访问的时间框架
        oldest_tf = min(
            timeframes.items(),
            key=lambda x: x[1].last_access
        )[0]

        del timeframes[oldest_tf]

        if not timeframes:
            del self.cache[symbol]

        self.stats['evictions'] += 1
        logger.debug(f"LRU淘汰: {symbol} {oldest_tf.value}")

    def _evict_lfu(self):
        """LFU淘汰：删除最少使用的"""
        if not self.cache:
            return

        # 找到访问次数最少的条目
        min_access_count = float('inf')
        target_symbol = None
        target_timeframe = None

        for symbol, timeframes in self.cache.items():
            for timeframe, entry in timeframes.items():
                if entry.access_count < min_access_count:
                    min_access_count = entry.access_count
                    target_symbol = symbol
                    target_timeframe = timeframe

        if target_symbol and target_timeframe:
            del self.cache[target_symbol][target_timeframe]

            if not self.cache[target_symbol]:
                del self.cache[target_symbol]

            self.stats['evictions'] += 1
            logger.debug(f"LFU淘汰: {target_symbol} {target_timeframe.value}")

    def _evict_oldest(self):
        """删除最早的缓存"""
        if not self.cache:
            return

        # 找到最早的条目
        oldest_timestamp = datetime.max
        target_symbol = None
        target_timeframe = None

        for symbol, timeframes in self.cache.items():
            for timeframe, entry in timeframes.items():
                if entry.timestamp < oldest_timestamp:
                    oldest_timestamp = entry.timestamp
                    target_symbol = symbol
                    target_timeframe = timeframe

        if target_symbol and target_timeframe:
            del self.cache[target_symbol][target_timeframe]

            if not self.cache[target_symbol]:
                del self.cache[target_symbol]

            self.stats['evictions'] += 1
            logger.debug(f"最早淘汰: {target_symbol} {target_timeframe.value}")

    def _evict_oldest_symbol(self):
        """删除最早访问的股票（所有时间框架）"""
        if not self.cache:
            return

        # OrderedDict的第一个是最早的
        symbol = next(iter(self.cache))
        entry_count = len(self.cache[symbol])

        del self.cache[symbol]

        self.stats['evictions'] += entry_count
        logger.debug(f"删除股票缓存: {symbol} ({entry_count}个时间框架)")

    def get_memory_usage_mb(self) -> float:
        """获取当前缓存内存使用量（MB）"""
        total_bytes = 0

        for timeframes in self.cache.values():
            for entry in timeframes.values():
                total_bytes += entry.get_memory_size()

        return total_bytes / (1024 * 1024)

    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        with self.lock:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0

            # 统计每个时间框架的缓存数量
            timeframe_counts = {}
            for timeframes in self.cache.values():
                for timeframe in timeframes.keys():
                    tf_name = timeframe.value
                    timeframe_counts[tf_name] = timeframe_counts.get(tf_name, 0) + 1

            return {
                'total_symbols': len(self.cache),
                'total_entries': sum(len(tfs) for tfs in self.cache.values()),
                'hit_rate': round(hit_rate, 3),
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'evictions': self.stats['evictions'],
                'expired': self.stats['expired'],
                'memory_usage_mb': round(self.get_memory_usage_mb(), 2),
                'memory_limit_mb': self.max_memory_mb,
                'timeframe_distribution': timeframe_counts
            }

    def is_trading_hours(self) -> bool:
        """
        判断是否在交易时段

        Returns:
            是否在交易时段
        """
        now = datetime.now()
        current_time = now.time()
        weekday = now.weekday()

        # 周末不交易
        if weekday >= 5:  # 5=周六, 6=周日
            return False

        # 早盘 9:30-11:30
        morning_start = datetime.strptime("09:30", "%H:%M").time()
        morning_end = datetime.strptime("11:30", "%H:%M").time()

        # 午盘 13:00-15:00
        afternoon_start = datetime.strptime("13:00", "%H:%M").time()
        afternoon_end = datetime.strptime("15:00", "%H:%M").time()

        in_morning = morning_start <= current_time <= morning_end
        in_afternoon = afternoon_start <= current_time <= afternoon_end

        return in_morning or in_afternoon


# 全局缓存实例
_global_cache: Optional[MultiTimeframeDataCache] = None


def get_cache(config: Dict = None) -> MultiTimeframeDataCache:
    """获取全局缓存实例（单例模式）"""
    global _global_cache

    if _global_cache is None:
        _global_cache = MultiTimeframeDataCache(config)

    return _global_cache


def cleanup_cache():
    """清理全局缓存"""
    global _global_cache

    if _global_cache:
        _global_cache.clear()
        _global_cache = None
