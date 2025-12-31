# -*- coding: utf-8 -*-
"""
高级回测引擎 - 更真实的交易策略回测
支持仓位管理、动态止损止盈、基准对比等功能
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import logging
import sys
import os

# 添加config路径
current_dir = os.path.dirname(os.path.abspath(__file__))
config_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'config')
sys.path.insert(0, config_dir)

try:
    from ..stock.stock_validator import stock_validator
except ImportError:
    from stock.stock_validator import stock_validator
try:
    from config_manager import get_config
except ImportError:
    def get_config():
        return None

logger = logging.getLogger(__name__)

class AdvancedBacktestEngine:
    """高级回测引擎"""
    
    def __init__(self, initial_capital: float = None, config_manager=None):
        """
        初始化回测引擎
        
        Args:
            initial_capital: 初始资金(元)
            config_manager: 配置管理器
        """
        # 使用统一配置
        self.config = config_manager or get_config()
        backtest_config = self.config.get_backtest_config() if self.config else {}
        
        # 资金管理
        capital_config = backtest_config.get('capital_management', {})
        self.initial_capital = initial_capital or capital_config.get('initial_capital', 1000000.0)
        self.current_capital = self.initial_capital
        
        # 交易成本
        cost_config = backtest_config.get('transaction_costs', {})
        self.transaction_cost_rate = cost_config.get('commission_rate', 0.0015)
        self.min_transaction_cost = cost_config.get('min_commission', 5.0)
        self.stamp_duty_rate = cost_config.get('stamp_duty_rate', 0.001)
        
        # 风险管理参数（优先使用analysis_settings，回退到backtest_settings）
        analysis_config = self.config.get_analysis_config() if self.config else {}
        analysis_risk = analysis_config.get('risk_management', {})
        
        # 如果analysis_settings没有配置，使用backtest_settings
        if not analysis_risk:
            analysis_risk = backtest_config.get('risk_management', {})
        
        self.max_position_size = capital_config.get('max_position_size', analysis_risk.get('max_position_size', 0.15))
        self.stop_loss_rate = analysis_risk.get('stop_loss_rate', -0.08)
        self.take_profit_rate = analysis_risk.get('take_profit_rate', 0.15)
        self.max_holding_days = analysis_risk.get('max_holding_days', 45)

        # 是否启用强制退出规则（止损止盈、超期持有）
        self.enable_forced_exit = analysis_risk.get('enable_forced_exit', True)

        # 回测状态
        self.positions = {}  # 当前持仓 {symbol: position_info}
        self.trade_history = []  # 交易历史
        self.daily_returns = []  # 每日收益率
        self.portfolio_values = []  # 每日组合价值

        logger.info(f"回测引擎初始化完成 - 初始资金: {self.initial_capital:.0f}元, 最大仓位: {self.max_position_size:.1%}")
        if self.enable_forced_exit:
            logger.info(f"风险管理 - 止损: {self.stop_loss_rate:.1%}, 止盈: {self.take_profit_rate:.1%}, 最大持有: {self.max_holding_days}天")
        else:
            logger.info(f"风险管理 - 完全按策略信号执行，不启用强制止损止盈")
        
    def run_strategy_backtest(self, recommendations: List[Dict], 
                            market_data: Dict[str, pd.DataFrame],
                            benchmark_data: pd.DataFrame = None) -> Dict:
        """
        运行策略回测
        
        Args:
            recommendations: 推荐列表
            market_data: 市场数据 {symbol: DataFrame}
            benchmark_data: 基准指数数据(如沪深300)
        
        Returns:
            回测结果
        """
        logger.info("开始高级回测分析")
        
        try:
            # 1. 验证推荐列表中的股票代码
            logger.info("验证股票代码有效性...")
            valid_recommendations = stock_validator.validate_recommendations(recommendations)
            
            if not valid_recommendations:
                return {"error": "没有有效的股票推荐"}
            
            if len(valid_recommendations) != len(recommendations):
                logger.warning(f"过滤掉 {len(recommendations) - len(valid_recommendations)} 个无效推荐")
            
            # 2. 重置回测状态
            self._reset_backtest_state()
            
            # 3. 按时间排序推荐
            sorted_recommendations = sorted(
                valid_recommendations, 
                key=lambda x: x.get('analysis_time', '')
            )
            
            # 获取回测时间范围
            start_date, end_date = self._get_backtest_period(sorted_recommendations)
            all_dates = pd.date_range(start=start_date, end=end_date, freq='D')
            trading_dates = [d for d in all_dates if d.weekday() < 5]  # 工作日
            
            # 逐日执行回测
            for current_date in trading_dates:
                self._process_trading_day(
                    current_date, sorted_recommendations, market_data
                )
            
            # 强制平仓所有持仓
            self._close_all_positions(trading_dates[-1], market_data)
            
            # 计算回测结果
            results = self._calculate_backtest_results(benchmark_data)
            
            logger.info(f"回测完成: 最终收益率 {results['total_return']:.2%}")
            return results
            
        except Exception as e:
            logger.error(f"高级回测失败: {e}")
            return {"error": str(e)}
    
    def _reset_backtest_state(self):
        """重置回测状态"""
        self.current_capital = self.initial_capital
        self.positions = {}
        self.trade_history = []
        self.daily_returns = []
        self.portfolio_values = []
    
    def _process_trading_day(self, current_date: pd.Timestamp, 
                           recommendations: List[Dict], 
                           market_data: Dict[str, pd.DataFrame]):
        """处理单个交易日"""
        date_str = current_date.strftime('%Y-%m-%d')
        
        # 1. 处理当日的新推荐
        today_recommendations = [
            rec for rec in recommendations
            if rec.get('analysis_time', '')[:10] == date_str
        ]
        
        for rec in today_recommendations:
            self._process_recommendation(rec, current_date, market_data)
        
        # 2. 更新现有持仓
        self._update_positions(current_date, market_data)

        # 3. 检查止损止盈（仅在启用强制退出时）
        if self.enable_forced_exit:
            self._check_stop_conditions(current_date, market_data)

        # 4. 检查超期持仓（仅在启用强制退出时）
        if self.enable_forced_exit:
            self._check_max_holding_period(current_date, market_data)
        
        # 5. 计算当日组合价值
        portfolio_value = self._calculate_portfolio_value(current_date, market_data)
        self.portfolio_values.append({
            'date': date_str,
            'portfolio_value': portfolio_value,
            'cash': self.current_capital,
            'positions_value': portfolio_value - self.current_capital
        })
        
        # 6. 计算当日收益率
        if len(self.portfolio_values) > 1:
            prev_value = self.portfolio_values[-2]['portfolio_value']
            daily_return = (portfolio_value - prev_value) / prev_value
            self.daily_returns.append({
                'date': date_str,
                'daily_return': daily_return
            })
    
    def _process_recommendation(self, recommendation: Dict, current_date: pd.Timestamp,
                              market_data: Dict[str, pd.DataFrame]):
        """处理推荐信号"""
        symbol = recommendation['symbol']
        rec_type = recommendation.get('recommendation', '持有')
        confidence = recommendation.get('confidence', 0.5)
        
        if symbol not in market_data:
            logger.warning(f"缺少{symbol}的市场数据")
            return
        
        stock_data = market_data[symbol]
        date_str = current_date.strftime('%Y-%m-%d')
        
        # 获取当日价格数据
        if date_str not in stock_data.index.strftime('%Y-%m-%d'):
            return
        
        daily_data = stock_data.loc[stock_data.index.strftime('%Y-%m-%d') == date_str]
        if daily_data.empty:
            return
            
        current_price = daily_data.iloc[0]['Close']
        
        # 根据推荐类型执行操作
        if rec_type == "买入":
            self._execute_buy_signal(
                symbol, current_price, current_date, confidence, recommendation
            )
        elif rec_type == "卖出" and symbol in self.positions:
            self._execute_sell_signal(
                symbol, current_price, current_date, "主动卖出"
            )
    
    def _execute_buy_signal(self, symbol: str, price: float, date: pd.Timestamp,
                          confidence: float, recommendation: Dict):
        """执行买入信号"""
        # 检查是否已有持仓
        if symbol in self.positions:
            # 记录持仓期间出现的重复买点
            if 'missed_buy_signals' not in self.positions[symbol]:
                self.positions[symbol]['missed_buy_signals'] = []

            self.positions[symbol]['missed_buy_signals'].append({
                'date': date.strftime('%Y-%m-%d'),
                'price': price,
                'confidence': confidence,
                'days_since_entry': (date - self.positions[symbol]['entry_date']).days
            })

            logger.info(f"⚠️ {symbol} 持仓期间出现重复买点 - 价格:{price:.2f}, 信心度:{confidence:.2%}, "
                       f"持仓天数:{(date - self.positions[symbol]['entry_date']).days}天")
            return
        
        # 计算仓位大小 (基于信心度调整)
        base_position_size = self.max_position_size * confidence
        portfolio_value = self._calculate_current_portfolio_value(date)
        
        position_value = portfolio_value * base_position_size
        shares = int(position_value / price / 100) * 100  # A股最小交易单位100股
        
        if shares < 100:  # 不足一手
            logger.debug(f"{symbol} 资金不足一手，跳过买入")
            return
        
        # 计算实际交易金额和成本
        actual_value = shares * price
        transaction_cost = max(
            actual_value * self.transaction_cost_rate, 
            self.min_transaction_cost
        )
        total_cost = actual_value + transaction_cost
        
        if total_cost > self.current_capital:
            logger.debug(f"{symbol} 资金不足，跳过买入")
            return
        
        # 执行买入
        self.current_capital -= total_cost
        
        position = {
            'symbol': symbol,
            'shares': shares,
            'entry_price': price,
            'entry_date': date,
            'current_price': price,
            'position_value': actual_value,
            'transaction_cost': transaction_cost,
            'confidence': confidence,
            'recommendation': recommendation
        }
        
        self.positions[symbol] = position
        
        # 记录交易
        trade = {
            'date': date.strftime('%Y-%m-%d'),
            'symbol': symbol,
            'action': '买入',
            'shares': shares,
            'price': price,
            'value': actual_value,
            'transaction_cost': transaction_cost,
            'reason': '策略买入信号'
        }
        self.trade_history.append(trade)
        
        logger.info(f"{date.strftime('%Y-%m-%d')} 买入 {symbol} {shares}股 @{price:.2f}元")
    
    def _execute_sell_signal(self, symbol: str, price: float, 
                           date: pd.Timestamp, reason: str):
        """执行卖出信号"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        shares = position['shares']
        
        # 计算交易金额和成本
        actual_value = shares * price
        transaction_cost = max(
            actual_value * self.transaction_cost_rate, 
            self.min_transaction_cost
        )
        stamp_duty = actual_value * self.stamp_duty_rate  # 印花税
        total_cost = transaction_cost + stamp_duty
        net_proceeds = actual_value - total_cost
        
        # 更新资金
        self.current_capital += net_proceeds
        
        # 计算收益
        entry_cost = position['shares'] * position['entry_price'] + position['transaction_cost']
        profit = net_proceeds - entry_cost
        return_rate = profit / entry_cost
        
        # 记录交易（包含持仓期间的重复买点信息）
        trade = {
            'date': date.strftime('%Y-%m-%d'),
            'symbol': symbol,
            'action': '卖出',
            'shares': shares,
            'price': price,
            'value': actual_value,
            'transaction_cost': total_cost,
            'profit': profit,
            'return_rate': return_rate,
            'holding_days': (date - position['entry_date']).days,
            'reason': reason,
            'missed_buy_signals': position.get('missed_buy_signals', [])  # 记录持仓期间的重复买点
        }
        self.trade_history.append(trade)
        
        # 移除持仓
        del self.positions[symbol]
        
        logger.info(f"{date.strftime('%Y-%m-%d')} 卖出 {symbol} {shares}股 @{price:.2f}元, "
                   f"收益率: {return_rate:.2%}")
    
    def _update_positions(self, date: pd.Timestamp, market_data: Dict[str, pd.DataFrame]):
        """更新持仓价格"""
        date_str = date.strftime('%Y-%m-%d')
        
        for symbol, position in self.positions.items():
            if symbol in market_data:
                stock_data = market_data[symbol]
                if date_str in stock_data.index.strftime('%Y-%m-%d'):
                    daily_data = stock_data.loc[stock_data.index.strftime('%Y-%m-%d') == date_str]
                    if not daily_data.empty:
                        current_price = daily_data.iloc[0]['Close']
                        position['current_price'] = current_price
                        position['position_value'] = position['shares'] * current_price
    
    def _check_stop_conditions(self, date: pd.Timestamp, market_data: Dict[str, pd.DataFrame]):
        """检查止损止盈条件"""
        symbols_to_sell = []
        
        for symbol, position in self.positions.items():
            entry_price = position['entry_price']
            current_price = position['current_price']
            
            return_rate = (current_price - entry_price) / entry_price
            
            # 检查止损
            if return_rate <= self.stop_loss_rate:
                symbols_to_sell.append((symbol, "止损"))
            
            # 检查止盈
            elif return_rate >= self.take_profit_rate:
                symbols_to_sell.append((symbol, "止盈"))
        
        # 执行卖出
        for symbol, reason in symbols_to_sell:
            self._execute_sell_signal(symbol, self.positions[symbol]['current_price'], date, reason)
    
    def _check_max_holding_period(self, date: pd.Timestamp, market_data: Dict[str, pd.DataFrame]):
        """检查最大持有期限"""
        symbols_to_sell = []
        
        for symbol, position in self.positions.items():
            holding_days = (date - position['entry_date']).days
            
            if holding_days >= self.max_holding_days:
                symbols_to_sell.append((symbol, f"超期持有({holding_days}天)"))
        
        # 执行卖出
        for symbol, reason in symbols_to_sell:
            self._execute_sell_signal(symbol, self.positions[symbol]['current_price'], date, reason)
    
    def _close_all_positions(self, date: pd.Timestamp, market_data: Dict[str, pd.DataFrame]):
        """强制平仓所有持仓"""
        symbols_to_sell = list(self.positions.keys())
        
        for symbol in symbols_to_sell:
            self._execute_sell_signal(symbol, self.positions[symbol]['current_price'], 
                                   date, "回测结束强制平仓")
    
    def _calculate_portfolio_value(self, date: pd.Timestamp, market_data: Dict[str, pd.DataFrame]) -> float:
        """计算组合总价值"""
        total_value = self.current_capital
        
        for symbol, position in self.positions.items():
            total_value += position['position_value']
        
        return total_value
    
    def _calculate_current_portfolio_value(self, date: pd.Timestamp) -> float:
        """计算当前组合价值（用于仓位计算）"""
        if self.portfolio_values:
            return self.portfolio_values[-1]['portfolio_value']
        return self.initial_capital
    
    def _get_backtest_period(self, recommendations: List[Dict]) -> Tuple[str, str]:
        """获取回测时间范围"""
        if not recommendations:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            return start_date, end_date
        
        dates = [rec.get('analysis_time', '')[:10] for rec in recommendations]
        dates = [d for d in dates if d]  # 过滤空日期
        
        start_date = min(dates)
        end_date = max(dates)
        
        # 延长结束时间以完成持仓
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=self.max_holding_days)
        end_date = min(end_dt, datetime.now()).strftime('%Y-%m-%d')
        
        return start_date, end_date
    
    def _calculate_backtest_results(self, benchmark_data: pd.DataFrame = None) -> Dict:
        """计算回测结果统计"""
        if not self.portfolio_values:
            return {"error": "没有回测数据"}
        
        # 基础统计
        final_value = self.portfolio_values[-1]['portfolio_value']
        total_return = (final_value - self.initial_capital) / self.initial_capital
        
        # 日收益率统计
        returns = [r['daily_return'] for r in self.daily_returns]
        
        # 风险指标
        if returns:
            avg_daily_return = np.mean(returns)
            volatility = np.std(returns)
            
            # 年化指标
            trading_days = len(returns)
            annualized_return = (1 + total_return) ** (252 / trading_days) - 1 if trading_days > 0 else 0
            annualized_volatility = volatility * np.sqrt(252)
            
            # 夏普比率 (假设无风险利率3%)
            risk_free_rate = 0.03
            sharpe_ratio = (annualized_return - risk_free_rate) / annualized_volatility if annualized_volatility > 0 else 0
            
            # 最大回撤
            portfolio_values = [pv['portfolio_value'] for pv in self.portfolio_values]
            rolling_max = np.maximum.accumulate(portfolio_values)
            drawdowns = (np.array(portfolio_values) - rolling_max) / rolling_max
            max_drawdown = np.min(drawdowns)
        else:
            avg_daily_return = annualized_return = annualized_volatility = 0
            sharpe_ratio = max_drawdown = 0
        
        # 交易统计
        total_trades = len(self.trade_history)
        buy_trades = [t for t in self.trade_history if t['action'] == '买入']
        sell_trades = [t for t in self.trade_history if t['action'] == '卖出']
        
        successful_trades = [t for t in sell_trades if t.get('profit', 0) > 0]
        win_rate = len(successful_trades) / len(sell_trades) if sell_trades else 0
        
        # 基准对比
        benchmark_stats = {}
        if benchmark_data is not None and not benchmark_data.empty:
            benchmark_stats = self._calculate_benchmark_comparison(benchmark_data)
        
        results = {
            # 收益指标
            "total_return": total_return,
            "annualized_return": annualized_return,
            "initial_capital": self.initial_capital,
            "final_capital": final_value,
            "profit": final_value - self.initial_capital,
            
            # 风险指标
            "volatility": annualized_volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            
            # 交易统计
            "total_trades": total_trades,
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "win_rate": win_rate,
            "avg_holding_days": np.mean([t.get('holding_days', 0) for t in sell_trades]) if sell_trades else 0,
            
            # 详细数据
            "daily_returns": returns,
            "portfolio_values": self.portfolio_values,
            "trade_history": self.trade_history,
            "benchmark_comparison": benchmark_stats
        }
        
        return results
    
    def _calculate_benchmark_comparison(self, benchmark_data: pd.DataFrame) -> Dict:
        """计算基准对比"""
        try:
            if self.portfolio_values and not benchmark_data.empty:
                # 对齐时间序列
                portfolio_dates = [pv['date'] for pv in self.portfolio_values]
                
                benchmark_returns = []
                for i, date in enumerate(portfolio_dates):
                    if date in benchmark_data.index.strftime('%Y-%m-%d'):
                        if i == 0:
                            benchmark_returns.append(0)
                        else:
                            prev_date = portfolio_dates[i-1]
                            if prev_date in benchmark_data.index.strftime('%Y-%m-%d'):
                                curr_price = benchmark_data.loc[benchmark_data.index.strftime('%Y-%m-%d') == date, 'Close'].iloc[0]
                                prev_price = benchmark_data.loc[benchmark_data.index.strftime('%Y-%m-%d') == prev_date, 'Close'].iloc[0]
                                benchmark_return = (curr_price - prev_price) / prev_price
                                benchmark_returns.append(benchmark_return)
                
                if benchmark_returns:
                    benchmark_total_return = np.prod(1 + np.array(benchmark_returns)) - 1
                    alpha = (1 + self.daily_returns[-1]['daily_return']) / (1 + benchmark_total_return) - 1
                    
                    return {
                        "benchmark_total_return": benchmark_total_return,
                        "alpha": alpha,
                        "outperform": alpha > 0
                    }
            
            return {}
            
        except Exception as e:
            logger.error(f"基准对比计算失败: {e}")
            return {}