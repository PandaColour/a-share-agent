# -*- coding: utf-8 -*-
"""回测分析引擎"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import logging

from .backtest_database import BacktestDatabase
from .data_collector import BacktestDataCollector

logger = logging.getLogger(__name__)

class BacktestEngine:
    """回测分析引擎"""
    
    def __init__(self, db_path: str = "backtest/backtest.db"):
        self.db = BacktestDatabase(db_path)
        self.data_collector = BacktestDataCollector(db_path)
        
        # 回测配置
        self.transaction_cost = 0.0015  # 交易成本(0.15%)
        self.min_holding_days = 1       # 最小持有天数
        self.max_holding_days = 30      # 最大持有天数
    
    def run_backtest(self, start_date: str = None, end_date: str = None, 
                    period_days: int = 30) -> Dict:
        """执行回测分析"""
        logger.info(f"开始执行回测分析，周期{period_days}天")
        
        try:
            # 获取推荐记录
            recommendations = self.db.get_recommendations(
                start_date=start_date, 
                end_date=end_date
            )
            
            if not recommendations:
                logger.warning("没有找到推荐记录")
                return {"error": "没有推荐记录"}
            
            logger.info(f"找到{len(recommendations)}条推荐记录")
            
            results = []
            success_count = 0
            
            for rec in recommendations:
                try:
                    result = self._backtest_single_recommendation(rec, period_days)
                    if result:
                        results.append(result)
                        if result.get('success'):
                            success_count += 1
                        
                        # 保存回测结果
                        self.db.save_backtest_result(result)
                        
                except Exception as e:
                    logger.error(f"回测推荐{rec['id']}失败: {e}")
            
            # 计算整体统计
            summary = self._calculate_backtest_summary(results)
            
            logger.info(f"回测完成: {len(results)}条记录，成功率{summary.get('success_rate', 0):.2f}%")
            
            return {
                "summary": summary,
                "results": results,
                "total_recommendations": len(recommendations),
                "backtest_results": len(results),
                "success_count": success_count
            }
            
        except Exception as e:
            logger.error(f"回测分析失败: {e}")
            return {"error": str(e)}
    
    def _backtest_single_recommendation(self, recommendation: Dict, period_days: int) -> Dict:
        """回测单个推荐"""
        try:
            symbol = recommendation['symbol']
            entry_date = recommendation['analysis_time'].split()[0]  # 获取日期部分
            entry_price = recommendation['current_price']
            recommendation_type = recommendation['recommendation']
            
            # 计算退出日期
            entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
            exit_dt = entry_dt + timedelta(days=period_days)
            exit_date = exit_dt.strftime('%Y-%m-%d')
            
            # 获取价格数据
            price_data = self.data_collector.get_price_data(
                symbol, entry_date, exit_date
            )
            
            if price_data.empty:
                logger.warning(f"未获取到{symbol}的价格数据")
                return None
            
            # 确保数据完整性
            if len(price_data) < self.min_holding_days:
                logger.warning(f"{symbol}价格数据不足{self.min_holding_days}天")
                return None
            
            # 计算回测结果
            result = self._calculate_returns(
                recommendation, price_data, entry_price, entry_date, period_days
            )
            
            return result
            
        except Exception as e:
            logger.error(f"单个推荐回测失败: {e}")
            return None
    
    def _calculate_returns(self, recommendation: Dict, price_data: pd.DataFrame,
                          entry_price: float, entry_date: str, period_days: int) -> Dict:
        """计算收益率"""
        try:
            symbol = recommendation['symbol']
            recommendation_type = recommendation['recommendation']
            
            # 获取实际入场价格（下一交易日开盘价）
            if len(price_data) == 0:
                return None
                
            actual_entry_price = price_data.iloc[0]['Open'] if len(price_data) > 0 else entry_price
            
            # 获取出场价格（最后一日收盘价）
            exit_price = price_data.iloc[-1]['Close']
            exit_date = price_data.index[-1].strftime('%Y-%m-%d')
            
            # 计算持有天数
            holding_days = len(price_data)
            
            # 根据推荐类型计算收益率
            if recommendation_type == "买入":
                # 买入策略：计算持有收益
                gross_return = (exit_price - actual_entry_price) / actual_entry_price
                net_return = gross_return - self.transaction_cost  # 扣除交易成本
                success = net_return > 0
                
            elif recommendation_type.startswith("卖出"):
                # 卖出策略：反向计算收益（做空收益）
                gross_return = (actual_entry_price - exit_price) / actual_entry_price
                net_return = gross_return - self.transaction_cost
                success = net_return > 0
                
            else:  # 持有
                # 持有策略：基准收益
                gross_return = (exit_price - actual_entry_price) / actual_entry_price
                net_return = gross_return  # 持有不产生交易成本
                success = abs(net_return) < 0.02  # 持有成功定义为波动小于2%
            
            # 计算期间最大收益和最大亏损
            max_price = price_data['High'].max()
            min_price = price_data['Low'].min()
            
            max_gain = (max_price - actual_entry_price) / actual_entry_price
            max_loss = (min_price - actual_entry_price) / actual_entry_price
            
            result = {
                "recommendation_id": recommendation['id'],
                "symbol": symbol,
                "entry_price": actual_entry_price,
                "entry_date": entry_date,
                "exit_price": exit_price,
                "exit_date": exit_date,
                "holding_days": holding_days,
                "return_rate": net_return,
                "gross_return": gross_return,
                "success": success,
                "period_days": period_days,
                "backtest_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "max_gain": max_gain,
                "max_loss": max_loss,
                "recommendation_type": recommendation_type,
                "confidence": recommendation['confidence'],
                "stock_name": recommendation['stock_name']
            }
            
            return result
            
        except Exception as e:
            logger.error(f"计算收益率失败: {e}")
            return None
    
    def _calculate_backtest_summary(self, results: List[Dict]) -> Dict:
        """计算回测汇总统计"""
        if not results:
            return {}
        
        try:
            # 基础统计
            total_count = len(results)
            success_count = sum(1 for r in results if r.get('success', False))
            success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
            
            # 收益率统计
            returns = [r['return_rate'] for r in results if r.get('return_rate') is not None]
            
            if returns:
                avg_return = np.mean(returns)
                median_return = np.median(returns)
                std_return = np.std(returns)
                max_return = np.max(returns)
                min_return = np.min(returns)
                
                # 计算夏普比率（假设无风险利率为3%年化）
                risk_free_rate = 0.03 / 365 * np.mean([r.get('holding_days', 30) for r in results])
                sharpe_ratio = (avg_return - risk_free_rate) / std_return if std_return > 0 else 0
                
                # 最大回撤
                cumulative_returns = np.cumprod(1 + np.array(returns))
                rolling_max = np.maximum.accumulate(cumulative_returns)
                drawdowns = (cumulative_returns - rolling_max) / rolling_max
                max_drawdown = np.min(drawdowns) if len(drawdowns) > 0 else 0
            else:
                avg_return = median_return = std_return = max_return = min_return = 0
                sharpe_ratio = max_drawdown = 0
            
            # 按推荐类型统计
            by_recommendation = {}
            for rec_type in ["买入", "持有", "卖出"]:
                type_results = [r for r in results if r.get('recommendation_type') == rec_type]
                if type_results:
                    type_success = sum(1 for r in type_results if r.get('success', False))
                    type_returns = [r['return_rate'] for r in type_results]
                    
                    by_recommendation[rec_type] = {
                        "count": len(type_results),
                        "success_count": type_success,
                        "success_rate": (type_success / len(type_results)) * 100,
                        "avg_return": np.mean(type_returns) if type_returns else 0,
                        "total_return": sum(type_returns) if type_returns else 0
                    }
            
            # 按持有期统计
            holding_periods = {}
            for days in [7, 15, 30]:
                period_results = [r for r in results if r.get('holding_days', 0) <= days]
                if period_results:
                    period_success = sum(1 for r in period_results if r.get('success', False))
                    period_returns = [r['return_rate'] for r in period_results]
                    
                    holding_periods[f"{days}天内"] = {
                        "count": len(period_results),
                        "success_rate": (period_success / len(period_results)) * 100,
                        "avg_return": np.mean(period_returns) if period_returns else 0
                    }
            
            summary = {
                "backtest_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_recommendations": total_count,
                "successful_recommendations": success_count,
                "success_rate": success_rate,
                "avg_return": avg_return,
                "median_return": median_return,
                "std_return": std_return,
                "max_return": max_return,
                "min_return": min_return,
                "total_return": sum(returns) if returns else 0,
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_drawdown,
                "by_recommendation_type": by_recommendation,
                "by_holding_period": holding_periods,
                "avg_holding_days": np.mean([r.get('holding_days', 0) for r in results])
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"计算回测汇总失败: {e}")
            return {}
    
    def get_analyst_performance(self, analyst_type: str = None, 
                              start_date: str = None, end_date: str = None) -> Dict:
        """获取分析师表现"""
        try:
            backtest_results = self.db.get_backtest_results()
            
            if analyst_type:
                # 这里需要通过recommendation_id关联获取analyst_type
                recommendations = self.db.get_recommendations()
                rec_map = {r['id']: r for r in recommendations}
                backtest_results = [
                    r for r in backtest_results 
                    if rec_map.get(r['recommendation_id'], {}).get('analyst_type') == analyst_type
                ]
            
            if not backtest_results:
                return {"error": "没有找到回测结果"}
            
            # 计算表现指标
            performance = self._calculate_backtest_summary(backtest_results)
            
            return {
                "analyst_type": analyst_type or "all",
                "performance": performance,
                "period": {
                    "start": start_date,
                    "end": end_date
                }
            }
            
        except Exception as e:
            logger.error(f"获取分析师表现失败: {e}")
            return {"error": str(e)}
    
    def generate_backtest_report(self, backtest_results: Dict, save_path: str = None) -> str:
        """生成回测报告"""
        try:
            from datetime import datetime
            
            report_lines = []
            report_lines.append("=" * 60)
            report_lines.append("📊 A股TradingAgents回测分析报告")
            report_lines.append("=" * 60)
            
            summary = backtest_results.get('summary', {})
            results = backtest_results.get('results', [])
            
            # 基础统计
            report_lines.append(f"\n📈 回测概览:")
            report_lines.append(f"  总推荐数量: {summary.get('total_recommendations', 0)}")
            report_lines.append(f"  成功推荐数量: {summary.get('successful_recommendations', 0)}")
            report_lines.append(f"  成功率: {summary.get('success_rate', 0):.2f}%")
            report_lines.append(f"  平均收益率: {summary.get('avg_return', 0)*100:.2f}%")
            report_lines.append(f"  总收益率: {summary.get('total_return', 0)*100:.2f}%")
            
            # 风险指标
            report_lines.append(f"\n📊 风险指标:")
            report_lines.append(f"  收益率标准差: {summary.get('std_return', 0)*100:.2f}%")
            report_lines.append(f"  最大收益率: {summary.get('max_return', 0)*100:.2f}%")
            report_lines.append(f"  最大亏损率: {summary.get('min_return', 0)*100:.2f}%")
            report_lines.append(f"  夏普比率: {summary.get('sharpe_ratio', 0):.3f}")
            report_lines.append(f"  最大回撤: {summary.get('max_drawdown', 0)*100:.2f}%")
            
            # 按推荐类型统计
            by_type = summary.get('by_recommendation_type', {})
            if by_type:
                report_lines.append(f"\n📋 按推荐类型统计:")
                for rec_type, stats in by_type.items():
                    report_lines.append(f"  {rec_type}:")
                    report_lines.append(f"    数量: {stats['count']}")
                    report_lines.append(f"    成功率: {stats['success_rate']:.2f}%")
                    report_lines.append(f"    平均收益: {stats['avg_return']*100:.2f}%")
            
            # 生成时间
            report_lines.append(f"\n⏰ 报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("=" * 60)
            
            report_content = "\n".join(report_lines)
            
            # 保存报告
            if save_path:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                logger.info(f"回测报告已保存到: {save_path}")
            
            return report_content
            
        except Exception as e:
            logger.error(f"生成回测报告失败: {e}")
            return f"生成报告失败: {e}"