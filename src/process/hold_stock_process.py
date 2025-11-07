# -*- coding: utf-8 -*-
"""
持股流程模块
封装持仓股票的分析流程
"""

import time
import logging
import csv
from typing import Dict, List, Optional
from datetime import datetime, date
from pathlib import Path
import pandas as pd

from .hold_stock_analyzer import HoldStockAnalyzer

logger = logging.getLogger(__name__)


class HoldStockProcess:
    """持股流程管理类 - 负责持仓股票的监控和分析"""

    def __init__(self, system=None, config=None, output_dir=None):
        """
        初始化持股流程

        Args:
            system: A股TradingAgents系统实例
            config: 配置管理器实例
            output_dir: 输出目录（可选，默认为 outputs/当前时间戳）
        """
        self.system = system
        self.config = config
        self.output_dir = output_dir  # 保存输出目录
        self.process_start_time = time.time()
        self.logger = logging.getLogger("HoldStockProcess")
        self.logger.info("🚀 持股流程开始初始化...")

        # 初始化分析器
        self.analyzer = HoldStockAnalyzer(system, config)

    def load_hold_stocks(self) -> List[Dict]:
        """
        加载持仓股票数据

        Returns:
            持仓股票列表
        """
        try:
            from src.stock.stock_selection_manager import StockSelectionManager
            stock_manager = StockSelectionManager(self.config)
            hold_config = stock_manager._load_hold_stock_config()

            hold_stocks = hold_config.get('hold_stocks', [])
            self.logger.info(f"加载持仓股票: {len(hold_stocks)} 只")

            return hold_stocks

        except Exception as e:
            self.logger.error(f"加载持仓股票失败: {e}")
            return []

    def analyze_all_positions(self, hold_stocks: List[Dict], analysis_results=None) -> List[Dict]:
        """
        分析所有持仓股票

        Args:
            hold_stocks: 持仓股票列表
            analysis_results: 已有的分析结果（可选），如果提供则从中提取数据

        Returns:
            所有股票的分析结果列表
        """
        if not self.system:
            raise ValueError("系统实例未初始化，无法执行分析")

        try:
            # 如果提供了已有的分析结果，直接从中提取持仓股票数据
            if analysis_results:
                print(f"\n💡 使用已有分析结果（无需重新调用AI）")
                print(f"🔍 从 {len(analysis_results)} 个分析结果中提取 {len(hold_stocks)} 只持仓股票...")

                # 创建 symbol -> result 的映射（analysis_results 使用中文字段名）
                result_map = {}
                for r in analysis_results:
                    # 优先使用中文字段名（format_analysis_result 返回的格式）
                    symbol = r.get('股票代码') or r.get('symbol')
                    if symbol:
                        result_map[symbol] = r

                position_analyses = []

                for i, stock in enumerate(hold_stocks, 1):
                    symbol = stock['symbol']
                    print(f"\n[{i}/{len(hold_stocks)}] 处理 {stock['name']}({symbol})...")

                    # 从已有结果中提取数据
                    if symbol in result_map:
                        existing_result = result_map[symbol]
                        # 使用已有结果创建持仓分析
                        analysis = self.analyzer.analyze_position(stock, existing_result=existing_result)
                    else:
                        # 如果没有找到，执行新的分析（回退机制）
                        print(f"  ⚠️ 未找到已有分析结果，执行新分析...")
                        analysis = self.analyzer.analyze_position(stock)

                    position_analyses.append(analysis)

                    # 简单输出当前分析结果
                    action = analysis.get('操作建议', 'N/A')
                    profit_rate = analysis.get('持仓收益率', 0)
                    print(f"  收益: {profit_rate:+.2f}% | 建议: {action}")

                print(f"\n✅ 持仓股票处理完成: {len(position_analyses)} 只")
                return position_analyses

            # 原有逻辑：没有提供分析结果，执行完整分析
            print(f"\n🔍 开始分析 {len(hold_stocks)} 只持仓股票...")

            position_analyses = []

            for i, stock in enumerate(hold_stocks, 1):
                print(f"\n[{i}/{len(hold_stocks)}] 分析 {stock['name']}({stock['symbol']})...")

                # 使用分析器分析单只股票
                analysis = self.analyzer.analyze_position(stock)
                position_analyses.append(analysis)

                # 简单输出当前分析结果
                action = analysis.get('操作建议', 'N/A')
                profit_rate = analysis.get('持仓收益率', 0)
                print(f"  收益: {profit_rate:+.2f}% | 建议: {action}")

            print(f"\n✅ 持仓股票分析完成: {len(position_analyses)} 只")
            return position_analyses

        except Exception as e:
            self.logger.error(f"持仓股票分析失败: {e}")
            return []

    def generate_position_summary(self, position_analyses: List[Dict]) -> Dict:
        """
        生成持仓概览

        Args:
            position_analyses: 持仓分析结果列表

        Returns:
            持仓概览数据
        """
        try:
            total_cost = sum(p['成本价'] for p in position_analyses)
            total_value = sum(p['当前价格'] for p in position_analyses)
            total_profit = total_value - total_cost
            total_profit_rate = (total_profit / total_cost * 100) if total_cost > 0 else 0

            # 统计盈亏情况
            profit_count = sum(1 for p in position_analyses if p['收益状态'] == '盈利')
            loss_count = sum(1 for p in position_analyses if p['收益状态'] == '亏损')
            flat_count = sum(1 for p in position_analyses if p['收益状态'] == '持平')

            # 统计需要操作的股票
            action_needed = sum(1 for p in position_analyses
                              if any(keyword in p['操作建议']
                                   for keyword in ['卖出', '减仓', '止盈', '止损']))

            return {
                '分析时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '持仓数量': len(position_analyses),
                '总成本': total_cost,
                '总市值': total_value,
                '总收益': total_profit,
                '总收益率': total_profit_rate,
                '盈利股票数': profit_count,
                '亏损股票数': loss_count,
                '持平股票数': flat_count,
                '需要操作股票数': action_needed
            }

        except Exception as e:
            self.logger.error(f"生成持仓概览失败: {e}")
            return {}

    def generate_risk_warnings(self, position_analyses: List[Dict]) -> List[Dict]:
        """
        生成风险预警

        Args:
            position_analyses: 持仓分析结果列表

        Returns:
            风险预警列表
        """
        warnings = []

        for analysis in position_analyses:
            warning_status = analysis.get('预警状态', '正常')

            if warning_status in ['触发止损', '严重警告', '警告']:
                warning = {
                    '股票': f"{analysis['股票代码']} {analysis['股票名称']}",
                    '预警类型': warning_status,
                    '当前价格': analysis['当前价格'],
                    '止损价格': analysis['止损价格'],
                    '距离止损': analysis['距离止损'],
                    '建议': analysis['风险提示']
                }
                warnings.append(warning)

        return warnings

    def generate_action_recommendations(self, position_analyses: List[Dict]) -> Dict:
        """
        生成操作建议汇总

        Args:
            position_analyses: 持仓分析结果列表

        Returns:
            操作建议汇总
        """
        immediate_actions = []
        watch_list = []

        for analysis in position_analyses:
            action = analysis['操作建议']
            stock_name = f"{analysis['股票代码']} {analysis['股票名称']}"

            # 需要立即操作的
            if any(keyword in action for keyword in ['强烈卖出', '触发止损', '全部止盈']):
                immediate_actions.append({
                    '股票': stock_name,
                    '操作': action,
                    '价格': analysis['当前价格'],
                    '理由': analysis['建议理由'][0] if analysis['建议理由'] else ''
                })

            # 需要近期关注的
            elif any(keyword in action for keyword in ['减仓', '观察', '部分止盈', '加仓']):
                watch_list.append({
                    '股票': stock_name,
                    '操作': action,
                    '理由': analysis['下一步行动']
                })

        return {
            '立即操作': immediate_actions,
            '近期关注': watch_list
        }

    def print_analysis_report(self, summary: Dict, position_analyses: List[Dict],
                             warnings: List[Dict], actions: Dict):
        """
        打印分析报告到控制台

        Args:
            summary: 持仓概览
            position_analyses: 持仓分析结果
            warnings: 风险预警
            actions: 操作建议
        """
        print("\n" + "=" * 80)
        print(f"持仓分析报告 - {summary.get('分析时间', 'N/A')}")
        print("=" * 80)

        # 持仓概览
        print("\n📊 持仓概览")
        print(f"  持仓数量: {summary['持仓数量']}只")
        print(f"  总成本: ¥{summary['总成本']:.2f}")
        print(f"  总市值: ¥{summary['总市值']:.2f}")
        profit_symbol = "+" if summary['总收益'] >= 0 else ""
        print(f"  总收益: {profit_symbol}¥{summary['总收益']:.2f} ({profit_symbol}{summary['总收益率']:.2f}%)")
        print(f"  盈利/亏损: {summary['盈利股票数']}盈{summary['亏损股票数']}亏")

        # 个股分析
        print("\n【个股分析】")
        print("-" * 80)

        for i, analysis in enumerate(position_analyses, 1):
            # 确定状态图标
            profit_rate = analysis['持仓收益率']
            if profit_rate > 0:
                status_icon = "✅ 盈利"
            elif profit_rate < 0:
                warning_status = analysis.get('预警状态', '正常')
                if warning_status in ['触发止损', '严重警告']:
                    status_icon = "⚠️ 触发止损" if warning_status == '触发止损' else "⚠️ 警告"
                else:
                    status_icon = "❌ 亏损"
            else:
                status_icon = "➖ 持平"

            print(f"\n{i}. {analysis['股票名称']} ({analysis['股票代码']}) {status_icon}")
            print(f"   成本: ¥{analysis['成本价']:.2f}  当前: ¥{analysis['当前价格']:.2f}  "
                  f"收益: {profit_rate:+.2f}%  持仓: {analysis['持仓天数']}天")

            # 止损信息
            if analysis['止损价格']:
                print(f"   止损: ¥{analysis['止损价格']:.2f} ({analysis['止损规则']})  "
                      f"距离: {analysis['距离止损']}")
            else:
                print(f"   止损: {analysis['止损规则']}")

            # 系统建议
            print(f"   系统建议: {analysis['系统建议']} ({analysis['系统信心度']})")

            # 操作建议
            print(f"   ▶ 操作建议: {analysis['操作建议']}")
            print(f"   理由: {'; '.join(analysis['建议理由'][:2])}")

        # 风险预警
        if warnings:
            print("\n" + "=" * 80)
            print("⚠️ 风险预警")
            print("-" * 80)
            for warning in warnings:
                print(f"  • {warning['股票']}: {warning['预警类型']}")
                print(f"    当前价格: ¥{warning['当前价格']:.2f}  "
                      f"止损价格: ¥{warning['止损价格']:.2f}  "
                      f"距离: {warning['距离止损']}")
                print(f"    建议: {warning['建议']}")

        # 操作建议
        print("\n" + "=" * 80)
        print("📋 建议操作")
        print("-" * 80)

        if actions['立即操作']:
            print("  立即操作:")
            for action in actions['立即操作']:
                print(f"    ✓ {action['股票']}: {action['操作']}")
                print(f"      {action['理由']}")
        else:
            print("  立即操作: 无")

        if actions['近期关注']:
            print("\n  近期关注:")
            for action in actions['近期关注']:
                print(f"    ◉ {action['股票']}: {action['操作']}")
                print(f"      {action['理由']}")
        else:
            print("\n  近期关注: 无")

        print("\n" + "=" * 80)

    def save_analysis_to_csv(self, position_analyses: List[Dict]):
        """
        保存分析结果到CSV文件

        Args:
            position_analyses: 持仓分析结果

        Returns:
            CSV文件路径（字符串）
        """
        try:
            # 确定输出目录
            if self.output_dir:
                output_path = Path(self.output_dir)
            else:
                # 如果没有指定输出目录，使用默认的 outputs 目录
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = Path("outputs") / timestamp

            output_path.mkdir(parents=True, exist_ok=True)

            # 生成文件名（不再在文件名中添加时间戳，因为已经在目录名中了）
            csv_filename = output_path / "holdings_analysis.csv"

            # 准备CSV数据
            csv_data = []
            for analysis in position_analyses:
                csv_row = {
                    '股票代码': analysis['股票代码'],
                    '股票名称': analysis['股票名称'],
                    '成本价': f"{analysis['成本价']:.2f}",
                    '当前价格': f"{analysis['当前价格']:.2f}",
                    '持仓天数': analysis['持仓天数'],
                    '持仓收益': f"{analysis['持仓收益']:+.2f}",
                    '持仓收益率': f"{analysis['持仓收益率']:+.2f}%",
                    '止损价格': f"{analysis['止损价格']:.2f}" if analysis['止损价格'] else 'N/A',
                    '距离止损': analysis['距离止损'],
                    '系统建议': f"{analysis['系统建议']}({analysis['系统信心度']})",
                    '操作建议': analysis['操作建议'],
                    '建议理由': '; '.join(analysis['建议理由'])
                }
                csv_data.append(csv_row)

            # 写入CSV
            df = pd.DataFrame(csv_data)
            df.to_csv(csv_filename, index=False, encoding='utf-8-sig')

            print(f"\n📄 分析结果已保存到: {csv_filename}")
            return str(csv_filename)  # 返回文件路径

        except Exception as e:
            self.logger.error(f"保存CSV文件失败: {e}")
            print(f"保存CSV文件失败: {e}")
            return None  # 失败时返回 None

    def _calculate_holding_days(self, purchase_date: str) -> int:
        """计算持仓天数"""
        try:
            if purchase_date == '未知':
                return 0
            purchase_dt = datetime.strptime(purchase_date, '%Y-%m-%d').date()
            return (date.today() - purchase_dt).days
        except:
            return 0

    def execute_full_process(self, analysis_results=None) -> Dict:
        """
        执行完整的持仓分析流程

        Args:
            analysis_results: 已有的分析结果（可选），如果提供则复用数据

        Returns:
            流程执行结果字典
        """
        self.logger.info("🚀 ================ 持股流程开始 ================")

        try:
            # 第一阶段：加载持仓股票
            hold_stocks = self.load_hold_stocks()

            if not hold_stocks:
                print("没有找到持仓股票")
                return {
                    'success': False,
                    'error': '没有持仓股票',
                    'hold_stocks': []
                }

            # 第二阶段：分析所有持仓（如果提供了analysis_results，则使用数据复用）
            position_analyses = self.analyze_all_positions(hold_stocks, analysis_results=analysis_results)

            # 第三阶段：生成概览和建议
            summary = self.generate_position_summary(position_analyses)
            warnings = self.generate_risk_warnings(position_analyses)
            actions = self.generate_action_recommendations(position_analyses)

            # 第四阶段：输出报告
            self.print_analysis_report(summary, position_analyses, warnings, actions)

            # 第五阶段：保存到CSV
            csv_file = self.save_analysis_to_csv(position_analyses)

            # 计算总耗时
            total_time = time.time() - self.process_start_time
            self.logger.info(f"⏱️ 持股流程总耗时: {total_time:.2f}秒")

            return {
                'success': True,
                'hold_stocks': hold_stocks,
                'position_analyses': position_analyses,
                'summary': summary,
                'warnings': warnings,
                'actions': actions,
                'csv_file': csv_file,  # 添加CSV文件路径
                'total_time': total_time
            }

        except Exception as e:
            self.logger.error(f"持股流程执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'total_time': time.time() - self.process_start_time
            }