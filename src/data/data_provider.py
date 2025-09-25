# -*- coding: utf-8 -*-
"""
A股数据提供者 - 兼容性包装器
为了保持向后兼容，这个文件现在使用新的多数据源系统
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging
import os
import sys

# 导入新的多数据源提供者
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from multi_source_data_provider import MultiSourceDataProvider
    logger = logging.getLogger(__name__)
    logger.info("使用新的多数据源数据提供者")
    _use_multi_source = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("多数据源提供者不可用，使用原有的YFinance提供者")
    import yfinance as yf
    _use_multi_source = False

class AShareDataProvider:
    def __init__(self):
        self.popular_stocks = {
            "贵州茅台": "600519.SS", "招商银行": "600036.SS", "五粮液": "000858.SZ",
            "美的集团": "000333.SZ", "比亚迪": "002594.SZ", "宁德时代": "300750.SZ",
            "中国平安": "601318.SS", "中国移动": "600941.SS"
        }
        
        # 初始化多数据源提供者 (如果可用)
        if _use_multi_source:
            try:
                self._multi_provider = MultiSourceDataProvider()
                logger.info("多数据源提供者初始化成功")
            except Exception as e:
                logger.error(f"多数据源提供者初始化失败: {e}")
                self._multi_provider = None
        else:
            self._multi_provider = None

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

    def get_stock_data(self, symbol: str, start_date: str = None, end_date: str = None, period: str = "1y") -> Tuple[pd.DataFrame, Dict, Dict, Dict]:
        """
        获取股票完整数据 - 增强版，支持多数据源
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD) 
            period: 时间周期 (当start_date和end_date为None时使用)
        
        Returns:
            Tuple[data, info, indicators, price_info]
        """
        try:
            # 优先使用多数据源提供者
            if self._multi_provider:
                return self._multi_provider.get_complete_stock_data(symbol, start_date, end_date, period)
            
            # 降级到原有的YFinance实现
            logger.debug(f"使用YFinance获取 {symbol} 数据")
            return self._get_stock_data_yfinance(symbol, start_date, end_date, period)
            
        except Exception as e:
            logger.error(f"获取股票数据失败 {symbol}: {e}")
            return pd.DataFrame(), {}, {}, {}
    
    def _get_stock_data_yfinance(self, symbol: str, start_date: str = None, end_date: str = None, period: str = "1y") -> Tuple[pd.DataFrame, Dict, Dict, Dict]:
        """使用YFinance获取股票数据 (原有实现)"""
        import yfinance as yf

        # 转换股票代码格式
        yf_symbol = self._convert_symbol_for_yfinance(symbol)
        ticker = yf.Ticker(yf_symbol)
        
        # 根据参数选择获取方式
        if start_date and end_date:
            data = ticker.history(start=start_date, end=end_date)
        else:
            data = ticker.history(period=period)
        
        if data.empty:
            return pd.DataFrame(), {}, {}, {}
        
        # 获取股票信息
        try:
            info = ticker.info
        except:
            info = {"symbol": symbol}
        
        # 计算技术指标
        indicators = self.calculate_technical_indicators(data, info)
        
        # 获取价格信息
        price_info = self.get_current_price_info(data)
        
        return data, info, indicators, price_info
    
    def get_stock_info(self, symbol: str) -> Dict:
        try:
            yf_symbol = self._convert_symbol_for_yfinance(symbol)
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info
            return info
        except Exception as e:
            logger.error(f"获取股票信息失败 {symbol}: {e}")
            return {}
    
    def calculate_technical_indicators(self, data: pd.DataFrame, info: Dict = None) -> Dict:
        if data.empty:
            return {}
        
        indicators = {}
        
        try:
            # 移动平均线
            if len(data) >= 5:
                indicators['ma5'] = data['Close'].rolling(window=5).mean().iloc[-1]
            if len(data) >= 20:
                indicators['ma20'] = data['Close'].rolling(window=20).mean().iloc[-1]
            
            # RSI
            if len(data) >= 14:
                delta = data['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                indicators['rsi'] = (100 - (100 / (1 + rs))).iloc[-1]
            
            # 波动率
            if len(data) >= 20:
                indicators['volatility'] = data['Close'].pct_change().rolling(window=20).std().iloc[-1] * np.sqrt(252)
            
            # MACD指标
            if len(data) >= 26:
                macd_data = self._calculate_macd(data['Close'])
                indicators.update(macd_data)
            
            # KDJ指标  
            if len(data) >= 9:
                kdj_data = self._calculate_kdj(data)
                indicators.update(kdj_data)
            
            # 威廉指标
            if len(data) >= 14:
                williams_data = self._calculate_williams_r(data)
                indicators.update(williams_data)
            
            # CCI指标
            if len(data) >= 14:
                cci_data = self._calculate_cci(data)
                indicators.update(cci_data)
            
            # 成交量指标
            if len(data) >= 5:
                volume_data = self._calculate_volume_indicators(data, info or {})
                indicators.update(volume_data)
                
            # 价格位置
            current_price = data['Close'].iloc[-1]
            high_52w = data['High'].rolling(window=min(252, len(data))).max().iloc[-1]
            low_52w = data['Low'].rolling(window=min(252, len(data))).min().iloc[-1]
            if high_52w != low_52w:
                indicators['price_position'] = (current_price - low_52w) / (high_52w - low_52w)
            else:
                indicators['price_position'] = 0.5
                
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
        
        return indicators
    
    def _calculate_macd(self, close_prices: pd.Series, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict:
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
            
            return {
                'macd': macd_line.iloc[-1],
                'macd_signal': signal_line.iloc[-1], 
                'macd_histogram': histogram.iloc[-1]
            }
        except Exception as e:
            logger.error(f"MACD计算失败: {e}")
            return {'macd': 0, 'macd_signal': 0, 'macd_histogram': 0}
    
    def _calculate_kdj(self, data: pd.DataFrame, k_period: int = 9, d_period: int = 3, j_period: int = 3) -> Dict:
        """计算KDJ指标"""
        try:
            # 计算RSV (Raw Stochastic Value)
            low_min = data['Low'].rolling(window=k_period).min()
            high_max = data['High'].rolling(window=k_period).max()
            
            # RSV = (当前收盘价 - n日内最低价) / (n日内最高价 - n日内最低价) * 100
            rsv = ((data['Close'] - low_min) / (high_max - low_min)) * 100
            
            # K值 = RSV的移动平均
            # 使用SMA而不是EMA来计算K值
            k_values = rsv.rolling(window=d_period).mean()
            
            # D值 = K值的移动平均  
            d_values = k_values.rolling(window=j_period).mean()
            
            # J值 = 3*K - 2*D
            j_values = 3 * k_values - 2 * d_values
            
            return {
                'kdj_k': k_values.iloc[-1] if not k_values.empty else 50,
                'kdj_d': d_values.iloc[-1] if not d_values.empty else 50,
                'kdj_j': j_values.iloc[-1] if not j_values.empty else 50
            }
        except Exception as e:
            logger.error(f"KDJ计算失败: {e}")
            return {'kdj_k': 50, 'kdj_d': 50, 'kdj_j': 50}
    
    def _calculate_williams_r(self, data: pd.DataFrame, period: int = 14) -> Dict:
        """计算威廉指标(Williams %R)"""
        try:
            # 计算n日内最高价和最低价
            high_max = data['High'].rolling(window=period).max()
            low_min = data['Low'].rolling(window=period).min()
            
            # Williams %R = (最高价 - 收盘价) / (最高价 - 最低价) * (-100)
            williams_r = ((high_max - data['Close']) / (high_max - low_min)) * (-100)
            
            return {
                'williams_r': williams_r.iloc[-1] if not williams_r.empty else -50
            }
        except Exception as e:
            logger.error(f"威廉指标计算失败: {e}")
            return {'williams_r': -50}
    
    def _calculate_cci(self, data: pd.DataFrame, period: int = 14) -> Dict:
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
            
            return {
                'cci': cci.iloc[-1] if not cci.empty else 0
            }
        except Exception as e:
            logger.error(f"CCI指标计算失败: {e}")
            return {'cci': 0}
    
    def _calculate_volume_indicators(self, data: pd.DataFrame, info: Dict) -> Dict:
        """计算成交量相关指标"""
        try:
            volume_indicators = {}
            
            # 计算换手率 (需要流通股本数据)
            shares_outstanding = info.get('sharesOutstanding', 0)  # 流通股本
            if shares_outstanding > 0 and not data.empty:
                # 换手率 = 成交量 / 流通股本 * 100%
                turnover_rate = (data['Volume'].iloc[-1] / shares_outstanding) * 100
                volume_indicators['turnover_rate'] = min(turnover_rate, 100)  # 限制最大100%
            else:
                # 如果没有流通股本数据，使用相对换手率估算
                avg_volume = data['Volume'].rolling(window=20).mean().iloc[-1] if len(data) >= 20 else data['Volume'].mean()
                volume_indicators['turnover_rate'] = min((data['Volume'].iloc[-1] / avg_volume) * 2, 20)  # 相对换手率
            
            # 量价关系分析
            if len(data) >= 5:
                volume_price_relation = self._analyze_volume_price_relation(data)
                volume_indicators.update(volume_price_relation)
            
            return volume_indicators
        except Exception as e:
            logger.error(f"成交量指标计算失败: {e}")
            return {'turnover_rate': 1.0, 'volume_price_trend': 'neutral'}
    
    def _analyze_volume_price_relation(self, data: pd.DataFrame) -> Dict:
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
                
                return {
                    'volume_price_trend': volume_price_trend,
                    'volume_price_correlation': round(correlation, 3),
                    'volume_ratio': round(volume_ratio, 2)
                }
            else:
                return {
                    'volume_price_trend': 'neutral',
                    'volume_price_correlation': 0.0,
                    'volume_ratio': 1.0
                }
                
        except Exception as e:
            logger.error(f"量价关系分析失败: {e}")
            return {
                'volume_price_trend': 'neutral',
                'volume_price_correlation': 0.0,
                'volume_ratio': 1.0
            }
    
    def get_current_price_info(self, data: pd.DataFrame) -> Dict:
        """获取当前价格信息"""
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

# 向后兼容性别名
DataProvider = AShareDataProvider
