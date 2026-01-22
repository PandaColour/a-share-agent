# -*- coding: utf-8 -*-
"""
多数据源股票数据提供者
支持AkShare、Tushare、yfinance等多种数据源
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional, List
import logging
from datetime import datetime, timedelta
import json
import os
import sys

logger = logging.getLogger(__name__)

class MultiSourceDataProvider:
    """多数据源数据提供者"""
    
    def __init__(self, config_file: str = None):
        """
        初始化多数据源提供者

        Args:
            config_file: 配置文件路径，如果为None则使用统一配置文件
        """
        # 如果没有指定配置文件，使用统一配置文件
        if config_file is None:
            config_file = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'unified_config.json')

        self.config = self._load_config(config_file)

        # 从data_sources部分获取配置
        data_sources_config = self.config.get('system_settings', {}).get('data_sources', {})
        self.primary_source = data_sources_config.get('primary_source', 'akshare')
        self.fallback_sources = data_sources_config.get('fallback_sources', ['yfinance'])
        
        # 初始化各种数据源
        self.sources = {}
        self._init_data_sources()
        
        logger.info(f"多数据源提供者初始化完成，主数据源: {self.primary_source}")
    
    def _load_config(self, config_file: str = None) -> Dict:
        """加载配置文件"""
        default_config = {
            "primary_source": "akshare",
            "fallback_sources": ["yfinance"],
            "tushare": {
                "token": "",
                "enabled": False
            },
            "akshare": {
                "enabled": True
            },
            "yfinance": {
                "enabled": True
            }
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                default_config.update(file_config)
                logger.info(f"已加载配置文件: {config_file}")
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}，使用默认配置")
        
        # 检查环境变量中的Tushare token
        tushare_token = os.getenv('TUSHARE_TOKEN')
        if tushare_token:
            default_config['tushare']['token'] = tushare_token
            default_config['tushare']['enabled'] = True
            logger.info("从环境变量获取Tushare token")
        
        return default_config
    
    def _init_data_sources(self):
        """初始化数据源"""
        # 获取数据源配置
        data_sources_config = self.config.get('system_settings', {}).get('data_sources', {})

        # 初始化AkShare
        akshare_config = data_sources_config.get('akshare', {})
        if akshare_config.get('enabled', True):
            try:
                self.sources['akshare'] = AkShareSource()
                logger.info("✅ AkShare数据源初始化成功")
            except Exception as e:
                logger.error(f"❌ AkShare数据源初始化失败: {e}")

        # 初始化Tushare
        tushare_config = data_sources_config.get('tushare', {})
        if tushare_config.get('enabled', False):
            tushare_token = tushare_config.get('token')
            if tushare_token:
                try:
                    self.sources['tushare'] = TushareSource(tushare_token)
                    logger.info("✅ Tushare数据源初始化成功")
                except Exception as e:
                    logger.error(f"❌ Tushare数据源初始化失败: {e}")
            else:
                logger.warning("⚠️ Tushare token未配置，跳过初始化")

        # 初始化yfinance (作为备用数据源)
        yfinance_config = data_sources_config.get('yfinance', {})
        if yfinance_config.get('enabled', True):
            try:
                self.sources['yfinance'] = YFinanceSource()
                logger.info("✅ YFinance数据源初始化成功")
            except Exception as e:
                logger.error(f"❌ YFinance数据源初始化失败: {e}")
    
    def get_stock_data(self, symbol: str, start_date: str = None, end_date: str = None, period: str = "1y") -> pd.DataFrame:
        """
        获取股票数据，支持多数据源自动切换

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            period: 时间周期 (当start_date和end_date为None时使用)

        Returns:
            股票数据DataFrame
        """
        # 标准化股票代码格式
        normalized_symbol = self._normalize_symbol_format(symbol)
        if normalized_symbol is None:  # 过滤掉B股等不支持的代码
            logger.debug(f"股票代码被过滤: {symbol}")
            return pd.DataFrame()

        # 确定尝试顺序
        sources_to_try = [self.primary_source] + [s for s in self.fallback_sources if s != self.primary_source]

        for source_name in sources_to_try:
            if source_name not in self.sources:
                logger.debug(f"数据源 {source_name} 不可用，跳过")
                continue

            try:
                logger.debug(f"尝试从 {source_name} 获取 {normalized_symbol} 数据")
                source = self.sources[source_name]

                if start_date and end_date:
                    data = source.get_data_by_date_range(normalized_symbol, start_date, end_date)
                else:
                    data = source.get_data_by_period(normalized_symbol, period)

                if data is not None and not data.empty:
                    logger.debug(f"✅ 从 {source_name} 成功获取 {normalized_symbol} 数据: {len(data)}条记录")
                    # 添加数据源标记
                    data.attrs['source'] = source_name
                    return data
                else:
                    logger.debug(f"⚠️ {source_name} 返回空数据: {normalized_symbol}")

            except Exception as e:
                logger.warning(f"❌ 从 {source_name} 获取 {normalized_symbol} 数据失败: {e}")
                continue

        logger.error(f"所有数据源都无法获取 {normalized_symbol} 的数据")
        return pd.DataFrame()

    def _normalize_symbol_format(self, symbol: str) -> str:
        """标准化股票代码格式，处理混合格式问题"""
        if not symbol:
            return symbol

        symbol = symbol.strip().upper()

        # 处理混合格式 (如 SH600376.SZ -> 600376.SH)
        if symbol.startswith('SH') and symbol.endswith('.SZ'):
            code_part = symbol[2:8]  # 提取中间6位数字
            if code_part.isdigit():
                normalized = f"{code_part}.SH"
                logger.debug(f"修正混合格式: {symbol} -> {normalized}")
                return normalized
        elif symbol.startswith('SZ') and symbol.endswith('.SH'):
            code_part = symbol[2:8]  # 提取中间6位数字
            if code_part.isdigit():
                normalized = f"{code_part}.SZ"
                logger.debug(f"修正混合格式: {symbol} -> {normalized}")
                return normalized

        # 处理带前缀但无后缀的情况
        if symbol.startswith('SH') and '.' not in symbol:
            code_part = symbol[2:]
            if code_part.isdigit() and len(code_part) == 6:
                return f"{code_part}.SH"
        elif symbol.startswith('SZ') and '.' not in symbol:
            code_part = symbol[2:]
            if code_part.isdigit() and len(code_part) == 6:
                return f"{code_part}.SZ"

        # 过滤B股代码
        if symbol.isdigit() and len(symbol) == 6:
            if symbol.startswith('90') or symbol.startswith('20'):  # B股代码
                logger.debug(f"过滤B股代码: {symbol}")
                return None  # 返回None表示过滤掉此代码

        return symbol
    
    def get_stock_info(self, symbol: str) -> Dict:
        """获取股票基本信息"""
        # 标准化股票代码格式
        normalized_symbol = self._normalize_symbol_format(symbol)
        if normalized_symbol is None:  # 过滤掉B股等不支持的代码
            logger.debug(f"股票代码被过滤: {symbol}")
            return {}

        sources_to_try = [self.primary_source] + [s for s in self.fallback_sources if s != self.primary_source]

        for source_name in sources_to_try:
            if source_name not in self.sources:
                continue

            try:
                source = self.sources[source_name]
                info = source.get_stock_info(normalized_symbol)

                if info:
                    logger.debug(f"✅ 从 {source_name} 获取 {normalized_symbol} 基本信息")
                    return info

            except Exception as e:
                logger.debug(f"从 {source_name} 获取 {normalized_symbol} 基本信息失败: {e}")
                continue

        return {"symbol": normalized_symbol}

    def get_fundamental_data(self, symbol: str) -> Dict:
        """
        获取基本面数据（PE/PB/ROE/营收增长/毛利率/债务权益比等）

        Args:
            symbol: 股票代码

        Returns:
            基本面数据字典，包含:
            - pe_ratio: 市盈率
            - pb_ratio: 市净率
            - roe: 净资产收益率
            - revenue_yoy: 营收同比增长率
            - grossprofit_margin: 毛利率
            - debt_to_equity: 债务权益比
            - ... 其他指标
        """
        # 标准化股票代码格式
        normalized_symbol = self._normalize_symbol_format(symbol)
        if normalized_symbol is None:
            logger.debug(f"股票代码被过滤: {symbol}")
            return {}

        # 优先使用Tushare（Tushare有完整的财务数据API）
        sources_to_try = ['tushare', 'akshare']

        for source_name in sources_to_try:
            if source_name not in self.sources:
                continue

            try:
                source = self.sources[source_name]

                # 检查数据源是否支持get_fundamental_data方法
                if hasattr(source, 'get_fundamental_data'):
                    fundamental_data = source.get_fundamental_data(normalized_symbol)

                    if fundamental_data and isinstance(fundamental_data, dict):
                        # 验证至少有一些关键指标
                        has_data = any(fundamental_data.get(key) is not None
                                      for key in ['pe_ratio', 'pb_ratio', 'roe', 'revenue_yoy'])

                        if has_data:
                            logger.debug(f"✅ 从 {source_name} 获取 {normalized_symbol} 基本面数据")
                            return fundamental_data

            except Exception as e:
                logger.debug(f"从 {source_name} 获取 {normalized_symbol} 基本面数据失败: {e}")
                continue

        # 如果所有数据源都失败，返回空字典
        logger.debug(f"无法获取 {normalized_symbol} 的基本面数据")
        return {}

    def calculate_dual_timeframe_indicators(self, daily_data: pd.DataFrame, intraday_data: pd.DataFrame, info: Dict = None) -> Dict:
        """
        计算双重时间框架技术指标

        Args:
            daily_data: 日线数据
            intraday_data: 5分钟数据
            info: 股票基本信息

        Returns:
            包含daily_*和intraday_*指标的字典
        """
        indicators = {}

        # 计算日线指标
        if not daily_data.empty:
            daily_indicators = self.calculate_technical_indicators(daily_data, info, prefix="daily_")
            indicators.update(daily_indicators)

        # 计算5分钟指标
        if not intraday_data.empty:
            intraday_indicators = self.calculate_technical_indicators(intraday_data, info, prefix="intraday_")
            indicators.update(intraday_indicators)

            # 计算融合指标
            if not daily_data.empty:
                fusion_indicators = self.calculate_fusion_indicators(daily_indicators, intraday_indicators, daily_data, intraday_data)
                indicators.update(fusion_indicators)

        return indicators

    def calculate_technical_indicators(self, data: pd.DataFrame, info: Dict = None, prefix: str = "") -> Dict:
        """计算技术指标（支持前缀）"""
        if data.empty:
            return {}

        indicators = {}

        # 添加前缀函数
        def add_prefix(key: str) -> str:
            return f"{prefix}{key}" if prefix else key
        
        try:
            # 移动平均线
            if len(data) >= 5:
                indicators[add_prefix('ma5')] = data['Close'].rolling(window=5).mean().iloc[-1]
            if len(data) >= 20:
                indicators[add_prefix('ma20')] = data['Close'].rolling(window=20).mean().iloc[-1]

            # RSI
            if len(data) >= 14:
                delta = data['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                indicators[add_prefix('rsi')] = (100 - (100 / (1 + rs))).iloc[-1]

            # 波动率
            if len(data) >= 20:
                indicators[add_prefix('volatility')] = data['Close'].pct_change().rolling(window=20).std().iloc[-1] * np.sqrt(252)

            # MACD指标
            if len(data) >= 26:
                macd_data = self._calculate_macd(data['Close'], prefix)
                indicators.update(macd_data)

            # KDJ指标
            if len(data) >= 9:
                kdj_data = self._calculate_kdj(data, prefix)
                indicators.update(kdj_data)

            # 威廉指标
            if len(data) >= 14:
                williams_data = self._calculate_williams_r(data, prefix)
                indicators.update(williams_data)

            # CCI指标
            if len(data) >= 14:
                cci_data = self._calculate_cci(data, prefix)
                indicators.update(cci_data)

            # 成交量指标
            if len(data) >= 5:
                volume_data = self._calculate_volume_indicators(data, info or {}, prefix)
                indicators.update(volume_data)

            # 价格位置
            current_price = data['Close'].iloc[-1]
            high_52w = data['High'].rolling(window=min(252, len(data))).max().iloc[-1]
            low_52w = data['Low'].rolling(window=min(252, len(data))).min().iloc[-1]
            if high_52w != low_52w:
                indicators[add_prefix('price_position')] = (current_price - low_52w) / (high_52w - low_52w)
            else:
                indicators[add_prefix('price_position')] = 0.5
                
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
        
        return indicators
    
    def get_minute_data(self, symbol: str, period: str = "5", days: int = 10) -> pd.DataFrame:
        """
        获取分钟级数据（支持多数据源故障转移）

        Args:
            symbol: 股票代码
            period: 分钟周期 ("1", "5", "15", "30", "60")
            days: 获取最近几天的数据

        Returns:
            分钟级数据DataFrame
        """
        # 标准化股票代码格式
        normalized_symbol = self._normalize_symbol_format(symbol)
        if normalized_symbol is None:  # 过滤掉B股等不支持的代码
            logger.debug(f"股票代码被过滤: {symbol}")
            return pd.DataFrame()

        # 确定尝试顺序（当前只有AkShare支持分钟级数据）
        sources_to_try = ['akshare']  # 后续可扩展tushare等

        for source_name in sources_to_try:
            if source_name not in self.sources:
                logger.debug(f"数据源 {source_name} 不可用，跳过")
                continue

            try:
                logger.debug(f"尝试从 {source_name} 获取 {normalized_symbol} 的{period}分钟数据")
                source = self.sources[source_name]

                # 检查数据源是否支持分钟级数据
                if hasattr(source, 'get_minute_data'):
                    data = source.get_minute_data(normalized_symbol, period, days)

                    if data is not None and not data.empty:
                        logger.debug(f"✅ 从 {source_name} 成功获取 {normalized_symbol} 的{period}分钟数据: {len(data)}条记录")
                        # 添加数据源标记
                        data.attrs['source'] = source_name
                        data.attrs['timeframe'] = f"{period}min"
                        return data
                    else:
                        logger.debug(f"⚠️ {source_name} 返回空的分钟级数据: {normalized_symbol}")
                else:
                    logger.debug(f"⚠️ {source_name} 不支持分钟级数据")

            except Exception as e:
                logger.warning(f"❌ 从 {source_name} 获取 {normalized_symbol} 的分钟级数据失败: {e}")
                continue

        logger.error(f"所有数据源都无法获取 {normalized_symbol} 的分钟级数据")
        return pd.DataFrame()

    def get_complete_stock_data(self, symbol: str, start_date: str = None, end_date: str = None, period: str = "1y", include_intraday: bool = True) -> Tuple[pd.DataFrame, Dict, Dict, Dict, pd.DataFrame, Dict]:
        """
        获取完整的股票数据（支持双重时间框架 + 基本面数据）

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 日线数据时间周期
            include_intraday: 是否包含5分钟数据

        Returns:
            Tuple[daily_data, info, indicators, price_info, intraday_data, fundamental_data]
            - daily_data: 日线数据
            - info: 股票基本信息
            - indicators: 技术指标（包含daily_*和intraday_*指标）
            - price_info: 价格信息
            - intraday_data: 5分钟K线数据（如果获取失败则为空DataFrame）
            - fundamental_data: 基本面数据字典（PE/PB/ROE/营收增长/毛利率/债务权益比等）
        """
        try:
            # 获取日线数据
            daily_data = self.get_stock_data(symbol, start_date, end_date, period)

            if daily_data.empty:
                return pd.DataFrame(), {}, {}, {}, pd.DataFrame(), {}

            # 获取股票信息
            info = self.get_stock_info(symbol)

            # 获取基本面数据（新增）
            fundamental_data = self.get_fundamental_data(symbol)

            # 获取5分钟数据（如果需要）
            intraday_data = pd.DataFrame()
            if include_intraday:
                try:
                    intraday_data = self.get_minute_data(symbol, period="5", days=10)
                    if not intraday_data.empty:
                        logger.debug(f"✅ 获取到{symbol}的5分钟数据: {len(intraday_data)}条记录")
                    else:
                        logger.debug(f"未能获取{symbol}的5分钟数据，将只使用日线数据")
                except Exception as e:
                    logger.debug(f"获取{symbol}的5分钟数据失败: {e}，将只使用日线数据")

            # 计算双重时间框架技术指标
            indicators = self.calculate_dual_timeframe_indicators(daily_data, intraday_data, info)

            # 获取价格信息（优先使用实时数据）
            price_info = self._get_realtime_price_info(daily_data, intraday_data)

            # 【改进】返回5分钟数据和基本面数据，供因子计算使用
            return daily_data, info, indicators, price_info, intraday_data, fundamental_data

        except Exception as e:
            logger.error(f"获取完整股票数据失败 {symbol}: {e}")
            return pd.DataFrame(), {}, {}, {}, pd.DataFrame(), {}
    
    def get_current_price_info(self, data: pd.DataFrame) -> Dict:
        """获取当前价格信息（复用原有逻辑）"""
        if data.empty:
            return {
                "current_price": 0.0,
                "daily_high": 0.0,
                "daily_low": 0.0,
                "daily_change": 0.0,
                "daily_change_percent": 0.0
            }
        
        try:
            # 最新交易日的数据
            latest_data = data.iloc[-1]
            current_price = float(latest_data['Close'])
            daily_high = float(latest_data['High'])
            daily_low = float(latest_data['Low'])
            
            # 计算日涨跌
            if len(data) >= 2:
                prev_close = float(data.iloc[-2]['Close'])
                daily_change = current_price - prev_close
                daily_change_percent = (daily_change / prev_close) * 100 if prev_close != 0 else 0.0
            else:
                daily_change = 0.0
                daily_change_percent = 0.0
            
            price_info = {
                "current_price": round(current_price, 2),
                "daily_high": round(daily_high, 2),
                "daily_low": round(daily_low, 2),
                "daily_change": round(daily_change, 2),
                "daily_change_percent": round(daily_change_percent, 2)
            }
            
            return price_info
            
        except Exception as e:
            logger.error(f"获取价格信息失败: {e}")
            return {
                "current_price": 0.0,
                "daily_high": 0.0,
                "daily_low": 0.0,
                "daily_change": 0.0,
                "daily_change_percent": 0.0
            }

    def _get_realtime_price_info(self, daily_data: pd.DataFrame, intraday_data: pd.DataFrame) -> Dict:
        """
        获取实时价格信息(优先使用5分钟数据补充今日价格)

        Args:
            daily_data: 日线数据
            intraday_data: 5分钟数据

        Returns:
            Dict: 价格信息字典
        """
        if daily_data.empty:
            return {
                "current_price": 0.0,
                "daily_high": 0.0,
                "daily_low": 0.0,
                "daily_change": 0.0,
                "daily_change_percent": 0.0
            }

        try:
            # 检查日线数据最后日期是否是今天
            today = datetime.now().date()
            daily_last_date = pd.to_datetime(daily_data.index[-1]).date()

            # 如果日线数据已包含今天，直接使用日线数据
            if daily_last_date == today:
                logger.debug(f"日线数据包含今天({today})，使用日线数据")
                return self.get_current_price_info(daily_data)

            # 如果日线数据不包含今天，且有5分钟数据，使用5分钟数据补充
            if not intraday_data.empty:
                intraday_last_date = pd.to_datetime(intraday_data.index[-1]).date()

                # 检查5分钟数据是否是今天的
                if intraday_last_date == today:
                    logger.info(f"⏰ 日线数据最后日期({daily_last_date})非今日，使用5分钟实时数据({intraday_last_date})")

                    # 从5分钟数据获取今日实时价格
                    current_price = float(intraday_data['Close'].iloc[-1])

                    # 获取今日的5分钟数据，计算日内最高最低
                    today_intraday = intraday_data[pd.to_datetime(intraday_data.index).date == today]
                    daily_high = float(today_intraday['High'].max())
                    daily_low = float(today_intraday['Low'].min())

                    # 昨日收盘价从日线数据获取
                    prev_close = float(daily_data['Close'].iloc[-1])
                    daily_change = current_price - prev_close
                    daily_change_percent = (daily_change / prev_close) * 100 if prev_close != 0 else 0.0

                    price_info = {
                        "current_price": round(current_price, 2),
                        "daily_high": round(daily_high, 2),
                        "daily_low": round(daily_low, 2),
                        "daily_change": round(daily_change, 2),
                        "daily_change_percent": round(daily_change_percent, 2),
                        "data_source": "intraday"  # 标记数据来源
                    }

                    logger.debug(f"实时价格: {current_price:.2f}, 涨跌: {daily_change_percent:+.2f}%")
                    return price_info
                else:
                    logger.warning(f"5分钟数据最后日期({intraday_last_date})也不是今天，使用日线数据")

            # 如果没有今日实时数据，使用日线数据
            logger.debug(f"无今日实时数据，使用日线数据(最后日期: {daily_last_date})")
            return self.get_current_price_info(daily_data)

        except Exception as e:
            logger.error(f"获取实时价格信息失败: {e}，回退到日线数据")
            return self.get_current_price_info(daily_data)

    def get_available_sources(self) -> List[str]:
        """获取可用的数据源列表"""
        return list(self.sources.keys())
    
    def set_primary_source(self, source_name: str):
        """设置主数据源"""
        if source_name in self.sources:
            self.primary_source = source_name
            logger.info(f"已设置主数据源为: {source_name}")
        else:
            logger.error(f"数据源 {source_name} 不可用")
    
    # 以下是技术指标计算方法（复用原有逻辑）
    def _calculate_macd(self, close_prices: pd.Series, prefix: str = "", fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict:
        """计算MACD指标"""
        try:
            # 计算EMA
            ema_fast = close_prices.ewm(span=fast_period).mean()
            ema_slow = close_prices.ewm(span=slow_period).mean()
            
            # MACD线 = 快线EMA - 慢线EMA
            macd_line = ema_fast - ema_slow
            
            # 信号线 = MACD线的EMA
            signal_line = macd_line.ewm(span=signal_period).mean()
            
            # MACD柱状图 = MACD线 - 信号线
            histogram = macd_line - signal_line
            
            def add_prefix(key: str) -> str:
                return f"{prefix}{key}" if prefix else key

            return {
                add_prefix('macd'): macd_line.iloc[-1],
                add_prefix('macd_signal'): signal_line.iloc[-1],
                add_prefix('macd_histogram'): histogram.iloc[-1]
            }
        except Exception as e:
            logger.error(f"MACD计算失败: {e}")
            def add_prefix(key: str) -> str:
                return f"{prefix}{key}" if prefix else key
            return {add_prefix('macd'): 0, add_prefix('macd_signal'): 0, add_prefix('macd_histogram'): 0}
    
    def _calculate_kdj(self, data: pd.DataFrame, prefix: str = "", k_period: int = 9, d_period: int = 3, j_period: int = 3) -> Dict:
        """计算KDJ指标"""
        try:
            # 计算RSV (Raw Stochastic Value)
            low_min = data['Low'].rolling(window=k_period).min()
            high_max = data['High'].rolling(window=k_period).max()
            
            # RSV = (当前收盘价 - n日内最低价) / (n日内最高价 - n日内最低价) * 100
            rsv = ((data['Close'] - low_min) / (high_max - low_min)) * 100
            
            # K值 = RSV的移动平均
            k_values = rsv.rolling(window=d_period).mean()
            
            # D值 = K值的移动平均  
            d_values = k_values.rolling(window=j_period).mean()
            
            # J值 = 3*K - 2*D
            j_values = 3 * k_values - 2 * d_values
            
            def add_prefix(key: str) -> str:
                return f"{prefix}{key}" if prefix else key

            return {
                add_prefix('kdj_k'): k_values.iloc[-1] if not k_values.empty else 50,
                add_prefix('kdj_d'): d_values.iloc[-1] if not d_values.empty else 50,
                add_prefix('kdj_j'): j_values.iloc[-1] if not j_values.empty else 50
            }
        except Exception as e:
            logger.error(f"KDJ计算失败: {e}")
            def add_prefix(key: str) -> str:
                return f"{prefix}{key}" if prefix else key
            return {add_prefix('kdj_k'): 50, add_prefix('kdj_d'): 50, add_prefix('kdj_j'): 50}
    
    def _calculate_williams_r(self, data: pd.DataFrame, prefix: str = "", period: int = 14) -> Dict:
        """计算威廉指标(Williams %R)"""
        try:
            # 计算n日内最高价和最低价
            high_max = data['High'].rolling(window=period).max()
            low_min = data['Low'].rolling(window=period).min()
            
            # Williams %R = (最高价 - 收盘价) / (最高价 - 最低价) * (-100)
            williams_r = ((high_max - data['Close']) / (high_max - low_min)) * (-100)
            
            def add_prefix(key: str) -> str:
                return f"{prefix}{key}" if prefix else key

            return {
                add_prefix('williams_r'): williams_r.iloc[-1] if not williams_r.empty else -50
            }
        except Exception as e:
            logger.error(f"威廉指标计算失败: {e}")
            def add_prefix(key: str) -> str:
                return f"{prefix}{key}" if prefix else key
            return {add_prefix('williams_r'): -50}
    
    def _calculate_cci(self, data: pd.DataFrame, prefix: str = "", period: int = 14) -> Dict:
        """计算CCI指标(Commodity Channel Index)"""
        try:
            # 计算典型价格 TP = (High + Low + Close) / 3
            tp = (data['High'] + data['Low'] + data['Close']) / 3
            
            # 计算TP的移动平均
            ma_tp = tp.rolling(window=period).mean()
            
            # 计算平均绝对偏差 MD
            md = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
            
            # CCI = (TP - MA) / (0.015 * MD)
            cci = (tp - ma_tp) / (0.015 * md)
            
            def add_prefix(key: str) -> str:
                return f"{prefix}{key}" if prefix else key

            return {
                add_prefix('cci'): cci.iloc[-1] if not cci.empty else 0
            }
        except Exception as e:
            logger.error(f"CCI指标计算失败: {e}")
            def add_prefix(key: str) -> str:
                return f"{prefix}{key}" if prefix else key
            return {add_prefix('cci'): 0}
    
    def _calculate_volume_indicators(self, data: pd.DataFrame, info: Dict, prefix: str = "") -> Dict:
        """计算成交量相关指标"""
        try:
            volume_indicators = {}
            
            # 计算换手率 (需要流通股本数据)
            shares_outstanding = info.get('sharesOutstanding', 0)  # 流通股本
            if shares_outstanding > 0 and not data.empty:
                # 换手率 = 成交量 / 流通股本 * 100%
                turnover_rate = (data['Volume'].iloc[-1] / shares_outstanding) * 100
                def add_prefix(key: str) -> str:
                    return f"{prefix}{key}" if prefix else key
                volume_indicators[add_prefix('turnover_rate')] = min(turnover_rate, 100)  # 限制最大100%
            else:
                # 如果没有流通股本数据，使用相对换手率估算
                avg_volume = data['Volume'].rolling(window=20).mean().iloc[-1] if len(data) >= 20 else data['Volume'].mean()
                def add_prefix(key: str) -> str:
                    return f"{prefix}{key}" if prefix else key
                volume_indicators[add_prefix('turnover_rate')] = min((data['Volume'].iloc[-1] / avg_volume) * 2, 20)  # 相对换手率
            
            # 量价关系分析
            if len(data) >= 5:
                volume_price_relation = self._analyze_volume_price_relation(data, prefix)
                volume_indicators.update(volume_price_relation)
            
            return volume_indicators
        except Exception as e:
            logger.error(f"成交量指标计算失败: {e}")
            def add_prefix(key: str) -> str:
                return f"{prefix}{key}" if prefix else key
            return {add_prefix('turnover_rate'): 1.0, add_prefix('volume_price_trend'): 'neutral'}
    
    def _analyze_volume_price_relation(self, data: pd.DataFrame, prefix: str = "") -> Dict:
        """分析量价关系"""
        try:
            # 取最近5天数据
            recent_data = data.tail(5)
            
            # 价格变化趋势
            price_change = recent_data['Close'].pct_change().dropna()
            volume_change = recent_data['Volume'].pct_change().dropna()
            
            # 计算价格和成交量的相关性
            if len(price_change) > 2 and len(volume_change) > 2:
                correlation = np.corrcoef(price_change, volume_change)[0, 1]
                
                # 判断量价关系
                if correlation > 0.3:
                    volume_price_trend = "量价齐升"
                elif correlation < -0.3:
                    volume_price_trend = "量价背离" 
                else:
                    volume_price_trend = "量价平衡"
                    
                # 计算量比 (当日成交量/近5日平均成交量)
                avg_volume = recent_data['Volume'].mean()
                current_volume = recent_data['Volume'].iloc[-1]
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
                
                def add_prefix(key: str) -> str:
                    return f"{prefix}{key}" if prefix else key

                return {
                    add_prefix('volume_price_trend'): volume_price_trend,
                    add_prefix('volume_price_correlation'): round(correlation, 3),
                    add_prefix('volume_ratio'): round(volume_ratio, 2)
                }
            else:
                def add_prefix(key: str) -> str:
                    return f"{prefix}{key}" if prefix else key

                return {
                    add_prefix('volume_price_trend'): 'neutral',
                    add_prefix('volume_price_correlation'): 0.0,
                    add_prefix('volume_ratio'): 1.0
                }
                
        except Exception as e:
            logger.error(f"量价关系分析失败: {e}")
            def add_prefix(key: str) -> str:
                return f"{prefix}{key}" if prefix else key

            return {
                add_prefix('volume_price_trend'): 'neutral',
                add_prefix('volume_price_correlation'): 0.0,
                add_prefix('volume_ratio'): 1.0
            }

    def calculate_fusion_indicators(self, daily_indicators: Dict, intraday_indicators: Dict, daily_data: pd.DataFrame, intraday_data: pd.DataFrame) -> Dict:
        """
        计算融合指标，结合日线和5分钟数据

        Args:
            daily_indicators: 日线指标字典
            intraday_indicators: 5分钟指标字典
            daily_data: 日线数据
            intraday_data: 5分钟数据

        Returns:
            融合指标字典
        """
        fusion_indicators = {}

        try:
            # 1. 趋势一致性：比较日线和5分钟的MA趋势
            daily_ma5 = daily_indicators.get('daily_ma5', 0)
            daily_ma20 = daily_indicators.get('daily_ma20', 0)
            intraday_ma5 = intraday_indicators.get('intraday_ma5', 0)
            intraday_ma20 = intraday_indicators.get('intraday_ma20', 0)

            daily_trend = 1 if daily_ma5 > daily_ma20 else -1 if daily_ma5 < daily_ma20 else 0
            intraday_trend = 1 if intraday_ma5 > intraday_ma20 else -1 if intraday_ma5 < intraday_ma20 else 0

            # 趋势一致性评分 (0-1)
            if daily_trend == intraday_trend and daily_trend != 0:
                trend_consistency = 1.0  # 完全一致
            elif daily_trend == 0 or intraday_trend == 0:
                trend_consistency = 0.5  # 中性
            else:
                trend_consistency = 0.0  # 背离

            fusion_indicators['trend_consistency'] = trend_consistency

            # 2. 波动率预警：基于5分钟波动率
            intraday_volatility = intraday_indicators.get('intraday_volatility', 0)
            daily_volatility = daily_indicators.get('daily_volatility', 0)

            # 波动率分类
            if intraday_volatility > daily_volatility * 2:
                volatility_alert = 'critical'  # 关键预警
            elif intraday_volatility > daily_volatility * 1.5:
                volatility_alert = 'warning'   # 黄色预警
            else:
                volatility_alert = 'normal'    # 正常

            fusion_indicators['volatility_alert'] = volatility_alert

            # 3. 动量背离：日线上涨但5分钟下跌（或反之）
            daily_momentum = self._calculate_momentum(daily_data, period=5)  # 5日动量
            intraday_momentum = intraday_indicators.get('intraday_momentum', 0)

            # 动量背离判断
            momentum_divergence = False
            if daily_momentum > 0.02 and intraday_momentum < -0.01:  # 日线上涨但5分钟下跌
                momentum_divergence = True
            elif daily_momentum < -0.02 and intraday_momentum > 0.01:  # 日线下跌但5分钟上涨
                momentum_divergence = True

            fusion_indicators['momentum_divergence'] = momentum_divergence

            # 4. 成交量异常倍数：比较当日和近期平均
            intraday_volume_ratio = intraday_indicators.get('intraday_volume_ratio', 1.0)
            daily_volume_ratio = daily_indicators.get('daily_volume_ratio', 1.0)

            # 成交量放大程度
            volume_amplification = max(intraday_volume_ratio, daily_volume_ratio)
            fusion_indicators['volume_amplification'] = round(volume_amplification, 2)

            # 5. 综合风险评级
            risk_score = 0
            if volatility_alert == 'critical':
                risk_score += 3
            elif volatility_alert == 'warning':
                risk_score += 2

            if momentum_divergence:
                risk_score += 2

            if trend_consistency < 0.3:
                risk_score += 1

            if volume_amplification > 5:
                risk_score += 1

            # 风险级别分类
            if risk_score >= 6:
                risk_level = 'high'
            elif risk_score >= 3:
                risk_level = 'medium'
            else:
                risk_level = 'low'

            fusion_indicators['risk_level'] = risk_level
            fusion_indicators['risk_score'] = risk_score

            # 6. 短期动量指标（基于5分钟数据）
            if not intraday_data.empty and len(intraday_data) >= 12:  # 至少1小时数据
                recent_intraday = intraday_data.tail(12)  # 最近1小时
                short_term_momentum = (recent_intraday['Close'].iloc[-1] - recent_intraday['Close'].iloc[0]) / recent_intraday['Close'].iloc[0]
                fusion_indicators['short_term_momentum'] = round(short_term_momentum, 4)
            else:
                fusion_indicators['short_term_momentum'] = 0.0

            logger.debug(f"融合指标计算成功: {fusion_indicators}")
            return fusion_indicators

        except Exception as e:
            logger.error(f"融合指标计算失败: {e}")
            return {
                'trend_consistency': 0.5,
                'volatility_alert': 'normal',
                'momentum_divergence': False,
                'volume_amplification': 1.0,
                'risk_level': 'low',
                'risk_score': 0,
                'short_term_momentum': 0.0
            }

    def _calculate_momentum(self, data: pd.DataFrame, period: int = 5) -> float:
        """计算动量指标"""
        try:
            if len(data) < period:
                return 0.0

            current_price = data['Close'].iloc[-1]
            past_price = data['Close'].iloc[-period]
            momentum = (current_price - past_price) / past_price
            return momentum
        except Exception:
            return 0.0


class DataSourceBase:
    """数据源基类"""
    
    def get_data_by_period(self, symbol: str, period: str) -> pd.DataFrame:
        """按时间周期获取数据"""
        raise NotImplementedError
    
    def get_data_by_date_range(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """按日期范围获取数据"""
        raise NotImplementedError
    
    def get_stock_info(self, symbol: str) -> Dict:
        """获取股票基本信息"""
        raise NotImplementedError


class AkShareSource(DataSourceBase):
    """AkShare数据源"""
    
    def __init__(self):
        try:
            import akshare as ak
            self.ak = ak
            logger.debug("AkShare模块导入成功")
        except ImportError:
            raise ImportError("AkShare未安装，请运行: pip install akshare")
    
    def _convert_symbol_for_akshare(self, symbol: str) -> str:
        """转换股票代码为AkShare格式"""
        # 600519.SS -> 600519, 000001.SZ -> 000001
        return symbol.replace('.SS', '').replace('.SZ', '').replace('.SH', '')

    def _is_etf_symbol(self, symbol: str) -> bool:
        """判断是否为ETF代码"""
        return (symbol.startswith('51') and symbol.endswith('.SH')) or \
               (symbol.startswith('15') and symbol.endswith('.SZ')) or \
               symbol.startswith('588')
    
    def get_data_by_period(self, symbol: str, period: str) -> pd.DataFrame:
        """按时间周期获取数据"""
        # 将period转换为日期范围
        end_date = datetime.now()
        
        if period == "1d":
            start_date = end_date - timedelta(days=1)
        elif period == "5d":
            start_date = end_date - timedelta(days=5)
        elif period == "1mo":
            start_date = end_date - timedelta(days=30)
        elif period == "3mo":
            start_date = end_date - timedelta(days=90)
        elif period == "6mo":
            start_date = end_date - timedelta(days=180)
        elif period == "1y":
            start_date = end_date - timedelta(days=365)
        elif period == "2y":
            start_date = end_date - timedelta(days=730)
        else:
            start_date = end_date - timedelta(days=365)  # 默认1年
        
        return self.get_data_by_date_range(
            symbol,
            start_date.strftime('%Y%m%d'),
            end_date.strftime('%Y%m%d')
        )
    
    def get_data_by_date_range(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """按日期范围获取数据"""
        try:
            # 转换日期格式 (YYYY-MM-DD -> YYYYMMDD)
            if '-' in start_date:
                start_date = start_date.replace('-', '')
            if '-' in end_date:
                end_date = end_date.replace('-', '')

            # 根据不同类型使用不同的API
            if self._is_etf_symbol(symbol):
                logger.debug(f"使用ETF API获取 {symbol}")
                data = self._get_etf_data(symbol, start_date, end_date)
            else:
                logger.debug(f"使用股票API获取 {symbol}")
                data = self._get_stock_data(symbol, start_date, end_date)

            if data is None or data.empty:
                logger.warning(f"AkShare返回空数据: {symbol}")
                return pd.DataFrame()

            return self._standardize_akshare_data(data, symbol)

        except Exception as e:
            logger.error(f"AkShare获取数据失败 {symbol}: {e}")
            return pd.DataFrame()

    def _get_stock_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票数据"""
        ak_symbol = self._convert_symbol_for_akshare(symbol)
        return self.ak.stock_zh_a_hist(
            symbol=ak_symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"  # 前复权
        )


    def _get_etf_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取ETF数据"""
        try:
            ak_symbol = self._convert_symbol_for_akshare(symbol)
            # ETF可以使用普通股票API
            return self.ak.stock_zh_a_hist(
                symbol=ak_symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
        except Exception as e:
            logger.warning(f"ETF API获取失败: {symbol}, {e}")
            return pd.DataFrame()

    def _standardize_akshare_data(self, data: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """标准化AkShare数据格式"""
        if data.empty:
            return pd.DataFrame()

        # 重命名列以匹配标准格式
        column_mapping = {
            '日期': 'Date',
            '开盘': 'Open',
            '收盘': 'Close',
            '最高': 'High',
            '最低': 'Low',
            '成交量': 'Volume',
            '成交额': 'Amount'
        }

        # 重命名存在的列
        existing_columns = data.columns.tolist()
        logger.debug(f"AkShare原始列名 {symbol}: {existing_columns}")
        rename_dict = {old: new for old, new in column_mapping.items() if old in existing_columns}
        data = data.rename(columns=rename_dict)

        # 检查是否成功重命名为Close列
        if 'Close' not in data.columns:
            logger.warning(f"AkShare数据缺少Close列 {symbol}，当前列名: {data.columns.tolist()}")
            # 尝试其他可能的列名
            for potential_close in ['close', '收盘价', '收盘']:
                if potential_close in data.columns:
                    data['Close'] = data[potential_close]
                    logger.info(f"使用 {potential_close} 作为Close列 {symbol}")
                    break

        # 设置日期索引
        if 'Date' in data.columns:
            data['Date'] = pd.to_datetime(data['Date'])
            data.set_index('Date', inplace=True)

        # 确保数值列是浮点型
        numeric_columns = ['Open', 'Close', 'High', 'Low', 'Volume']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')

        logger.debug(f"AkShare标准化后列名 {symbol}: {data.columns.tolist()}")
        return data
    
    def get_minute_data(self, symbol: str, period: str = "5", days: int = 10) -> pd.DataFrame:
        """获取分钟级数据

        Args:
            symbol: 股票代码
            period: 分钟周期 ("1", "5", "15", "30", "60")
            days: 获取最近几天的数据

        Returns:
            分钟级数据DataFrame
        """
        try:
            ak_symbol = self._convert_symbol_for_akshare(symbol)

            # 计算开始日期（交易日）
            from datetime import datetime, timedelta
            end_date = datetime.now()

            # 考虑到周末，获取稍多一些的天数以确保有足够的交易日数据
            start_date = end_date - timedelta(days=days + 4)

            # 获取分钟级数据
            data = self.ak.stock_zh_a_hist_min_em(
                symbol=ak_symbol,
                period=period,
                start_date=start_date.strftime('%Y-%m-%d %H:%M:%S'),
                end_date=end_date.strftime('%Y-%m-%d %H:%M:%S')
            )

            if data.empty:
                logger.debug(f"AkShare分钟级数据为空: {symbol}")
                return pd.DataFrame()

            # 重命名列以匹配标准格式
            column_mapping = {
                '时间': 'Date',
                '开盘': 'Open',
                '收盘': 'Close',
                '最高': 'High',
                '最低': 'Low',
                '成交量': 'Volume',
                '成交额': 'Amount'
            }

            # 重命名存在的列
            existing_columns = data.columns.tolist()
            logger.debug(f"AkShare分钟级原始列名: {existing_columns}")
            rename_dict = {old: new for old, new in column_mapping.items() if old in existing_columns}
            data = data.rename(columns=rename_dict)

            # 检查是否成功重命名为Close列
            if 'Close' not in data.columns:
                logger.warning(f"AkShare分钟级数据缺少Close列，当前列名: {data.columns.tolist()}")
                # 尝试其他可能的列名
                for potential_close in ['close', '收盘价', '收盘']:
                    if potential_close in data.columns:
                        data['Close'] = data[potential_close]
                        logger.info(f"分钟级数据使用 {potential_close} 作为Close列")
                        break

            # 设置时间索引
            if 'Date' in data.columns:
                data['Date'] = pd.to_datetime(data['Date'])
                data.set_index('Date', inplace=True)
                data.sort_index(inplace=True)

            # 确保数值列是浮点型
            numeric_columns = ['Open', 'Close', 'High', 'Low', 'Volume']
            for col in numeric_columns:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce')

            # 只保留最近指定交易日的数据
            if len(data) > 0:
                # 获取最近的交易日期
                data_dates = pd.to_datetime(data.index).date
                unique_dates = sorted(set(data_dates), reverse=True)

                if len(unique_dates) > days:
                    # 只保留最近days个交易日的数据
                    recent_dates = set(unique_dates[:days])
                    # 直接使用列表推导式过滤
                    filtered_data = data[[date in recent_dates for date in data_dates]]
                    data = filtered_data

            logger.debug(f"✅ AkShare获取{period}分钟数据成功: {symbol}, {len(data)}条记录")
            return data

        except Exception as e:
            logger.error(f"AkShare获取分钟级数据失败 {symbol}: {e}")
            return pd.DataFrame()

    def get_stock_info(self, symbol: str) -> Dict:
        """获取股票基本信息"""
        try:
            ak_symbol = self._convert_symbol_for_akshare(symbol)

            # 获取股票基本信息
            info = self.ak.stock_individual_info_em(symbol=ak_symbol)

            # 检查返回的数据类型和内容
            if info is None:
                logger.debug(f"AkShare返回None: {symbol}")
                return {"symbol": symbol}

            # 如果返回的是标量值，转换为DataFrame
            if not isinstance(info, pd.DataFrame):
                if isinstance(info, (dict, list)):
                    try:
                        info = pd.DataFrame(info)
                    except ValueError as ve:
                        if "scalar values" in str(ve):
                            # 处理标量值错误
                            logger.debug(f"处理标量值错误 {symbol}: {ve}")
                            if isinstance(info, dict):
                                info = pd.DataFrame([info])
                            else:
                                info = pd.DataFrame(info, index=[0])
                        else:
                            raise ve
                else:
                    # 单个标量值，包装成DataFrame
                    info = pd.DataFrame([{"value": info}], index=[0])

            if info.empty:
                logger.debug(f"AkShare返回空数据: {symbol}")
                return {"symbol": symbol}

            # 转换为字典格式
            info_dict = {}
            try:
                for _, row in info.iterrows():
                    key = row['item'] if 'item' in row else row.iloc[0]
                    value = row['value'] if 'value' in row else row.iloc[1]
                    info_dict[key] = value
            except Exception as e:
                logger.debug(f"解析AkShare信息数据失败 {symbol}: {e}")
                # 如果无法解析，尝试直接使用第一行数据
                if not info.empty:
                    first_row = info.iloc[0]
                    for col in info.columns:
                        info_dict[col] = first_row[col]

            # 标准化一些关键字段
            standardized_info = {"symbol": symbol}

            # 映射常用字段
            field_mapping = {
                '总股本': 'sharesOutstanding',
                '流通股本': 'floatShares',
                '总市值': 'marketCap',
                '流通市值': 'floatMarketCap',
                '行业': 'industry',
                '地区': 'region'
            }

            for chinese_key, english_key in field_mapping.items():
                if chinese_key in info_dict:
                    standardized_info[english_key] = info_dict[chinese_key]

            return standardized_info

        except Exception as e:
            logger.error(f"AkShare获取股票信息失败 {symbol}: {e}")
            return {"symbol": symbol}


class TushareSource(DataSourceBase):
    """Tushare数据源"""
    
    def __init__(self, token: str):
        try:
            import tushare as ts
            self.ts = ts
            ts.set_token(token)
            self.pro = ts.pro_api()
            logger.debug("Tushare模块初始化成功")
        except ImportError:
            raise ImportError("Tushare未安装，请运行: pip install tushare")
        except Exception as e:
            raise Exception(f"Tushare初始化失败: {e}")
    
    def _convert_symbol_for_tushare(self, symbol: str) -> str:
        """转换股票代码为Tushare格式"""
        # 600519.SS -> 600519.SH, 000001.SZ -> 000001.SZ
        return symbol.replace('.SS', '.SH')

    
    def get_data_by_period(self, symbol: str, period: str) -> pd.DataFrame:
        """按时间周期获取数据"""
        # 将period转换为日期范围
        end_date = datetime.now()
        
        if period == "1d":
            start_date = end_date - timedelta(days=1)
        elif period == "5d":
            start_date = end_date - timedelta(days=5)
        elif period == "1mo":
            start_date = end_date - timedelta(days=30)
        elif period == "3mo":
            start_date = end_date - timedelta(days=90)
        elif period == "6mo":
            start_date = end_date - timedelta(days=180)
        elif period == "1y":
            start_date = end_date - timedelta(days=365)
        elif period == "2y":
            start_date = end_date - timedelta(days=730)
        else:
            start_date = end_date - timedelta(days=365)  # 默认1年
        
        return self.get_data_by_date_range(
            symbol,
            start_date.strftime('%Y%m%d'),
            end_date.strftime('%Y%m%d')
        )
    
    def get_data_by_date_range(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """按日期范围获取数据"""
        try:
            ts_symbol = self._convert_symbol_for_tushare(symbol)

            # 转换日期格式 (YYYY-MM-DD -> YYYYMMDD)
            if '-' in start_date:
                start_date = start_date.replace('-', '')
            if '-' in end_date:
                end_date = end_date.replace('-', '')

            # 使用股票API获取数据
            logger.debug(f"Tushare使用股票API获取 {symbol}")
            # 获取日线数据
            data = self.pro.daily(
                ts_code=ts_symbol,
                start_date=start_date,
                end_date=end_date
            )
            
            if data.empty:
                return pd.DataFrame()
            
            # 重命名列以匹配标准格式
            column_mapping = {
                'trade_date': 'Date',
                'open': 'Open',
                'close': 'Close',
                'high': 'High',
                'low': 'Low',
                'vol': 'Volume',  # Tushare的成交量单位是手
                'amount': 'Amount'
            }
            
            data = data.rename(columns=column_mapping)
            
            # 设置日期索引
            if 'Date' in data.columns:
                data['Date'] = pd.to_datetime(data['Date'])
                data.set_index('Date', inplace=True)
                data.sort_index(inplace=True)  # 按日期排序
            
            # Tushare的成交量单位是手，需要转换为股数
            if 'Volume' in data.columns:
                data['Volume'] = data['Volume'] * 100  # 1手 = 100股
            
            # 确保数值列是浮点型
            numeric_columns = ['Open', 'Close', 'High', 'Low', 'Volume']
            for col in numeric_columns:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce')
            
            return data
            
        except Exception as e:
            logger.error(f"Tushare获取数据失败 {symbol}: {e}")
            return pd.DataFrame()
    
    def get_stock_info(self, symbol: str) -> Dict:
        """获取股票基本信息"""
        try:
            ts_symbol = self._convert_symbol_for_tushare(symbol)
            
            # 获取股票基本信息
            basic_info = self.pro.stock_basic(ts_code=ts_symbol)
            
            if basic_info.empty:
                return {"symbol": symbol}
            
            info_row = basic_info.iloc[0]
            
            # 构建标准化信息字典
            standardized_info = {
                "symbol": symbol,
                "name": info_row.get('name', ''),
                "industry": info_row.get('industry', ''),
                "area": info_row.get('area', ''),
                "market": info_row.get('market', ''),
                "list_date": info_row.get('list_date', '')
            }
            
            # 尝试获取财务数据
            try:
                # 获取最新的财务数据
                fina_data = self.pro.daily_basic(ts_code=ts_symbol, trade_date='')
                if not fina_data.empty:
                    latest_fina = fina_data.iloc[0]
                    standardized_info.update({
                        'pe': latest_fina.get('pe', 0),
                        'pb': latest_fina.get('pb', 0),
                        'total_mv': latest_fina.get('total_mv', 0),  # 总市值
                        'circ_mv': latest_fina.get('circ_mv', 0)    # 流通市值
                    })
            except Exception:
                pass  # 财务数据获取失败不影响基本信息
            
            return standardized_info
            
        except Exception as e:
            logger.error(f"Tushare获取股票信息失败 {symbol}: {e}")
            return {"symbol": symbol}


class YFinanceSource(DataSourceBase):
    """YFinance数据源（原有逻辑）"""

    def __init__(self):
        try:
            import yfinance as yf
            self.yf = yf
            logger.debug("YFinance模块导入成功")
        except ImportError:
            raise ImportError("yfinance未安装，请运行: pip install yfinance")

    def _convert_symbol_for_yfinance(self, symbol: str) -> str:
        """转换股票代码为YFinance格式"""
        # 处理带前缀的股票代码，如 SH600170.SZ -> 600170.SS
        original_symbol = symbol

        # 如果代码以SH开头，去掉SH前缀并转换后缀
        if symbol.startswith('SH') and len(symbol) > 8:
            code_part = symbol[2:8]  # 提取6位数字代码
            if code_part.isdigit():
                symbol = code_part + '.SS'  # 上海股票用.SS后缀
                logger.debug(f"转换股票代码: {original_symbol} -> {symbol}")
                return symbol

        # 如果代码以SZ开头，去掉SZ前缀并保持.SZ后缀
        if symbol.startswith('SZ') and len(symbol) > 8:
            code_part = symbol[2:8]  # 提取6位数字代码
            if code_part.isdigit():
                symbol = code_part + '.SZ'  # 深圳股票保持.SZ后缀
                logger.debug(f"转换股票代码: {original_symbol} -> {symbol}")
                return symbol

        # 如果已经是标准格式，直接返回
        return symbol
    
    def get_data_by_period(self, symbol: str, period: str) -> pd.DataFrame:
        """按时间周期获取数据"""
        try:
            yf_symbol = self._convert_symbol_for_yfinance(symbol)
            ticker = self.yf.Ticker(yf_symbol)
            data = ticker.history(period=period)
            return data
        except Exception as e:
            logger.error(f"YFinance获取数据失败 {symbol}: {e}")
            return pd.DataFrame()
    
    def get_data_by_date_range(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """按日期范围获取数据"""
        try:
            yf_symbol = self._convert_symbol_for_yfinance(symbol)
            ticker = self.yf.Ticker(yf_symbol)
            # yfinance需要YYYY-MM-DD格式
            if '-' not in start_date:
                start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            if '-' not in end_date:
                end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

            data = ticker.history(start=start_date, end=end_date)
            return data
        except Exception as e:
            logger.error(f"YFinance按日期获取数据失败 {symbol}: {e}")
            return pd.DataFrame()
    
    def get_stock_info(self, symbol: str) -> Dict:
        """获取股票基本信息"""
        try:
            yf_symbol = self._convert_symbol_for_yfinance(symbol)
            ticker = self.yf.Ticker(yf_symbol)
            info = ticker.info
            return info
        except Exception as e:
            logger.error(f"YFinance获取股票信息失败 {symbol}: {e}")
            return {"symbol": symbol}


# 创建兼容性别名
DataProvider = MultiSourceDataProvider