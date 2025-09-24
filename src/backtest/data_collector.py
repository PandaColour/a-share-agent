# -*- coding: utf-8 -*-
"""回测数据收集器"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import time
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from .backtest_database import BacktestDatabase

# 导入多数据源提供者
try:
    from src.data.multi_source_data_provider import MultiSourceDataProvider
    _use_multi_source = True
    logger = logging.getLogger(__name__)
    logger.info("回测数据收集器使用多数据源提供者")
except ImportError:
    import yfinance as yf
    _use_multi_source = False
    logger = logging.getLogger(__name__)
    logger.warning("多数据源提供者不可用，使用YFinance")

logger = logging.getLogger(__name__)

class BacktestDataCollector:
    """回测数据收集器"""
    
    def __init__(self, db_path: str = "backtest/backtest.db"):
        self.db = BacktestDatabase(db_path)
        self.data_cache = {}
        self._lock = threading.Lock()
        
        # 初始化数据提供者
        if _use_multi_source:
            try:
                self.data_provider = MultiSourceDataProvider()
                logger.info("回测数据收集器使用多数据源提供者")
            except Exception as e:
                logger.error(f"多数据源提供者初始化失败: {e}")
                self.data_provider = None
        else:
            self.data_provider = None
    
    def collect_recommendation_data(self, analysis_results: List[Dict]):
        """收集分析推荐数据"""
        logger.info(f"开始收集推荐数据，共{len(analysis_results)}条记录")
        
        recommendation_ids = []
        for result in analysis_results:
            try:
                # 只保存有效的推荐（非跳过和错误）
                if result.get('操作建议') not in ['跳过', '错误']:
                    rec_id = self.db.save_recommendation(result)
                    if rec_id:
                        recommendation_ids.append(rec_id)
                        
                        # 同时收集该股票的价格数据
                        symbol = result.get('股票代码', '')
                        if symbol:
                            self._collect_single_stock_data(symbol)
                            
            except Exception as e:
                logger.error(f"收集推荐数据失败: {e}")
        
        logger.info(f"推荐数据收集完成，保存了{len(recommendation_ids)}条有效记录")
        return recommendation_ids
    
    def _collect_single_stock_data(self, symbol: str, days_back: int = 365):
        """收集单只股票的历史数据"""
        try:
            # 检查缓存
            if symbol in self.data_cache:
                cache_time = self.data_cache[symbol].get('timestamp', datetime.min)
                if datetime.now() - cache_time < timedelta(hours=1):
                    return  # 缓存仍然有效
            
            # 获取历史数据
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            data = None
            if self.data_provider:
                # 使用多数据源提供者
                try:
                    data = self.data_provider.get_stock_data(
                        symbol,
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d')
                    )
                    if not data.empty:
                        logger.debug(f"使用多数据源获取数据: {symbol}, 数据源: {data.attrs.get('source', '未知')}")
                except Exception as e:
                    logger.warning(f"多数据源获取失败 {symbol}: {e}")
            
            # 如果多数据源失败，降级到YFinance
            if data is None or data.empty:
                if not _use_multi_source:
                    import yfinance as yf
                    ticker = yf.Ticker(symbol)
                    data = ticker.history(
                        start=start_date.strftime('%Y-%m-%d'),
                        end=end_date.strftime('%Y-%m-%d')
                    )
                    logger.debug(f"使用YFinance获取数据: {symbol}")
            
            if data is not None and not data.empty:
                # 保存到数据库
                self.db.save_price_data(symbol, data)
                
                # 更新缓存
                with self._lock:
                    self.data_cache[symbol] = {
                        'data': data,
                        'timestamp': datetime.now()
                    }
                
                logger.debug(f"收集股票数据完成: {symbol}, {len(data)}条记录")
            else:
                logger.warning(f"未获取到股票数据: {symbol}")
                
        except Exception as e:
            logger.error(f"收集股票数据失败 {symbol}: {e}")
    
    def batch_collect_price_data(self, symbols: List[str], days_back: int = 365, max_workers: int = 5):
        """批量收集多只股票的价格数据"""
        logger.info(f"开始批量收集价格数据，共{len(symbols)}只股票")
        
        start_time = time.time()
        success_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_symbol = {
                executor.submit(self._collect_single_stock_data, symbol, days_back): symbol
                for symbol in symbols
            }
            
            # 等待完成
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    future.result()  # 获取结果（会抛出异常如果有的话）
                    success_count += 1
                except Exception as e:
                    logger.error(f"批量收集失败 {symbol}: {e}")
        
        elapsed_time = time.time() - start_time
        logger.info(f"批量收集完成: {success_count}/{len(symbols)}成功, 耗时{elapsed_time:.1f}秒")
        
        return success_count
    
    def collect_recent_data_for_backtest(self, recommendation_id: int, symbol: str, 
                                       analysis_date: str, days_forward: int = 30):
        """为特定推荐收集后续数据用于回测"""
        try:
            # 解析分析日期
            analysis_dt = datetime.strptime(analysis_date.split()[0], '%Y-%m-%d')
            
            # 计算数据收集范围
            start_date = analysis_dt
            end_date = analysis_dt + timedelta(days=days_forward)
            
            # 如果结束日期是未来，则使用当前时间
            if end_date > datetime.now():
                end_date = datetime.now()
            
            # 获取数据
            data = None
            if self.data_provider:
                # 使用多数据源提供者
                try:
                    data = self.data_provider.get_stock_data(
                        symbol,
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d')
                    )
                    if not data.empty:
                        logger.debug(f"使用多数据源获取回测数据: {symbol}, 数据源: {data.attrs.get('source', '未知')}")
                except Exception as e:
                    logger.warning(f"多数据源获取回测数据失败 {symbol}: {e}")
            
            # 如果多数据源失败，降级到YFinance
            if data is None or data.empty:
                if not _use_multi_source:
                    import yfinance as yf
                    ticker = yf.Ticker(symbol)
                    data = ticker.history(
                        start=start_date.strftime('%Y-%m-%d'),
                        end=end_date.strftime('%Y-%m-%d')
                    )
                    logger.debug(f"使用YFinance获取回测数据: {symbol}")
            
            if data is not None and not data.empty:
                # 保存价格数据
                self.db.save_price_data(symbol, data)
                logger.debug(f"收集回测数据完成: {symbol}, {len(data)}条记录")
                return True
            else:
                logger.warning(f"未获取到回测数据: {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"收集回测数据失败 {symbol}: {e}")
            return False
    
    def get_price_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取价格数据（优先从数据库获取）"""
        try:
            # 先从数据库获取
            data = self.db.get_price_data(symbol, start_date, end_date)
            
            if not data.empty:
                return data
            
            # 数据库没有，从API获取
            logger.info(f"从API获取价格数据: {symbol} {start_date} to {end_date}")
            
            data = None
            if self.data_provider:
                # 使用多数据源提供者
                try:
                    data = self.data_provider.get_stock_data(symbol, start_date, end_date)
                    if not data.empty:
                        logger.debug(f"使用多数据源获取价格数据: {symbol}, 数据源: {data.attrs.get('source', '未知')}")
                except Exception as e:
                    logger.warning(f"多数据源获取价格数据失败 {symbol}: {e}")
            
            # 如果多数据源失败，降级到YFinance
            if data is None or data.empty:
                if not _use_multi_source:
                    import yfinance as yf
                    ticker = yf.Ticker(symbol)
                    data = ticker.history(start=start_date, end=end_date)
                    logger.debug(f"使用YFinance获取价格数据: {symbol}")
            
            if data is not None and not data.empty:
                # 保存到数据库
                self.db.save_price_data(symbol, data)
            else:
                data = pd.DataFrame()
            
            return data
            
        except Exception as e:
            logger.error(f"获取价格数据失败 {symbol}: {e}")
            return pd.DataFrame()
    
    def update_missing_data(self):
        """更新缺失的价格数据"""
        logger.info("开始更新缺失的价格数据")
        
        try:
            # 获取所有有推荐但没有足够价格数据的股票
            recommendations = self.db.get_recommendations()
            
            symbols_to_update = set()
            for rec in recommendations:
                symbol = rec['symbol']
                analysis_date = rec['analysis_time'].split()[0]
                
                # 检查是否有足够的后续数据
                end_date = (datetime.strptime(analysis_date, '%Y-%m-%d') + timedelta(days=30)).strftime('%Y-%m-%d')
                data = self.db.get_price_data(symbol, analysis_date, end_date)
                
                if len(data) < 20:  # 如果数据不足20条，需要更新
                    symbols_to_update.add(symbol)
            
            if symbols_to_update:
                logger.info(f"需要更新{len(symbols_to_update)}只股票的数据")
                self.batch_collect_price_data(list(symbols_to_update))
            else:
                logger.info("所有价格数据都是最新的")
                
        except Exception as e:
            logger.error(f"更新缺失数据失败: {e}")
    
    def get_data_statistics(self) -> Dict:
        """获取数据收集统计信息"""
        try:
            stats = self.db.get_database_stats()
            
            # 添加缓存统计
            stats['cached_symbols'] = len(self.data_cache)
            
            # 计算数据覆盖率
            if stats.get('recommendations', 0) > 0:
                backtest_coverage = (stats.get('backtest_results', 0) / 
                                   stats.get('recommendations', 1)) * 100
                stats['backtest_coverage'] = round(backtest_coverage, 2)
            
            return stats
            
        except Exception as e:
            logger.error(f"获取数据统计失败: {e}")
            return {}
    
    def cleanup_old_cache(self, hours: int = 24):
        """清理过期缓存"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with self._lock:
                expired_keys = [
                    key for key, value in self.data_cache.items()
                    if value.get('timestamp', datetime.min) < cutoff_time
                ]
                
                for key in expired_keys:
                    del self.data_cache[key]
            
            logger.info(f"清理过期缓存: 删除{len(expired_keys)}条缓存记录")
            
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
    
    def import_historical_results(self, results_dir: str = "outputs"):
        """导入历史分析结果"""
        logger.info(f"开始从 {results_dir} 导入历史分析结果")
        
        try:
            results_path = Path(results_dir)
            if not results_path.exists():
                logger.warning(f"结果目录不存在: {results_dir}")
                return 0
            
            imported_count = 0
            # 支持多种文件名格式
            json_files = []
            for pattern in ["analysis_*.json", "a_share_analysis_*.json"]:
                json_files.extend(list(results_path.glob(pattern)))
            
            logger.info(f"找到 {len(json_files)} 个JSON文件")
            
            for file_path in json_files:
                try:
                    import json
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 支持多种数据格式
                    results = []
                    if isinstance(data, list):
                        # 直接是结果列表
                        results = data
                    elif isinstance(data, dict):
                        # 包装在字典中
                        results = data.get('results', [])
                        if not results and 'data' in data:
                            results = data['data']
                    
                    if results:
                        logger.debug(f"文件 {file_path.name} 包含 {len(results)} 条记录")
                        rec_ids = self.collect_recommendation_data(results)
                        imported_count += len(rec_ids)
                        logger.info(f"文件导入完成: {file_path.name}, {len(rec_ids)}条有效记录")
                    else:
                        logger.warning(f"文件 {file_path.name} 没有找到有效数据")
                    
                except Exception as e:
                    logger.error(f"导入文件失败 {file_path}: {e}")
                    # 打印更详细的错误信息用于调试
                    import traceback
                    logger.debug(f"详细错误: {traceback.format_exc()}")
            
            logger.info(f"历史结果导入完成: 共导入{imported_count}条推荐记录")
            return imported_count
            
        except Exception as e:
            logger.error(f"导入历史结果失败: {e}")
            return 0