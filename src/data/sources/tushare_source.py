# -*- coding: utf-8 -*-
"""
Tushare数据源实现
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


class TushareSource(BaseDataSource):
    """Tushare数据源实现"""

    def __init__(self, token: str, config: Dict = None):
        super().__init__(config)
        self.token = token
        self.ts = None
        self.pro = None

    def _initialize(self):
        """初始化Tushare"""
        try:
            import tushare as ts
            self.ts = ts

            # 验证token
            if not self.token or self.token == "YOUR_TUSHARE_TOKEN_HERE":
                raise ValueError("Tushare token未配置或无效")

            # 设置token
            ts.set_token(self.token)
            self.pro = ts.pro_api()

            # 简单的连接测试（不获取具体数据，避免"No columns to parse"错误）
            try:
                # 只测试API连接，不解析数据
                test_response = self.pro.query('stock_basic', exchange='',
                                             list_status='L', fields='ts_code')
                if test_response is None:
                    raise ConnectionError("Tushare API连接失败")
                logger.debug("Tushare API连接测试成功")
            except Exception as conn_e:
                logger.warning(f"Tushare连接测试失败: {conn_e}")
                # 不抛出异常，允许在实际使用时再测试连接

            logger.debug("Tushare模块初始化成功")

        except ImportError:
            raise ImportError("Tushare未安装，请运行: pip install tushare")
        except ValueError as ve:
            raise ValueError(f"Tushare配置错误: {ve}")
        except Exception as e:
            raise Exception(f"Tushare初始化失败: {e}")

    def get_info(self) -> DataSourceInfo:
        """获取数据源信息"""
        return DataSourceInfo(
            source_type=DataSourceType.TUSHARE,
            name="Tushare专业数据源",
            is_available=self.is_available(),
            supported_timeframes=[TimeFrame.DAILY],  # Tushare主要支持日线数据
            rate_limit=5,  # 每秒5个请求（根据实际限制调整）
            description="Tushare提供的专业财经数据"
        )

    def normalize_symbol(self, symbol: str) -> Optional[str]:
        """标准化股票代码为Tushare格式"""
        normalized = super().normalize_symbol(symbol)
        if normalized is None:
            return None

        # Tushare格式: 600519.SH, 000001.SZ
        # 处理混合格式
        if symbol.startswith('SH') and symbol.endswith('.SZ'):
            code_part = symbol[2:8]
            if code_part.isdigit():
                return f"{code_part}.SH"
        elif symbol.startswith('SZ') and symbol.endswith('.SH'):
            code_part = symbol[2:8]
            if code_part.isdigit():
                return f"{code_part}.SZ"

        # 处理.SS后缀（YFinance格式）
        if symbol.endswith('.SS'):
            return symbol.replace('.SS', '.SH')

        # 处理带前缀但无后缀的情况
        if symbol.startswith('SH') and '.' not in symbol:
            code_part = symbol[2:]
            if code_part.isdigit() and len(code_part) == 6:
                return f"{code_part}.SH"
        elif symbol.startswith('SZ') and '.' not in symbol:
            code_part = symbol[2:]
            if code_part.isdigit() and len(code_part) == 6:
                return f"{code_part}.SZ"

        # 如果是纯数字，需要判断交易所
        if symbol.isdigit() and len(symbol) == 6:
            if symbol.startswith('6'):
                return f"{symbol}.SH"  # 上海
            elif symbol.startswith(('0', '3')):
                return f"{symbol}.SZ"  # 深圳

        return normalized

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

            logger.debug(f"Tushare获取日线数据: {symbol}, {start_date} - {end_date}")

            # 获取日线数据
            try:
                data = self.pro.daily(
                    ts_code=symbol,
                    start_date=start_date,
                    end_date=end_date
                )

                # 检查返回的数据类型
                if data is None:
                    raise DataNotFoundException(f"Tushare API返回None: {symbol}")

                if not isinstance(data, pd.DataFrame):
                    raise DataNotFoundException(f"Tushare返回非DataFrame数据: {type(data)}")

                if data.empty:
                    raise DataNotFoundException(f"Tushare未返回数据: {symbol}")

                logger.debug(f"Tushare成功获取数据: {symbol}, {len(data)}条记录")
                return self._standardize_tushare_data(data, request.symbol)

            except Exception as api_e:
                # 详细的API错误信息
                error_msg = str(api_e)
                if "No columns to parse from file" in error_msg:
                    raise DataNotFoundException(f"Tushare API异常(可能是token无效或积分不足): {symbol}")
                elif "权限" in error_msg or "积分" in error_msg:
                    raise DataNotFoundException(f"Tushare权限不足: {symbol} - {error_msg}")
                elif "频率" in error_msg or "limit" in error_msg.lower():
                    raise DataNotFoundException(f"Tushare请求频率过高: {symbol}")
                else:
                    raise DataNotFoundException(f"Tushare API错误: {symbol} - {error_msg}")

        except (InvalidSymbolException, DataNotFoundException):
            raise
        except Exception as e:
            logger.error(f"Tushare获取日线数据失败 {request.symbol}: {e}")
            raise DataNotFoundException(f"获取日线数据失败: {e}")

    def _get_minute_data(self, request: DataRequest) -> pd.DataFrame:
        """获取分钟数据（Tushare不支持）"""
        raise NotImplementedError("Tushare暂不支持分钟级数据")

    def _standardize_tushare_data(self, data: pd.DataFrame, original_symbol: str) -> pd.DataFrame:
        """标准化Tushare数据格式"""
        if data.empty:
            return pd.DataFrame()

        # Tushare数据列名映射
        column_mapping = {
            'trade_date': 'Date',
            'open': 'Open',
            'close': 'Close',
            'high': 'High',
            'low': 'Low',
            'vol': 'Volume',  # Tushare的成交量单位是手
            'amount': 'Amount'
        }

        # 重命名列
        data = data.rename(columns=column_mapping)

        # 设置日期索引
        if 'Date' in data.columns:
            data['Date'] = pd.to_datetime(data['Date'])
            data.set_index('Date', inplace=True)

        # Tushare的成交量单位是手，转换为股数
        if 'Volume' in data.columns:
            data['Volume'] = data['Volume'] * 100

        return self._standardize_data_format(data, original_symbol)

    def get_stock_info(self, symbol: str) -> StockInfo:
        """获取股票基本信息"""
        try:
            ts_symbol = self.normalize_symbol(symbol)
            if ts_symbol is None:
                return StockInfo(symbol=symbol)

            # 获取股票基本信息
            try:
                basic_info = self.pro.stock_basic(ts_code=ts_symbol)

                if basic_info is None or basic_info.empty:
                    logger.debug(f"Tushare未找到股票基本信息: {ts_symbol}")
                    return StockInfo(symbol=symbol)

                info_row = basic_info.iloc[0]

            except Exception as basic_e:
                error_msg = str(basic_e)
                if "No columns to parse from file" in error_msg:
                    logger.warning(f"Tushare基本信息API异常: {ts_symbol}")
                    return StockInfo(symbol=symbol)
                else:
                    logger.error(f"Tushare获取基本信息失败 {ts_symbol}: {basic_e}")
                    return StockInfo(symbol=symbol)

            # 尝试获取最新的财务数据
            additional_data = {}
            try:
                # 获取最新交易日的基本数据
                from datetime import datetime, timedelta
                # 获取最近5个交易日的数据，避免节假日问题
                end_date = datetime.now()
                start_date = end_date - timedelta(days=10)

                daily_basic = self.pro.daily_basic(
                    ts_code=ts_symbol,
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d')
                )

                if not daily_basic.empty:
                    # 取最新一条数据
                    latest_basic = daily_basic.iloc[-1]
                    additional_data.update({
                        'pe': latest_basic.get('pe', 0),
                        'pb': latest_basic.get('pb', 0),
                        'total_mv': latest_basic.get('total_mv', 0),
                        'circ_mv': latest_basic.get('circ_mv', 0)
                    })
                    logger.debug(f"Tushare成功获取财务数据: {ts_symbol}")

            except Exception as fin_e:
                logger.debug(f"Tushare财务数据获取失败 {ts_symbol}: {fin_e}")
                # 财务数据获取失败不影响基本信息

            stock_info = StockInfo(
                symbol=symbol,
                name=info_row.get('name', ''),
                industry=info_row.get('industry', ''),
                market_cap=additional_data.get('total_mv', 0),
                pe_ratio=additional_data.get('pe', 0),
                pb_ratio=additional_data.get('pb', 0),
                region=info_row.get('area', ''),
                list_date=info_row.get('list_date', ''),
                additional_data=additional_data
            )

            return stock_info

        except Exception as e:
            logger.error(f"Tushare获取股票信息失败 {symbol}: {e}")
            return StockInfo(symbol=symbol)