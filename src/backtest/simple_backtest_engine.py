# -*- coding: utf-8 -*-
"""
简化回测引擎 - 基于outputs目录中的分析结果
无需重新获取股票数据，直接使用历史分析结果进行回测
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set
import logging

logger = logging.getLogger(__name__)


# 中国股市交易日判断
def is_trading_day(date_str: str) -> bool:
    """
    判断是否为交易日（排除周末和节假日）

    Args:
        date_str: 日期字符串，格式 YYYY-MM-DD

    Returns:
        bool: 是否为交易日
    """
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')

    # 排除周六日
    if date_obj.weekday() >= 5:  # 5=Saturday, 6=Sunday
        return False

    # 中国法定节假日（2025年）- 需要定期更新
    holidays = {
        # 元旦
        '2025-01-01',
        # 春节
        '2025-01-28', '2025-01-29', '2025-01-30', '2025-01-31',
        '2025-02-01', '2025-02-02', '2025-02-03', '2025-02-04',
        # 清明节
        '2025-04-04', '2025-04-05', '2025-04-06',
        # 劳动节
        '2025-05-01', '2025-05-02', '2025-05-03', '2025-05-04', '2025-05-05',
        # 端午节
        '2025-05-31', '2025-06-01', '2025-06-02',
        # 中秋节
        '2025-10-06', '2025-10-07', '2025-10-08',
        # 国庆节
        '2025-10-01', '2025-10-02', '2025-10-03', '2025-10-04',
        '2025-10-05', '2025-10-06', '2025-10-07',
    }

    return date_str not in holidays


def calculate_trading_days_between(start_date: str, end_date: str) -> int:
    """
    计算两个日期之间的交易日天数

    Args:
        start_date: 起始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD

    Returns:
        int: 交易日天数
    """
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    trading_days = 0
    current = start

    while current <= end:
        if is_trading_day(current.strftime('%Y-%m-%d')):
            trading_days += 1
        current += timedelta(days=1)

    return trading_days


class SimpleBacktestEngine:
    """简化回测引擎 - 基于历史分析结果"""

    def __init__(self, outputs_dir: str = "outputs"):
        """
        初始化回测引擎

        Args:
            outputs_dir: outputs目录路径
        """
        self.outputs_dir = Path(outputs_dir)
        self.analysis_by_date = defaultdict(dict)  # {日期: {股票代码: 分析结果}}
        self.stock_timeline = defaultdict(list)     # {股票代码: [(日期, 分析结果)]}
        self.stock_names = {}                       # {股票代码: 股票名称}

    def load_analysis_results(self) -> Dict:
        """
        加载所有分析结果，按日期分类

        Returns:
            Dict: 加载统计信息
        """
        logger.info("🔍 开始加载历史分析结果...")

        total_files = 0
        loaded_files = 0
        total_stocks = 0

        # 遍历outputs目录
        for analysis_dir in sorted(self.outputs_dir.iterdir()):
            if not analysis_dir.is_dir():
                continue

            # 解析目录名中的日期时间
            try:
                dir_name = analysis_dir.name  # 格式: YYYYMMDD_HHMMSS
                date_str = dir_name.split('_')[0]  # 提取YYYYMMDD
                analysis_date = datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
            except (ValueError, IndexError):
                logger.warning(f"⚠️ 无法解析目录名: {analysis_dir.name}")
                continue

            # 读取analysis_detailed.json
            analysis_file = analysis_dir / "analysis_detailed.json"
            if not analysis_file.exists():
                continue

            total_files += 1

            try:
                with open(analysis_file, 'r', encoding='utf-8') as f:
                    stocks_data = json.load(f)

                # 处理每只股票的分析结果
                for stock_data in stocks_data:
                    symbol = stock_data.get("股票代码")
                    if not symbol:
                        continue

                    # 保存股票名称
                    stock_name = stock_data.get("股票名称", symbol)
                    if symbol not in self.stock_names:
                        self.stock_names[symbol] = stock_name

                    # 如果同一天已有该股票的分析结果，保留第一次的（目录名排序后靠前的）
                    if symbol in self.analysis_by_date[analysis_date]:
                        continue

                    # 保存分析结果
                    self.analysis_by_date[analysis_date][symbol] = stock_data
                    self.stock_timeline[symbol].append((analysis_date, stock_data))
                    total_stocks += 1

                loaded_files += 1
                logger.debug(f"  ✓ 加载: {analysis_date} - {len(stocks_data)}只股票")

            except Exception as e:
                logger.error(f"❌ 加载文件失败: {analysis_file}, 错误: {e}")
                continue

        # 对每只股票的时间线按日期排序
        for symbol in self.stock_timeline:
            self.stock_timeline[symbol].sort(key=lambda x: x[0])

        stats = {
            "total_files": total_files,
            "loaded_files": loaded_files,
            "total_stocks": total_stocks,
            "unique_stocks": len(self.stock_timeline),
            "date_range": (
                min(self.analysis_by_date.keys()) if self.analysis_by_date else None,
                max(self.analysis_by_date.keys()) if self.analysis_by_date else None
            )
        }

        logger.info(f"✅ 加载完成: {loaded_files}/{total_files}个文件, "
                   f"{total_stocks}条分析记录, {stats['unique_stocks']}只唯一股票")
        if stats['date_range'][0]:
            logger.info(f"📅 时间范围: {stats['date_range'][0]} 至 {stats['date_range'][1]}")

        return stats

    def filter_continuous_stocks(self, min_days: int = 2) -> Dict[str, List]:
        """
        筛选有连续分析结果的股票

        Args:
            min_days: 最小连续天数

        Returns:
            Dict: {股票代码: [(日期, 分析结果)]}
        """
        logger.info(f"🔍 筛选至少有{min_days}天连续分析的股票...")

        continuous_stocks = {}

        for symbol, timeline in self.stock_timeline.items():
            if len(timeline) >= min_days:
                continuous_stocks[symbol] = timeline

        logger.info(f"✅ 筛选完成: {len(continuous_stocks)}/{len(self.stock_timeline)}只股票符合条件")

        return continuous_stocks

    def generate_trading_signals(self, stock_timeline: List[Tuple]) -> List[Dict]:
        """
        生成交易信号

        策略：
        - 首次出现"买入"时买入
        - 出现"卖出"或下一日无分析结果时卖出

        Args:
            stock_timeline: [(日期, 分析结果)]

        Returns:
            List[Dict]: 交易记录列表
        """
        trades = []
        holding = False
        buy_date = None
        buy_price = None

        for i, (date, analysis) in enumerate(stock_timeline):
            action = analysis.get("操作建议", "持有")
            price_str = analysis.get("当前价格", "0元")
            price = float(price_str.replace('元', ''))

            # 买入信号
            if not holding and action == "买入":
                holding = True
                buy_date = date
                buy_price = price
                logger.debug(f"  📈 买入: {date}, 价格: {price}元")

            # 卖出信号
            elif holding:
                should_sell = False
                sell_reason = ""

                # 情况1: 出现卖出建议
                if action == "卖出":
                    should_sell = True
                    sell_reason = "卖出信号"

                # 情况2: 下一日无分析结果
                elif i == len(stock_timeline) - 1:  # 最后一天
                    should_sell = True
                    sell_reason = "时间线结束"
                else:
                    next_date = stock_timeline[i + 1][0]

                    # 使用交易日计算间隔
                    trading_days_gap = calculate_trading_days_between(date, next_date) - 1

                    # 如果下一个交易日的间隔大于1个交易日，说明中间有缺失
                    if trading_days_gap > 1:
                        should_sell = True
                        sell_reason = "下一日无分析"

                if should_sell:
                    sell_date = date
                    sell_price = price

                    # 计算收益率
                    return_rate = (sell_price - buy_price) / buy_price if buy_price > 0 else 0

                    # 使用交易日计算持仓天数
                    holding_trading_days = calculate_trading_days_between(buy_date, sell_date)

                    trade = {
                        "buy_date": buy_date,
                        "buy_price": buy_price,
                        "sell_date": sell_date,
                        "sell_price": sell_price,
                        "return_rate": return_rate,
                        "holding_days": holding_trading_days,  # 使用交易日天数
                        "sell_reason": sell_reason
                    }

                    trades.append(trade)
                    logger.debug(f"  📉 卖出: {sell_date}, 价格: {sell_price}元, "
                               f"收益率: {return_rate:.2%}, 原因: {sell_reason}")

                    holding = False
                    buy_date = None
                    buy_price = None

        return trades

    def run_backtest(self, min_continuous_days: int = 2) -> Dict:
        """
        运行回测

        Args:
            min_continuous_days: 最小连续天数

        Returns:
            Dict: 回测结果
        """
        logger.info("🚀 开始简化回测...")

        # 1. 加载分析结果
        load_stats = self.load_analysis_results()

        if load_stats["unique_stocks"] == 0:
            logger.error("❌ 未找到任何分析结果")
            return {"error": "未找到分析结果"}

        # 2. 筛选连续股票
        continuous_stocks = self.filter_continuous_stocks(min_continuous_days)

        if not continuous_stocks:
            logger.error(f"❌ 未找到至少有{min_continuous_days}天连续分析的股票")
            return {"error": "未找到连续分析的股票"}

        # 3. 生成交易信号并计算收益
        logger.info("📊 开始生成交易信号和计算收益...")

        stock_results = {}
        all_trades = []

        for symbol, timeline in continuous_stocks.items():
            logger.debug(f"\n分析股票: {symbol}")
            trades = self.generate_trading_signals(timeline)

            if trades:
                # 计算该股票的统计数据
                total_return = sum(t['return_rate'] for t in trades)
                avg_return = total_return / len(trades)
                win_trades = [t for t in trades if t['return_rate'] > 0]
                win_rate = len(win_trades) / len(trades) if trades else 0

                # 添加股票名称到结果中
                stock_name = self.stock_names.get(symbol, symbol)

                stock_results[symbol] = {
                    "stock_name": stock_name,  # 添加股票名称
                    "trades": trades,
                    "trade_count": len(trades),
                    "total_return": total_return,
                    "avg_return": avg_return,
                    "win_rate": win_rate,
                    "timeline_length": len(timeline)
                }

                all_trades.extend(trades)

                logger.info(f"  ✓ {symbol}: {len(trades)}笔交易, "
                          f"总收益: {total_return:.2%}, 胜率: {win_rate:.2%}")

        # 4. 计算整体统计
        if all_trades:
            overall_total_return = sum(t['return_rate'] for t in all_trades)
            overall_avg_return = overall_total_return / len(all_trades)
            overall_win_trades = [t for t in all_trades if t['return_rate'] > 0]
            overall_win_rate = len(overall_win_trades) / len(all_trades)

            # 最佳和最差交易
            best_trade = max(all_trades, key=lambda x: x['return_rate'])
            worst_trade = min(all_trades, key=lambda x: x['return_rate'])

            overall_stats = {
                "total_trades": len(all_trades),
                "total_return": overall_total_return,
                "avg_return": overall_avg_return,
                "win_rate": overall_win_rate,
                "win_trades": len(overall_win_trades),
                "lose_trades": len(all_trades) - len(overall_win_trades),
                "best_trade": best_trade,
                "worst_trade": worst_trade,
                "avg_holding_days": sum(t['holding_days'] for t in all_trades) / len(all_trades)
            }
        else:
            overall_stats = {"error": "未产生任何交易"}

        result = {
            "load_stats": load_stats,
            "stock_results": stock_results,
            "overall_stats": overall_stats,
            "analyzed_stocks": len(stock_results)
        }

        logger.info("\n" + "="*60)
        logger.info("📊 回测结果汇总:")
        logger.info(f"  分析股票数: {len(stock_results)}")
        logger.info(f"  总交易次数: {overall_stats.get('total_trades', 0)}")
        logger.info(f"  平均收益率: {overall_stats.get('avg_return', 0):.2%}")
        logger.info(f"  胜率: {overall_stats.get('win_rate', 0):.2%}")
        logger.info(f"  最佳交易: {best_trade['return_rate']:.2%} "
                   f"({best_trade['buy_date']} -> {best_trade['sell_date']})"
                   if all_trades else "  无交易")
        logger.info("="*60)

        return result

    def save_results(self, result: Dict, output_dir: str = None):
        """
        保存回测结果

        Args:
            result: 回测结果
            output_dir: 输出目录路径（可选，默认使用backtest_results/YYYYMMDD_HHMMSS格式）
        """
        # 使用与outputs目录相同的日期时间格式
        if output_dir is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = f"backtest_results/{timestamp}"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 保存JSON结果
        json_file = output_path / "backtest_result.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"💾 回测结果已保存: {json_file}")

        # 生成文本报告
        report_file = output_path / "backtest_report.txt"
        self._generate_text_report(result, report_file)
        logger.info(f"📄 文本报告已保存: {report_file}")

        # 生成README
        readme_file = output_path / "README.md"
        self._generate_readme(result, readme_file)
        logger.info(f"📋 说明文件已保存: {readme_file}")

        return output_path

    def _generate_text_report(self, result: Dict, report_file: Path):
        """生成文本格式报告"""
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("简化回测报告 - 基于历史分析结果\n")
            f.write("="*80 + "\n\n")

            # 加载统计
            load_stats = result.get("load_stats", {})
            f.write("📁 数据加载统计:\n")
            f.write(f"  加载文件数: {load_stats.get('loaded_files', 0)}/{load_stats.get('total_files', 0)}\n")
            f.write(f"  分析记录数: {load_stats.get('total_stocks', 0)}\n")
            f.write(f"  唯一股票数: {load_stats.get('unique_stocks', 0)}\n")
            date_range = load_stats.get('date_range', (None, None))
            if date_range[0]:
                f.write(f"  时间范围: {date_range[0]} 至 {date_range[1]}\n")
            f.write("\n")

            # 整体统计
            overall = result.get("overall_stats", {})
            f.write("📊 整体回测结果:\n")
            f.write(f"  分析股票数: {result.get('analyzed_stocks', 0)}\n")
            f.write(f"  总交易次数: {overall.get('total_trades', 0)}\n")
            f.write(f"  盈利交易数: {overall.get('win_trades', 0)}\n")
            f.write(f"  亏损交易数: {overall.get('lose_trades', 0)}\n")
            f.write(f"  胜率: {overall.get('win_rate', 0):.2%}\n")
            f.write(f"  总收益率: {overall.get('total_return', 0):.2%}\n")
            f.write(f"  平均收益率: {overall.get('avg_return', 0):.2%}\n")
            f.write(f"  平均持仓天数: {overall.get('avg_holding_days', 0):.1f}天\n")
            f.write("\n")

            # 最佳和最差交易
            if 'best_trade' in overall:
                best = overall['best_trade']
                f.write(f"🏆 最佳交易:\n")
                f.write(f"  收益率: {best['return_rate']:.2%}\n")
                f.write(f"  买入: {best['buy_date']} @ {best['buy_price']}元\n")
                f.write(f"  卖出: {best['sell_date']} @ {best['sell_price']}元\n")
                f.write(f"  持仓: {best['holding_days']}天\n")
                f.write("\n")

            if 'worst_trade' in overall:
                worst = overall['worst_trade']
                f.write(f"📉 最差交易:\n")
                f.write(f"  收益率: {worst['return_rate']:.2%}\n")
                f.write(f"  买入: {worst['buy_date']} @ {worst['buy_price']}元\n")
                f.write(f"  卖出: {worst['sell_date']} @ {worst['sell_price']}元\n")
                f.write(f"  持仓: {worst['holding_days']}天\n")
                f.write("\n")

            # 个股详情
            f.write("="*80 + "\n")
            f.write("个股交易详情:\n")
            f.write("="*80 + "\n\n")

            stock_results = result.get("stock_results", {})
            for symbol, stock_data in sorted(stock_results.items(),
                                            key=lambda x: x[1]['total_return'],
                                            reverse=True):
                # 获取股票名称
                stock_name = self.stock_names.get(symbol, symbol)
                f.write(f"\n📈 {symbol} ({stock_name}):\n")
                f.write(f"  交易次数: {stock_data['trade_count']}\n")
                f.write(f"  总收益率: {stock_data['total_return']:.2%}\n")
                f.write(f"  平均收益率: {stock_data['avg_return']:.2%}\n")
                f.write(f"  胜率: {stock_data['win_rate']:.2%}\n")
                f.write(f"  分析天数: {stock_data['timeline_length']}\n")

                f.write(f"\n  交易明细:\n")
                for i, trade in enumerate(stock_data['trades'], 1):
                    f.write(f"    [{i}] 买入: {trade['buy_date']} @ {trade['buy_price']:.2f}元\n")
                    f.write(f"        卖出: {trade['sell_date']} @ {trade['sell_price']:.2f}元\n")
                    f.write(f"        持仓: {trade['buy_date']} 至 {trade['sell_date']} ({trade['holding_days']}个交易日)\n")
                    f.write(f"        收益率: {trade['return_rate']:+.2%}\n")
                    f.write(f"        卖出原因: {trade['sell_reason']}\n")
                    if i < len(stock_data['trades']):
                        f.write("\n")
                f.write("\n")

    def _generate_readme(self, result: Dict, readme_file: Path):
        """生成README.md说明文件"""
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write("# 简化回测结果\n\n")

            # 回测信息
            load_stats = result.get("load_stats", {})
            date_range = load_stats.get('date_range', (None, None))

            f.write("## 回测信息\n\n")
            f.write(f"- **回测时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **数据来源**: outputs目录中的历史分析结果\n")
            if date_range[0]:
                f.write(f"- **数据时间范围**: {date_range[0]} 至 {date_range[1]}\n")
            f.write(f"- **加载文件数**: {load_stats.get('loaded_files', 0)}\n")
            f.write(f"- **分析记录数**: {load_stats.get('total_stocks', 0)}\n")
            f.write(f"- **唯一股票数**: {load_stats.get('unique_stocks', 0)}\n\n")

            # 回测策略
            f.write("## 回测策略\n\n")
            f.write("- **买入信号**: 首次出现\"买入\"建议时买入\n")
            f.write("- **卖出信号**: 出现\"卖出\"建议 OR 下一日无分析结果时卖出\n")
            f.write("- **筛选条件**: 至少有2天连续分析的股票\n\n")

            # 整体结果
            overall = result.get("overall_stats", {})
            f.write("## 整体回测结果\n\n")
            f.write(f"| 指标 | 数值 |\n")
            f.write(f"|------|------|\n")
            f.write(f"| 分析股票数 | {result.get('analyzed_stocks', 0)} |\n")
            f.write(f"| 总交易次数 | {overall.get('total_trades', 0)} |\n")
            f.write(f"| 盈利交易数 | {overall.get('win_trades', 0)} |\n")
            f.write(f"| 亏损交易数 | {overall.get('lose_trades', 0)} |\n")
            f.write(f"| 胜率 | {overall.get('win_rate', 0):.2%} |\n")
            f.write(f"| 总收益率 | {overall.get('total_return', 0):.2%} |\n")
            f.write(f"| 平均收益率 | {overall.get('avg_return', 0):.2%} |\n")
            f.write(f"| 平均持仓天数 | {overall.get('avg_holding_days', 0):.1f}天 |\n\n")

            # 最佳和最差交易
            if 'best_trade' in overall:
                best = overall['best_trade']
                f.write("### 最佳交易\n\n")
                f.write(f"- **收益率**: {best['return_rate']:.2%}\n")
                f.write(f"- **买入**: {best['buy_date']} @ {best['buy_price']}元\n")
                f.write(f"- **卖出**: {best['sell_date']} @ {best['sell_price']}元\n")
                f.write(f"- **持仓期间**: {best['buy_date']} 至 {best['sell_date']}\n")
                f.write(f"- **持仓天数**: {best['holding_days']}个交易日\n\n")

            if 'worst_trade' in overall:
                worst = overall['worst_trade']
                f.write("### 最差交易\n\n")
                f.write(f"- **收益率**: {worst['return_rate']:.2%}\n")
                f.write(f"- **买入**: {worst['buy_date']} @ {worst['buy_price']}元\n")
                f.write(f"- **卖出**: {worst['sell_date']} @ {worst['sell_price']}元\n")
                f.write(f"- **持仓期间**: {worst['buy_date']} 至 {worst['sell_date']}\n")
                f.write(f"- **持仓天数**: {worst['holding_days']}个交易日\n\n")

            # 个股表现概览
            f.write("## 个股表现概览\n\n")
            f.write("| 股票代码 | 股票名称 | 交易次数 | 总收益率 | 平均收益率 | 胜率 |\n")
            f.write("|----------|----------|----------|----------|------------|------|\n")

            stock_results = result.get("stock_results", {})
            for symbol, stock_data in sorted(stock_results.items(),
                                            key=lambda x: x[1]['total_return'],
                                            reverse=True):
                stock_name = self.stock_names.get(symbol, symbol)
                f.write(f"| {symbol} | {stock_name} | {stock_data['trade_count']} | "
                       f"{stock_data['total_return']:+.2%} | "
                       f"{stock_data['avg_return']:+.2%} | "
                       f"{stock_data['win_rate']:.2%} |\n")

            # 个股交易明细表格
            f.write("\n## 个股交易明细\n\n")
            f.write("| 股票代码 | 股票名称 | 买入日期 | 买入价格 | 卖出日期 | 卖出价格 | 持仓天数 | 收益率 | 卖出原因 |\n")
            f.write("|----------|----------|----------|----------|----------|----------|----------|--------|----------|\n")

            # 按股票代码排序，遍历所有交易
            for symbol, stock_data in sorted(stock_results.items()):
                stock_name = self.stock_names.get(symbol, symbol)
                for trade in stock_data['trades']:
                    f.write(f"| {symbol} | {stock_name} | "
                           f"{trade['buy_date']} | {trade['buy_price']:.2f}元 | "
                           f"{trade['sell_date']} | {trade['sell_price']:.2f}元 | "
                           f"{trade['holding_days']}天 | "
                           f"{trade['return_rate']:+.2%} | "
                           f"{trade['sell_reason']} |\n")

            f.write("\n## 文件说明\n\n")
            f.write("- `backtest_result.json` - 详细的回测结果数据（JSON格式）\n")
            f.write("- `backtest_report.txt` - 可读的文本格式报告\n")
            f.write("- `README.md` - 本文件，回测结果概览\n")
