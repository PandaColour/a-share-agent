# -*- coding: utf-8 -*-
"""回测数据库管理"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import logging
from pathlib import Path
import pandas as pd
import sys

# 添加utils路径以导入股票验证器
try:
    from ..stock.stock_validator import stock_validator
except ImportError:
    try:
        from stock.stock_validator import stock_validator
    except ImportError:
        logger.warning("未找到股票验证器，数据验证功能将受限")
        stock_validator = None

logger = logging.getLogger(__name__)

class BacktestDatabase:
    """回测数据库管理器"""
    
    def __init__(self, db_path: str = "backtest/backtest.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 推荐记录表
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS recommendations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        stock_name TEXT NOT NULL,
                        recommendation TEXT NOT NULL,  -- 买入/持有/卖出
                        confidence REAL NOT NULL,      -- 信心度 0-1
                        current_price REAL NOT NULL,   -- 推荐时价格
                        analysis_time TEXT NOT NULL,   -- 分析时间
                        analyst_type TEXT NOT NULL,    -- 分析师类型
                        reasoning TEXT,                -- 决策理由
                        risk_level TEXT,              -- 风险等级
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 价格历史表
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS price_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        date TEXT NOT NULL,
                        open_price REAL,
                        high_price REAL,
                        low_price REAL,
                        close_price REAL,
                        volume INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, date)
                    )
                ''')
                
                # 回测结果表
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS backtest_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        recommendation_id INTEGER NOT NULL,
                        symbol TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        entry_date TEXT NOT NULL,
                        exit_price REAL,
                        exit_date TEXT,
                        holding_days INTEGER,
                        return_rate REAL,           -- 收益率
                        success BOOLEAN,            -- 推荐是否成功
                        period_days INTEGER,        -- 回测周期(天)
                        backtest_date TEXT NOT NULL,
                        FOREIGN KEY (recommendation_id) REFERENCES recommendations (id)
                    )
                ''')
                
                # 分析师表现表
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS analyst_performance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        analyst_type TEXT NOT NULL,
                        period_start TEXT NOT NULL,
                        period_end TEXT NOT NULL,
                        total_recommendations INTEGER,
                        successful_recommendations INTEGER,
                        success_rate REAL,
                        avg_return REAL,
                        max_return REAL,
                        min_return REAL,
                        total_return REAL,
                        sharpe_ratio REAL,
                        max_drawdown REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 创建索引
                conn.execute('CREATE INDEX IF NOT EXISTS idx_recommendations_symbol ON recommendations(symbol)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_recommendations_time ON recommendations(analysis_time)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_price_history_symbol ON price_history(symbol)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(date)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_backtest_symbol ON backtest_results(symbol)')
                
                logger.info("回测数据库初始化完成")
                
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    def save_recommendation(self, recommendation: Dict) -> int:
        """保存推荐记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO recommendations 
                    (symbol, stock_name, recommendation, confidence, current_price, 
                     analysis_time, analyst_type, reasoning, risk_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    recommendation.get('股票代码', ''),
                    recommendation.get('股票名称', ''),
                    recommendation.get('操作建议', ''),
                    float(recommendation.get('信心度', '0%').rstrip('%')) / 100,
                    float(recommendation.get('当前价格', '0元').rstrip('元')),
                    recommendation.get('分析时间', ''),
                    'multi_agent',  # 多智能体综合
                    recommendation.get('决策理由', ''),
                    recommendation.get('风险等级', '')
                ))
                
                return cursor.lastrowid
                
        except Exception as e:
            logger.error(f"保存推荐记录失败: {e}")
            return 0
    
    def save_price_data(self, symbol: str, price_data: pd.DataFrame):
        """保存价格数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                for index, row in price_data.iterrows():
                    date_str = index.strftime('%Y-%m-%d') if hasattr(index, 'strftime') else str(index)
                    
                    conn.execute('''
                        INSERT OR REPLACE INTO price_history
                        (symbol, date, open_price, high_price, low_price, close_price, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        symbol,
                        date_str,
                        float(row.get('Open', 0)),
                        float(row.get('High', 0)),
                        float(row.get('Low', 0)),
                        float(row.get('Close', 0)),
                        int(row.get('Volume', 0))
                    ))
                
                logger.debug(f"保存价格数据: {symbol}, {len(price_data)}条记录")
                
        except Exception as e:
            logger.error(f"保存价格数据失败 {symbol}: {e}")
    
    def get_recommendations(self, 
                          symbol: str = None, 
                          start_date: str = None, 
                          end_date: str = None,
                          recommendation_type: str = None) -> List[Dict]:
        """获取推荐记录 - 增强版，包含股票代码验证"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                query = "SELECT * FROM recommendations WHERE 1=1"
                params = []
                
                if symbol:
                    query += " AND symbol = ?"
                    params.append(symbol)
                
                if start_date:
                    query += " AND analysis_time >= ?"
                    params.append(start_date)
                
                if end_date:
                    query += " AND analysis_time <= ?"
                    params.append(end_date)
                
                if recommendation_type:
                    query += " AND recommendation = ?"
                    params.append(recommendation_type)
                
                query += " ORDER BY analysis_time DESC"
                
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                raw_results = [dict(row) for row in cursor.fetchall()]
                
                # 验证股票代码有效性
                if stock_validator and raw_results:
                    logger.debug("验证数据库中的股票代码...")
                    valid_results = []
                    invalid_count = 0
                    
                    for rec in raw_results:
                        if stock_validator.is_valid_stock_code(rec.get('symbol', '')):
                            valid_results.append(rec)
                        else:
                            invalid_count += 1
                            logger.debug(f"跳过无效股票: {rec.get('symbol')} - {rec.get('stock_name')}")
                    
                    if invalid_count > 0:
                        logger.info(f"从数据库结果中过滤掉 {invalid_count} 个无效股票推荐")
                    
                    return valid_results
                
                return raw_results
                
        except Exception as e:
            logger.error(f"获取推荐记录失败: {e}")
            return []
    
    def get_price_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取价格数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = '''
                    SELECT date, open_price, high_price, low_price, close_price, volume
                    FROM price_history
                    WHERE symbol = ? AND date >= ? AND date <= ?
                    ORDER BY date
                '''
                
                df = pd.read_sql_query(query, conn, params=[symbol, start_date, end_date])
                
                if not df.empty:
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                    df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                
                return df
                
        except Exception as e:
            logger.error(f"获取价格数据失败 {symbol}: {e}")
            return pd.DataFrame()
    
    def save_backtest_result(self, result: Dict) -> int:
        """保存回测结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO backtest_results
                    (recommendation_id, symbol, entry_price, entry_date, exit_price, 
                     exit_date, holding_days, return_rate, success, period_days, backtest_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    result['recommendation_id'],
                    result['symbol'],
                    result['entry_price'],
                    result['entry_date'],
                    result.get('exit_price'),
                    result.get('exit_date'),
                    result.get('holding_days'),
                    result.get('return_rate'),
                    result.get('success'),
                    result['period_days'],
                    result['backtest_date']
                ))
                
                return cursor.lastrowid
                
        except Exception as e:
            logger.error(f"保存回测结果失败: {e}")
            return 0
    
    def get_backtest_results(self, 
                           symbol: str = None,
                           period_days: int = None) -> List[Dict]:
        """获取回测结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                query = '''
                    SELECT br.*, r.stock_name, r.recommendation, r.confidence, r.reasoning
                    FROM backtest_results br
                    JOIN recommendations r ON br.recommendation_id = r.id
                    WHERE 1=1
                '''
                params = []
                
                if symbol:
                    query += " AND br.symbol = ?"
                    params.append(symbol)
                
                if period_days:
                    query += " AND br.period_days = ?"
                    params.append(period_days)
                
                query += " ORDER BY br.entry_date DESC"
                
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"获取回测结果失败: {e}")
            return []
    
    def get_database_stats(self) -> Dict:
        """获取数据库统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 统计各表记录数
                stats = {}
                
                cursor.execute("SELECT COUNT(*) FROM recommendations")
                stats['recommendations'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM price_history")
                stats['price_records'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM backtest_results")
                stats['backtest_results'] = cursor.fetchone()[0]
                
                # 获取时间范围
                cursor.execute("SELECT MIN(analysis_time), MAX(analysis_time) FROM recommendations")
                time_range = cursor.fetchone()
                if time_range[0]:
                    stats['time_range'] = {
                        'start': time_range[0],
                        'end': time_range[1]
                    }
                
                # 统计股票数量
                cursor.execute("SELECT COUNT(DISTINCT symbol) FROM recommendations")
                stats['unique_stocks'] = cursor.fetchone()[0]
                
                return stats
                
        except Exception as e:
            logger.error(f"获取数据库统计失败: {e}")
            return {}
    
    def cleanup_old_data(self, days: int = 365):
        """清理旧数据"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 清理旧的价格数据
                cursor.execute("DELETE FROM price_history WHERE date < ?", (cutoff_date,))
                price_deleted = cursor.rowcount
                
                # 清理旧的推荐记录（保留更久一些）
                old_cutoff = (datetime.now() - timedelta(days=days*2)).strftime('%Y-%m-%d')
                cursor.execute("DELETE FROM recommendations WHERE analysis_time < ?", (old_cutoff,))
                rec_deleted = cursor.rowcount
                
                logger.info(f"数据清理完成: 删除{price_deleted}条价格记录, {rec_deleted}条推荐记录")
                
        except Exception as e:
            logger.error(f"数据清理失败: {e}")