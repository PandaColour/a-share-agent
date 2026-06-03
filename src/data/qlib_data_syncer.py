# -*- coding: utf-8 -*-
"""
Qlib数据同步器
从AkShare/Tushare同步股票数据到Qlib本地存储（.bin格式）
支持全量同步和增量同步，支持日线和5分钟数据
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
import logging
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time

logger = logging.getLogger(__name__)


class QlibDataSyncer:
    """Qlib数据同步器（支持多时间框架并发同步）"""

    def __init__(self, qlib_dir: str, source_provider=None):
        """
        初始化Qlib数据同步器

        Args:
            qlib_dir: Qlib数据目录路径
            source_provider: 源数据提供者（MultiSourceDataProvider实例）
        """
        self.qlib_dir = Path(qlib_dir)
        self.source_provider = source_provider

        # 如果未提供source_provider，尝试创建默认的
        if self.source_provider is None:
            from src.data.multi_source_data_provider import MultiSourceDataProvider
            self.source_provider = MultiSourceDataProvider()

        # 确保目录存在
        self.qlib_dir.mkdir(parents=True, exist_ok=True)

        # 统计信息
        self.sync_stats = {
            'total_symbols': 0,
            'success_symbols': 0,
            'failed_symbols': 0,
            'total_records': 0,
            'failed_list': []
        }

        logger.info(f"QlibDataSyncer initialized: {qlib_dir}")

    def sync_stock_list(
        self,
        symbols: List[str] = None,
        full_sync: bool = False,
        timeframes: List[str] = ['daily', '5min'],
        max_workers: int = 8,
        start_date: str = None,
        end_date: str = None
    ) -> Dict:
        """
        批量同步股票数据

        Args:
            symbols: 股票列表（None则同步沪深300成分股）
            full_sync: True=全量同步（3-5年），False=增量同步（最近30天）
            timeframes: 要同步的时间框架列表 ['daily', '5min']
            max_workers: 并发线程数
            start_date: 开始日期（YYYYMMDD），覆盖full_sync
            end_date: 结束日期（YYYYMMDD）

        Returns:
            同步统计信息
        """
        logger.info(f"开始同步数据: timeframes={timeframes}, full_sync={full_sync}, workers={max_workers}")

        # 确定股票列表
        if symbols is None:
            symbols = self._get_default_stock_list()

        # 确定日期范围
        if start_date is None or end_date is None:
            if full_sync:
                # 全量同步：最近3年数据
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=3*365)
            else:
                # 增量同步：最近30天
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=30)

            start_date = start_dt.strftime('%Y%m%d')
            end_date = end_dt.strftime('%Y%m%d')

        logger.info(f"日期范围: {start_date} 到 {end_date}")
        logger.info(f"股票数量: {len(symbols)}")

        # 重置统计信息
        self.sync_stats = {
            'total_symbols': len(symbols),
            'success_symbols': 0,
            'failed_symbols': 0,
            'total_records': 0,
            'failed_list': []
        }

        # 生成同步任务：股票 × 时间框架
        tasks = []
        for symbol in symbols:
            for timeframe in timeframes:
                tasks.append((symbol, timeframe, start_date, end_date))

        logger.info(f"生成同步任务: {len(tasks)}个（{len(symbols)}只股票 × {len(timeframes)}个时间框架）")

        # 并发同步
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self._sync_single_stock,
                    symbol, timeframe, start_date, end_date
                ): (symbol, timeframe)
                for symbol, timeframe, start_date, end_date in tasks
            }

            completed = 0
            for future in as_completed(futures):
                symbol, timeframe = futures[future]
                completed += 1

                try:
                    success, record_count = future.result()

                    if success:
                        self.sync_stats['success_symbols'] += 1
                        self.sync_stats['total_records'] += record_count
                        logger.debug(f"[{completed}/{len(tasks)}] {symbol} {timeframe}: {record_count}条记录")
                    else:
                        self.sync_stats['failed_symbols'] += 1
                        self.sync_stats['failed_list'].append((symbol, timeframe))
                        logger.warning(f"[{completed}/{len(tasks)}] {symbol} {timeframe}: 同步失败")

                except Exception as e:
                    self.sync_stats['failed_symbols'] += 1
                    self.sync_stats['failed_list'].append((symbol, timeframe))
                    logger.error(f"[{completed}/{len(tasks)}] {symbol} {timeframe}: 异常 - {e}")

                # 每10个任务打印进度
                if completed % 10 == 0:
                    elapsed = time.time() - start_time
                    progress = (completed / len(tasks)) * 100
                    logger.info(f"进度: {completed}/{len(tasks)} ({progress:.1f}%), 耗时: {elapsed:.1f}秒")

        # 生成Qlib元数据
        self._generate_qlib_metadata(symbols, timeframes)

        elapsed_time = time.time() - start_time
        logger.info(f"同步完成: {self.sync_stats['success_symbols']}/{len(tasks)}个任务成功, 耗时: {elapsed_time:.1f}秒")

        return self.sync_stats

    def _sync_single_stock(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str
    ) -> Tuple[bool, int]:
        """
        同步单只股票的单个时间框架

        Args:
            symbol: 股票代码（标准格式：000001.SZ）
            timeframe: 时间框架（'daily' 或 '5min'）
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）

        Returns:
            (成功标志, 记录数量)
        """
        try:
            # 转换日期格式为YYYY-MM-DD
            start_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            end_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

            # 从源数据提供者获取数据
            if timeframe == 'daily':
                # 日线数据：使用现有的get_stock_data方法
                data = self.source_provider.get_stock_data(
                    symbol=symbol,
                    start_date=start_fmt,
                    end_date=end_fmt
                )
            elif timeframe == '5min':
                # 5分钟数据暂不支持（需要扩展MultiSourceDataProvider）
                logger.warning(f"{symbol}: 5分钟数据暂不支持（需要扩展数据源接口）")
                return False, 0
            else:
                logger.warning(f"不支持的时间框架: {timeframe}")
                return False, 0

            if data is None or data.empty:
                logger.debug(f"{symbol} {timeframe}: 无数据返回")
                return False, 0

            # 写入Qlib格式
            record_count = len(data)
            self._write_to_qlib(symbol, data, timeframe)

            return True, record_count

        except Exception as e:
            logger.error(f"同步{symbol} {timeframe}失败: {e}")
            return False, 0

    def _write_to_qlib(self, symbol: str, data: pd.DataFrame, timeframe: str):
        """
        将数据写入Qlib .bin格式

        Args:
            symbol: 股票代码（标准格式）
            data: 股票数据（包含Open, High, Low, Close, Volume）
            timeframe: 时间框架（'daily' 或 '5min'）
        """
        # 转换股票代码格式：000001.SZ → SZ000001
        qlib_symbol = self._to_qlib_symbol(symbol)

        # 确定频率目录
        freq_dir = 'day' if timeframe == 'daily' else '5min'

        # 创建股票特征目录
        feature_dir = self.qlib_dir / "features" / freq_dir / qlib_symbol
        feature_dir.mkdir(parents=True, exist_ok=True)

        # 写入每个特征为单独的.bin文件
        feature_map = {
            'Open': '$open',
            'High': '$high',
            'Low': '$low',
            'Close': '$close',
            'Volume': '$volume'
        }

        for col_name, feature_name in feature_map.items():
            if col_name in data.columns:
                values = data[col_name].values.astype(np.float32)

                # 写入.bin文件
                bin_path = feature_dir / f"{feature_name}.bin"
                values.tofile(str(bin_path))

        # 写入日期索引（可选，用于验证）
        date_file = feature_dir / "dates.txt"
        with open(date_file, 'w') as f:
            for dt in data.index:
                f.write(dt.strftime('%Y-%m-%d %H:%M:%S') + '\n')

        logger.debug(f"写入Qlib数据: {qlib_symbol} {timeframe} ({len(data)}条记录)")

    def _to_qlib_symbol(self, symbol: str) -> str:
        """标准格式转Qlib格式：000001.SZ → SZ000001"""
        import re
        match = re.match(r'(\d{6})\.(SZ|SH)', symbol)
        if not match:
            return symbol
        code, market = match.groups()
        return f"{market}{code}"

    def _generate_qlib_metadata(self, symbols: List[str], timeframes: List[str]):
        """
        生成Qlib元数据文件

        Args:
            symbols: 股票列表
            timeframes: 时间框架列表
        """
        # 生成instruments文件（股票列表）
        instruments_dir = self.qlib_dir / "instruments"
        instruments_dir.mkdir(parents=True, exist_ok=True)

        instruments_file = instruments_dir / "all.txt"
        with open(instruments_file, 'w') as f:
            for symbol in symbols:
                qlib_symbol = self._to_qlib_symbol(symbol)
                # 格式：股票代码 开始日期 结束日期
                f.write(f"{qlib_symbol}\t2020-01-01\t2030-12-31\n")

        logger.info(f"生成instruments文件: {instruments_file} ({len(symbols)}只股票)")

        # 生成calendars文件（交易日历，简化版）
        calendars_dir = self.qlib_dir / "calendars"
        calendars_dir.mkdir(parents=True, exist_ok=True)

        # 日线交易日历
        if 'daily' in timeframes:
            day_calendar = calendars_dir / "day.txt"
            self._generate_calendar_file(day_calendar, freq='D')

        # 5分钟交易日历
        if '5min' in timeframes:
            min5_calendar = calendars_dir / "5min.txt"
            self._generate_calendar_file(min5_calendar, freq='5min')

    def _generate_calendar_file(self, calendar_file: Path, freq: str = 'D'):
        """
        生成交易日历文件

        Args:
            calendar_file: 日历文件路径
            freq: 频率（'D'为日线，'5min'为5分钟）
        """
        # 生成最近3年的交易日
        end_date = datetime.now()
        start_date = end_date - timedelta(days=3*365)

        dates = pd.date_range(start=start_date, end=end_date, freq='B')  # 工作日

        with open(calendar_file, 'w') as f:
            for dt in dates:
                if freq == 'D':
                    f.write(dt.strftime('%Y-%m-%d') + '\n')
                elif freq == '5min':
                    # 5分钟：生成交易时段的时间点
                    # 上午：9:30-11:30
                    for hour in [9, 10, 11]:
                        for minute in range(0, 60, 5):
                            time_str = f"{hour:02d}:{minute:02d}:00"
                            # 跳过9:00-9:30（开盘前）和11:30之后
                            if (hour == 9 and minute < 30) or (hour == 11 and minute >= 30):
                                continue
                            f.write(dt.strftime('%Y-%m-%d') + ' ' + time_str + '\n')

                    # 下午：13:00-15:00
                    for hour in [13, 14]:
                        for minute in range(0, 60, 5):
                            time_str = f"{hour:02d}:{minute:02d}:00"
                            f.write(dt.strftime('%Y-%m-%d') + ' ' + time_str + '\n')

        logger.info(f"生成交易日历: {calendar_file} (freq={freq})")

    def _get_default_stock_list(self) -> List[str]:
        """获取默认股票列表（沪深300成分股）"""
        # 简化版：返回常见的A股股票代码
        # 实际应用中可以从AkShare获取沪深300成分股
        default_stocks = [
            # 沪市主要股票
            '600519.SH',  # 贵州茅台
            '600036.SH',  # 招商银行
            '601318.SH',  # 中国平安
            '600887.SH',  # 伊利股份
            '600276.SH',  # 恒瑞医药

            # 深市主要股票
            '000001.SZ',  # 平安银行
            '000002.SZ',  # 万科A
            '000858.SZ',  # 五粮液
            '000333.SZ',  # 美的集团
            '000725.SZ',  # 京东方A
        ]

        logger.info(f"使用默认股票列表: {len(default_stocks)}只股票")
        return default_stocks


def test_syncer():
    """测试数据同步器"""
    print("=" * 60)
    print("Qlib Data Syncer Test")
    print("=" * 60)

    # 创建同步器
    syncer = QlibDataSyncer(qlib_dir="./qlib_data")

    # 同步5只股票的日线数据（测试）
    test_symbols = ['600519.SH', '000001.SZ', '600036.SH']

    print(f"\nSyncing {len(test_symbols)} stocks (daily data only)...")

    stats = syncer.sync_stock_list(
        symbols=test_symbols,
        full_sync=False,  # 增量同步（最近30天）
        timeframes=['daily'],  # 仅日线数据
        max_workers=4
    )

    print("\n" + "=" * 60)
    print("Sync Results:")
    print("=" * 60)
    print(f"Total symbols: {stats['total_symbols']}")
    print(f"Success: {stats['success_symbols']}")
    print(f"Failed: {stats['failed_symbols']}")
    print(f"Total records: {stats['total_records']}")

    if stats['failed_list']:
        print(f"\nFailed stocks:")
        for symbol, timeframe in stats['failed_list']:
            print(f"  - {symbol} ({timeframe})")


if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    test_syncer()
