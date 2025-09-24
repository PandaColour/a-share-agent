# -*- coding: utf-8 -*-
"""回测管理器"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from .backtest_database import BacktestDatabase
from .data_collector import BacktestDataCollector
from .backtest_engine import BacktestEngine

logger = logging.getLogger(__name__)

class BacktestManager:
    """回测管理器 - 统一管理回测功能"""
    
    def __init__(self, db_path: str = "backtest/backtest.db"):
        self.db_path = db_path
        self.db = BacktestDatabase(db_path)
        self.data_collector = BacktestDataCollector(db_path)
        self.engine = BacktestEngine(db_path)
        
        # 创建输出目录
        self.backtest_output_dir = Path("backtest_results")
        self.backtest_output_dir.mkdir(exist_ok=True)
    
    def import_analysis_results(self, analysis_results: List[Dict]) -> int:
        """导入分析结果到回测系统"""
        logger.info(f"导入{len(analysis_results)}条分析结果到回测系统")
        
        try:
            imported_count = 0
            
            for result in analysis_results:
                # 只导入有效的推荐
                if result.get('操作建议') not in ['跳过', '错误']:
                    rec_id = self.data_collector.collect_recommendation_data([result])
                    if rec_id:
                        imported_count += len(rec_id)
            
            logger.info(f"成功导入{imported_count}条推荐记录")
            return imported_count
            
        except Exception as e:
            logger.error(f"导入分析结果失败: {e}")
            return 0
    
    def collect_price_data_for_backtest(self, days_back: int = 365) -> Dict:
        """为回测收集价格数据"""
        logger.info("开始为回测收集价格数据")
        
        try:
            # 获取所有需要价格数据的股票
            recommendations = self.db.get_recommendations()
            symbols = list(set([rec['symbol'] for rec in recommendations]))
            
            if not symbols:
                logger.warning("没有找到需要收集数据的股票")
                return {"success": 0, "total": 0}
            
            # 批量收集价格数据
            success_count = self.data_collector.batch_collect_price_data(
                symbols, days_back=days_back
            )
            
            result = {
                "success": success_count,
                "total": len(symbols),
                "success_rate": (success_count / len(symbols)) * 100 if symbols else 0
            }
            
            logger.info(f"价格数据收集完成: {success_count}/{len(symbols)}成功")
            return result
            
        except Exception as e:
            logger.error(f"收集价格数据失败: {e}")
            return {"success": 0, "total": 0, "error": str(e)}
    
    def run_full_backtest(self, period_days: int = 30, 
                         start_date: str = None, end_date: str = None) -> Dict:
        """执行完整回测分析"""
        logger.info(f"开始执行完整回测分析，周期{period_days}天")
        
        try:
            # 1. 更新缺失的价格数据
            logger.info("第1步: 更新价格数据")
            self.data_collector.update_missing_data()
            
            # 2. 执行回测
            logger.info("第2步: 执行回测分析")
            backtest_results = self.engine.run_backtest(
                start_date=start_date,
                end_date=end_date,
                period_days=period_days
            )
            
            if "error" in backtest_results:
                return backtest_results
            
            # 3. 生成报告
            logger.info("第3步: 生成回测报告")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 保存详细结果
            results_file = self.backtest_output_dir / f"backtest_results_{timestamp}.json"
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(backtest_results, f, ensure_ascii=False, indent=2, default=str)
            
            # 生成文本报告
            report_file = self.backtest_output_dir / f"backtest_report_{timestamp}.txt"
            report_content = self.engine.generate_backtest_report(
                backtest_results, str(report_file)
            )
            
            # 4. 保存CSV格式结果
            self._save_results_to_csv(backtest_results, timestamp)
            
            result = {
                "backtest_results": backtest_results,
                "files": {
                    "results_json": str(results_file),
                    "report_txt": str(report_file),
                    "results_csv": str(self.backtest_output_dir / f"backtest_results_{timestamp}.csv")
                },
                "summary": backtest_results.get('summary', {}),
                "timestamp": timestamp
            }
            
            logger.info(f"回测分析完成，结果保存到: {results_file}")
            return result
            
        except Exception as e:
            logger.error(f"完整回测分析失败: {e}")
            return {"error": str(e)}
    
    def _save_results_to_csv(self, backtest_results: Dict, timestamp: str):
        """保存结果到CSV格式"""
        try:
            import pandas as pd
            
            results = backtest_results.get('results', [])
            if not results:
                return
            
            # 转换为DataFrame
            df_data = []
            for result in results:
                df_data.append({
                    '股票代码': result.get('symbol', ''),
                    '股票名称': result.get('stock_name', ''),
                    '推荐类型': result.get('recommendation_type', ''),
                    '信心度': f"{result.get('confidence', 0)*100:.1f}%",
                    '入场价格': f"{result.get('entry_price', 0):.2f}元",
                    '入场日期': result.get('entry_date', ''),
                    '出场价格': f"{result.get('exit_price', 0):.2f}元",
                    '出场日期': result.get('exit_date', ''),
                    '持有天数': result.get('holding_days', 0),
                    '收益率': f"{result.get('return_rate', 0)*100:.2f}%",
                    '最大收益': f"{result.get('max_gain', 0)*100:.2f}%",
                    '最大亏损': f"{result.get('max_loss', 0)*100:.2f}%",
                    '是否成功': '是' if result.get('success') else '否',
                    '回测日期': result.get('backtest_date', '')
                })
            
            df = pd.DataFrame(df_data)
            csv_file = self.backtest_output_dir / f"backtest_results_{timestamp}.csv"
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            
            logger.debug(f"CSV结果已保存: {csv_file}")
            
        except Exception as e:
            logger.error(f"保存CSV失败: {e}")
    
    def get_backtest_statistics(self) -> Dict:
        """获取回测统计信息"""
        try:
            stats = self.data_collector.get_data_statistics()
            
            # 添加回测特定统计
            backtest_results = self.db.get_backtest_results()
            if backtest_results:
                recent_results = sorted(backtest_results, 
                                      key=lambda x: x.get('backtest_date', ''), 
                                      reverse=True)[:100]  # 最近100条
                
                success_count = sum(1 for r in recent_results if r.get('success'))
                total_return = sum(r.get('return_rate', 0) for r in recent_results)
                
                stats['recent_backtest'] = {
                    'total_tests': len(recent_results),
                    'success_count': success_count,
                    'success_rate': (success_count / len(recent_results)) * 100,
                    'total_return': total_return * 100,
                    'avg_return': (total_return / len(recent_results)) * 100
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取回测统计失败: {e}")
            return {}
    
    def analyze_analyst_performance(self) -> Dict:
        """分析分析师表现"""
        try:
            # 获取所有回测结果
            backtest_results = self.db.get_backtest_results()
            if not backtest_results:
                return {"error": "没有回测结果"}
            
            # 按推荐类型分组分析
            performance_by_type = {}
            
            for rec_type in ["买入", "持有", "卖出"]:
                type_results = [r for r in backtest_results 
                              if r.get('recommendation') == rec_type]
                
                if type_results:
                    success_count = sum(1 for r in type_results if r.get('success'))
                    returns = [r.get('return_rate', 0) for r in type_results]
                    
                    performance_by_type[rec_type] = {
                        "total_recommendations": len(type_results),
                        "successful": success_count,
                        "success_rate": (success_count / len(type_results)) * 100,
                        "avg_return": sum(returns) / len(returns) * 100,
                        "total_return": sum(returns) * 100,
                        "best_return": max(returns) * 100 if returns else 0,
                        "worst_return": min(returns) * 100 if returns else 0
                    }
            
            return {
                "analysis_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "performance_by_type": performance_by_type,
                "total_backtest_results": len(backtest_results)
            }
            
        except Exception as e:
            logger.error(f"分析师表现分析失败: {e}")
            return {"error": str(e)}
    
    def import_historical_results_from_files(self, results_dir: str = "outputs") -> int:
        """从历史文件导入分析结果"""
        logger.info(f"从{results_dir}导入历史分析结果")
        
        try:
            return self.data_collector.import_historical_results(results_dir)
        except Exception as e:
            logger.error(f"导入历史结果失败: {e}")
            return 0
    
    def cleanup_old_data(self, days: int = 90):
        """清理旧数据"""
        try:
            self.db.cleanup_old_data(days)
            self.data_collector.cleanup_old_cache()
            logger.info("旧数据清理完成")
        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")
    
    def get_recent_backtest_summary(self, days: int = 30) -> Dict:
        """获取最近的回测摘要"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            recommendations = self.db.get_recommendations(start_date=cutoff_date)
            backtest_results = self.db.get_backtest_results()
            
            # 过滤最近的回测结果
            recent_results = [
                r for r in backtest_results
                if r.get('backtest_date', '')[:10] >= cutoff_date
            ]
            
            summary = {
                "period": f"最近{days}天",
                "recommendations": len(recommendations),
                "backtest_results": len(recent_results),
                "coverage": (len(recent_results) / len(recommendations)) * 100 if recommendations else 0
            }
            
            if recent_results:
                success_count = sum(1 for r in recent_results if r.get('success'))
                returns = [r.get('return_rate', 0) for r in recent_results]
                
                summary.update({
                    "success_count": success_count,
                    "success_rate": (success_count / len(recent_results)) * 100,
                    "avg_return": sum(returns) / len(returns) * 100 if returns else 0,
                    "total_return": sum(returns) * 100
                })
            
            return summary
            
        except Exception as e:
            logger.error(f"获取回测摘要失败: {e}")
            return {"error": str(e)}