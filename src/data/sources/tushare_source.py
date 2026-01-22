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
    def get_financial_indicators(self, symbol: str, period: str = None) -> Dict:
        """获取财务指标数据

        Args:
            symbol: 股票代码
            period: 报告期，格式YYYYMMDD，如20231231。None表示获取最新

        Returns:
            包含ROE、毛利率、营收增长率等指标的字典
        """
        try:
            ts_symbol = self.normalize_symbol(symbol)
            if ts_symbol is None:
                return {}

            # 获取财务指标
            if period:
                df = self.pro.fina_indicator(ts_code=ts_symbol, period=period)
            else:
                # 获取最近4个季度的数据
                df = self.pro.fina_indicator(ts_code=ts_symbol)

            if df is None or df.empty:
                logger.debug(f"Tushare未找到财务指标: {ts_symbol}")
                return {}

            # 取最新一期数据
            latest = df.iloc[0]

            indicators = {
                'roe': latest.get('roe', 0),  # 净资产收益率ROE
                'roe_waa': latest.get('roe_waa', 0),  # 加权平均ROE
                'grossprofit_margin': latest.get('grossprofit_margin', 0),  # 毛利率
                'netprofit_margin': latest.get('netprofit_margin', 0),  # 净利率
                'revenue_yoy': latest.get('or_yoy', 0),  # 营收同比增长率
                'profit_yoy': latest.get('op_yoy', 0),  # 营业利润同比增长率
                'netprofit_yoy': latest.get('net_profit_yoy', 0),  # 净利润同比增长率
                'debt_to_assets': latest.get('debt_to_assets', 0),  # 资产负债率
                'current_ratio': latest.get('current_ratio', 0),  # 流动比率
                'quick_ratio': latest.get('quick_ratio', 0),  # 速动比率
                'report_period': latest.get('end_date', ''),  # 报告期
            }

            logger.debug(f"Tushare成功获取财务指标: {ts_symbol}, 报告期: {indicators['report_period']}")
            return indicators

        except Exception as e:
            logger.error(f"Tushare获取财务指标失败 {symbol}: {e}")
            return {}

    def get_balance_sheet(self, symbol: str, period: str = None) -> Dict:
        """获取资产负债表数据

        Args:
            symbol: 股票代码
            period: 报告期，格式YYYYMMDD，如20231231。None表示获取最新

        Returns:
            包含总资产、总负债、股东权益等的字典
        """
        try:
            ts_symbol = self.normalize_symbol(symbol)
            if ts_symbol is None:
                return {}

            # 获取资产负债表
            if period:
                df = self.pro.balancesheet(ts_code=ts_symbol, period=period)
            else:
                # 获取最近4个季度的数据
                df = self.pro.balancesheet(ts_code=ts_symbol)

            if df is None or df.empty:
                logger.debug(f"Tushare未找到资产负债表: {ts_symbol}")
                return {}

            # 取最新一期数据
            latest = df.iloc[0]

            # 计算债务权益比
            total_liab = latest.get('total_liab', 0)  # 总负债
            total_hldr_eqy_exc_min_int = latest.get('total_hldr_eqy_exc_min_int', 0)  # 股东权益合计

            debt_to_equity = 0
            if total_hldr_eqy_exc_min_int and total_hldr_eqy_exc_min_int != 0:
                debt_to_equity = total_liab / total_hldr_eqy_exc_min_int

            balance_data = {
                'total_assets': latest.get('total_assets', 0),  # 总资产
                'total_liabilities': total_liab,  # 总负债
                'total_equity': total_hldr_eqy_exc_min_int,  # 股东权益
                'debt_to_equity': debt_to_equity,  # 债务权益比
                'current_assets': latest.get('total_cur_assets', 0),  # 流动资产
                'current_liabilities': latest.get('total_cur_liab', 0),  # 流动负债
                'report_period': latest.get('end_date', ''),  # 报告期
            }

            logger.debug(f"Tushare成功获取资产负债表: {ts_symbol}, 债务权益比: {debt_to_equity:.2f}")
            return balance_data

        except Exception as e:
            logger.error(f"Tushare获取资产负债表失败 {symbol}: {e}")
            return {}

    def get_fundamental_data(self, symbol: str) -> Dict:
        """获取完整的基本面数据（综合方法）

        Args:
            symbol: 股票代码

        Returns:
            包含所有基本面指标的字典
        """
        try:
            # 获取股票基本信息（包含PE、PB）
            stock_info = self.get_stock_info(symbol)

            # 获取财务指标（ROE、毛利率、营收增长率等）
            financial_indicators = self.get_financial_indicators(symbol)

            # 获取资产负债表（债务权益比等）
            balance_sheet = self.get_balance_sheet(symbol)

            # 合并所有数据
            fundamental_data = {
                # 估值指标
                'pe_ratio': stock_info.pe_ratio,
                'pb_ratio': stock_info.pb_ratio,
                'market_cap': stock_info.market_cap,

                # 盈利能力指标
                'roe': financial_indicators.get('roe', 0),
                'roe_waa': financial_indicators.get('roe_waa', 0),
                'grossprofit_margin': financial_indicators.get('grossprofit_margin', 0),
                'netprofit_margin': financial_indicators.get('netprofit_margin', 0),

                # 成长性指标
                'revenue_yoy': financial_indicators.get('revenue_yoy', 0),
                'profit_yoy': financial_indicators.get('profit_yoy', 0),
                'netprofit_yoy': financial_indicators.get('netprofit_yoy', 0),

                # 财务健康指标
                'debt_to_equity': balance_sheet.get('debt_to_equity', 0),
                'debt_to_assets': financial_indicators.get('debt_to_assets', 0),
                'current_ratio': financial_indicators.get('current_ratio', 0),

                # 元数据
                'report_period': financial_indicators.get('report_period', '') or balance_sheet.get('report_period', ''),
                'industry': stock_info.industry,
                'name': stock_info.name,
            }

            logger.debug(f"Tushare成功获取完整基本面数据: {symbol}")
            return fundamental_data

        except Exception as e:
            logger.error(f"Tushare获取基本面数据失败 {symbol}: {e}")
            return {}
