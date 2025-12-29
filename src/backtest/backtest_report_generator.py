# -*- coding: utf-8 -*-
"""
回测报告生成器 - 生成Markdown格式的回测报告
"""
from datetime import datetime
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def generate_backtest_markdown(results: Dict, output_file: str) -> None:
    """
    生成回测结果的Markdown报告

    Args:
        results: 回测结果字典
        output_file: 输出文件路径
    """
    try:
        # 获取股票名称映射
        symbol_to_name = results.get('symbol_to_name', {})

        with open(output_file, 'w', encoding='utf-8') as f:
            # 标题和基本信息
            f.write("# 历史回测结果报告\n\n")
            f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # 回测配置
            config = results.get('backtest_config', {})
            if config:
                f.write("## 回测配置\n\n")
                f.write(f"- **回测时间范围**: {config.get('start_date', 'N/A')} 至 {config.get('end_date', 'N/A')}\n")
                f.write(f"- **回测股票数量**: {config.get('stock_count', 0)} 只\n")
                f.write(f"- **交易日数量**: {config.get('trading_days', 0)} 天\n")
                f.write(f"- **生成决策数**: {config.get('decision_count', 0)} 条\n")
                f.write(f"- **初始资金**: ¥{config.get('initial_capital', 0):,.0f}\n\n")

            # 整体回测结果
            f.write("## 整体回测结果\n\n")

            # 收益指标
            f.write("### 📈 收益指标\n\n")
            f.write("| 指标 | 数值 |\n")
            f.write("|------|------|\n")
            f.write(f"| 总收益率 | {results.get('total_return', 0):.2%} |\n")
            f.write(f"| 年化收益率 | {results.get('annualized_return', 0):.2%} |\n")
            f.write(f"| 初始资金 | ¥{results.get('initial_capital', 0):,.2f} |\n")
            f.write(f"| 最终资金 | ¥{results.get('final_capital', 0):,.2f} |\n")
            f.write(f"| 盈亏金额 | ¥{results.get('profit', 0):,.2f} |\n\n")

            # 风险指标
            f.write("### ⚠️ 风险指标\n\n")
            f.write("| 指标 | 数值 |\n")
            f.write("|------|------|\n")
            f.write(f"| 年化波动率 | {results.get('volatility', 0):.2%} |\n")
            f.write(f"| 夏普比率 | {results.get('sharpe_ratio', 0):.2f} |\n")
            f.write(f"| 最大回撤 | {results.get('max_drawdown', 0):.2%} |\n\n")

            # 交易统计
            f.write("### 💼 交易统计\n\n")
            f.write("| 指标 | 数值 |\n")
            f.write("|------|------|\n")
            f.write(f"| 总交易次数 | {results.get('total_trades', 0)} 笔 |\n")
            f.write(f"| 买入次数 | {results.get('buy_trades', 0)} 笔 |\n")
            f.write(f"| 卖出次数 | {results.get('sell_trades', 0)} 笔 |\n")
            f.write(f"| 胜率 | {results.get('win_rate', 0):.2%} |\n")
            f.write(f"| 平均持有天数 | {results.get('avg_holding_days', 0):.1f} 天 |\n\n")

            # 详细交易记录（按股票分组）
            trade_history = results.get('trade_history', [])
            if trade_history:
                f.write("## 详细交易记录\n\n")
                f.write(f"共 {len(trade_history)} 笔交易\n\n")

                # 按股票分组
                trades_by_symbol = {}
                for trade in trade_history:
                    symbol = trade.get('symbol', 'UNKNOWN')
                    if symbol not in trades_by_symbol:
                        trades_by_symbol[symbol] = []
                    trades_by_symbol[symbol].append(trade)

                # 为每只股票生成交易记录
                for symbol in sorted(trades_by_symbol.keys()):
                    symbol_trades = trades_by_symbol[symbol]

                    # 获取股票名称
                    stock_name = symbol_to_name.get(symbol, symbol)

                    # 计算该股票的统计数据
                    buy_trades = [t for t in symbol_trades if t.get('action') == '买入']
                    sell_trades = [t for t in symbol_trades if t.get('action') == '卖出']

                    total_profit = sum(t.get('profit', 0) for t in sell_trades)
                    total_trades = len(buy_trades) + len(sell_trades)

                    f.write(f"### 📊 {stock_name} ({symbol})\n\n")
                    f.write(f"- **交易次数**: {total_trades} 笔 ({len(buy_trades)} 买 / {len(sell_trades)} 卖)\n")
                    if sell_trades:
                        avg_profit = total_profit / len(sell_trades)
                        win_trades = [t for t in sell_trades if t.get('profit', 0) > 0]
                        win_rate = len(win_trades) / len(sell_trades)
                        f.write(f"- **总盈亏**: ¥{total_profit:,.2f}\n")
                        f.write(f"- **平均盈亏**: ¥{avg_profit:,.2f}\n")
                        f.write(f"- **胜率**: {win_rate:.2%}\n")
                    f.write("\n")

                    # 交易明细表格
                    f.write("| 日期 | 操作 | 价格 | 数量 | 金额 | 手续费 | 盈亏 | 收益率 | 持有天数 | 原因 |\n")
                    f.write("|------|------|------|------|------|--------|------|--------|----------|------|\n")

                    for trade in symbol_trades:
                        date = trade.get('date', 'N/A')
                        action = trade.get('action', 'N/A')
                        price = trade.get('price', 0)
                        shares = trade.get('shares', 0)
                        value = trade.get('value', 0)
                        cost = trade.get('transaction_cost', 0)
                        profit = trade.get('profit', 0)
                        return_rate = trade.get('return_rate', 0)
                        holding_days = trade.get('holding_days', 0)
                        reason = trade.get('reason', 'N/A')

                        # 根据操作类型调整显示
                        if action == '买入':
                            f.write(f"| {date} | {action} | ¥{price:.2f} | {shares} | ¥{value:,.2f} | ¥{cost:.2f} | - | - | - | {reason} |\n")
                        else:  # 卖出
                            profit_str = f"¥{profit:,.2f}" if profit != 0 else "-"
                            return_str = f"{return_rate:+.2%}" if return_rate != 0 else "-"
                            holding_str = f"{holding_days}天" if holding_days > 0 else "-"
                            f.write(f"| {date} | {action} | ¥{price:.2f} | {shares} | ¥{value:,.2f} | ¥{cost:.2f} | {profit_str} | {return_str} | {holding_str} | {reason} |\n")

                    f.write("\n")

            # 性能评估
            f.write("## 性能评估\n\n")

            total_return = results.get('total_return', 0)
            sharpe_ratio = results.get('sharpe_ratio', 0)
            max_drawdown = results.get('max_drawdown', 0)
            win_rate = results.get('win_rate', 0)

            # 评分标准
            score = 0
            comments = []

            if total_return > 0.10:
                score += 25
                comments.append("✅ 收益率优秀 (>10%)")
            elif total_return > 0.05:
                score += 15
                comments.append("🟡 收益率良好 (5-10%)")
            else:
                score += 5
                comments.append("❌ 收益率偏低 (<5%)")

            if sharpe_ratio > 1.0:
                score += 25
                comments.append("✅ 夏普比率优秀 (>1.0)")
            elif sharpe_ratio > 0.5:
                score += 15
                comments.append("🟡 夏普比率良好 (0.5-1.0)")
            else:
                score += 5
                comments.append("❌ 夏普比率偏低 (<0.5)")

            if abs(max_drawdown) < 0.15:
                score += 25
                comments.append("✅ 最大回撤良好 (<15%)")
            elif abs(max_drawdown) < 0.20:
                score += 15
                comments.append("🟡 最大回撤可接受 (15-20%)")
            else:
                score += 5
                comments.append("❌ 最大回撤偏大 (>20%)")

            if win_rate > 0.55:
                score += 25
                comments.append("✅ 胜率优秀 (>55%)")
            elif win_rate > 0.45:
                score += 15
                comments.append("🟡 胜率良好 (45-55%)")
            else:
                score += 5
                comments.append("❌ 胜率偏低 (<45%)")

            f.write(f"### 综合评分: {score}/100\n\n")

            if score >= 80:
                f.write("🌟 **评级**: 优秀 - 策略表现出色，可以考虑实盘应用\n\n")
            elif score >= 60:
                f.write("👍 **评级**: 良好 - 策略有潜力，建议继续优化\n\n")
            elif score >= 40:
                f.write("⚠️ **评级**: 一般 - 策略需要较大改进\n\n")
            else:
                f.write("❌ **评级**: 较差 - 策略存在明显问题，不建议使用\n\n")

            f.write("**详细评估**:\n\n")
            for comment in comments:
                f.write(f"- {comment}\n")
            f.write("\n")

            # K线图表
            f.write("## 📊 K线图表\n\n")
            f.write("系统已为所有交易股票生成K线图，标注了买入和卖出点。\n\n")

            # 按股票列出图表文件
            import os
            charts_dir = os.path.join(os.path.dirname(output_file), "charts")
            if os.path.exists(charts_dir):
                chart_files = [f for f in os.listdir(charts_dir) if f.endswith('.png')]
                if chart_files:
                    f.write("**生成的图表文件**:\n\n")
                    for chart_file in sorted(chart_files):
                        # 从文件名提取股票信息
                        f.write(f"- `charts/{chart_file}`\n")
                    f.write(f"\n共生成 {len(chart_files)} 个K线图，保存在 `charts/` 目录中。\n\n")
                else:
                    f.write("*没有生成K线图*\n\n")
            else:
                f.write("*图表目录不存在*\n\n")

            # 风险提示
            f.write("## ⚠️ 风险提示\n\n")
            f.write("1. **历史表现不代表未来收益**: 回测结果基于历史数据，市场环境变化可能导致实盘表现不同\n")
            f.write("2. **交易成本假设**: 回测中使用固定交易成本，实际成本可能因券商、市场流动性等因素变化\n")
            f.write("3. **滑点影响**: 回测假设按收盘价成交，实盘中可能存在滑点\n")
            f.write("4. **市场冲击**: 大额交易可能对市场价格产生影响，回测未考虑此因素\n")
            f.write("5. **停牌和退市风险**: 回测未充分考虑停牌、退市等特殊情况\n\n")

            # 结尾
            f.write("---\n\n")
            f.write("*本报告由A股量化交易系统自动生成*\n")

        logger.info(f"回测Markdown报告已生成: {output_file}")

    except Exception as e:
        logger.error(f"生成Markdown报告失败: {e}")
        raise
