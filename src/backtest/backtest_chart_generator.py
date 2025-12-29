# -*- coding: utf-8 -*-
"""
回测K线图生成器 - 为交易股票生成K线图并标注买卖点
"""
import os
from datetime import datetime
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def generate_backtest_charts(results: Dict, historical_data: Dict, output_dir: str) -> List[str]:
    """
    为回测中交易的股票生成K线图

    Args:
        results: 回测结果字典
        historical_data: 历史数据 {symbol: DataFrame}
        output_dir: 输出目录

    Returns:
        生成的图表文件路径列表
    """
    try:
        import pandas as pd
        import matplotlib
        matplotlib.use('Agg')  # 使用非GUI后端
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrow
        import matplotlib.dates as mdates
        from matplotlib.patches import Rectangle

        # 检查是否有mplfinance（K线图专业库）
        try:
            import mplfinance as mpf
            use_mplfinance = True
            logger.info("使用 mplfinance 生成K线图")
        except ImportError:
            use_mplfinance = False
            logger.warning("mplfinance 未安装，使用 matplotlib 生成简化K线图")

    except ImportError as e:
        logger.error(f"图表生成依赖缺失: {e}")
        return []

    # 创建charts子目录
    charts_dir = os.path.join(output_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)

    # 获取交易记录
    trade_history = results.get('trade_history', [])
    if not trade_history:
        logger.warning("没有交易记录，跳过图表生成")
        return []

    # 按股票分组交易
    trades_by_symbol = {}
    for trade in trade_history:
        symbol = trade.get('symbol', 'UNKNOWN')
        if symbol not in trades_by_symbol:
            trades_by_symbol[symbol] = []
        trades_by_symbol[symbol].append(trade)

    # 获取股票名称映射
    symbol_to_name = results.get('symbol_to_name', {})

    # 为每只交易股票生成图表
    chart_files = []
    total_stocks = len(trades_by_symbol)

    logger.info(f"开始为 {total_stocks} 只股票生成K线图...")

    for idx, (symbol, symbol_trades) in enumerate(trades_by_symbol.items(), 1):
        try:
            logger.info(f"[{idx}/{total_stocks}] 生成 {symbol} 的K线图")

            # 获取该股票的历史数据
            if symbol not in historical_data:
                logger.warning(f"股票 {symbol} 没有历史数据，跳过")
                continue

            data = historical_data[symbol]
            stock_name = symbol_to_name.get(symbol, symbol)

            # 生成图表
            if use_mplfinance:
                chart_file = _generate_mplfinance_chart(
                    symbol, stock_name, data, symbol_trades, charts_dir
                )
            else:
                chart_file = _generate_matplotlib_chart(
                    symbol, stock_name, data, symbol_trades, charts_dir
                )

            if chart_file:
                chart_files.append(chart_file)
                logger.info(f"  ✓ 已生成: {os.path.basename(chart_file)}")

        except Exception as e:
            logger.error(f"生成 {symbol} 图表失败: {e}")
            continue

    logger.info(f"K线图生成完成，共 {len(chart_files)} 个文件")
    return chart_files


def _generate_mplfinance_chart(symbol: str, stock_name: str, data, trades: List[Dict], output_dir: str) -> str:
    """使用mplfinance生成专业K线图"""
    import pandas as pd
    import mplfinance as mpf

    # 准备买卖点标记
    buy_dates = []
    buy_prices = []
    sell_dates = []
    sell_prices = []

    for trade in trades:
        trade_date = pd.to_datetime(trade.get('date', ''))
        trade_price = trade.get('price', 0)

        if trade.get('action') == '买入':
            buy_dates.append(trade_date)
            buy_prices.append(trade_price)
        elif trade.get('action') == '卖出':
            sell_dates.append(trade_date)
            sell_prices.append(trade_price)

    # 创建买卖点Series
    buy_series = pd.Series(index=buy_dates, data=buy_prices)
    sell_series = pd.Series(index=sell_dates, data=sell_prices)

    # 准备附加图层
    apds = []
    if not buy_series.empty:
        apds.append(mpf.make_addplot(buy_series, type='scatter', markersize=100,
                                     marker='^', color='green'))
    if not sell_series.empty:
        apds.append(mpf.make_addplot(sell_series, type='scatter', markersize=100,
                                     marker='v', color='red'))

    # 图表样式
    mc = mpf.make_marketcolors(up='red', down='green', edge='inherit',
                               wick='inherit', volume='in')
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=False)

    # 生成文件名
    filename = f"{symbol}_{stock_name}_kline.png"
    filepath = os.path.join(output_dir, filename)

    # 绘制K线图
    mpf.plot(data, type='candle', style=s, addplot=apds if apds else None,
             title=f"{stock_name}({symbol}) 回测交易K线图",
             ylabel='价格',
             volume=True,
             savefig=dict(fname=filepath, dpi=150, bbox_inches='tight'))

    return filepath


def _generate_matplotlib_chart(symbol: str, stock_name: str, data, trades: List[Dict], output_dir: str) -> str:
    """使用matplotlib生成简化K线图（当mplfinance不可用时）"""
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    # 创建图表
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10),
                                    gridspec_kw={'height_ratios': [3, 1]})

    # 绘制收盘价折线图（简化版K线）
    ax1.plot(data.index, data['Close'], label='收盘价', linewidth=1.5, color='blue')

    # 标注买卖点
    for trade in trades:
        trade_date = pd.to_datetime(trade.get('date', ''))
        trade_price = trade.get('price', 0)

        if trade.get('action') == '买入':
            ax1.scatter(trade_date, trade_price, marker='^', color='green',
                       s=200, zorder=5, label='买入' if '买入' not in [t.get_label() for t in ax1.get_children()] else '')
            ax1.annotate('买', xy=(trade_date, trade_price),
                        xytext=(0, 10), textcoords='offset points',
                        ha='center', fontsize=9, color='green', weight='bold')
        elif trade.get('action') == '卖出':
            ax1.scatter(trade_date, trade_price, marker='v', color='red',
                       s=200, zorder=5, label='卖出' if '卖出' not in [t.get_label() for t in ax1.get_children()] else '')
            ax1.annotate('卖', xy=(trade_date, trade_price),
                        xytext=(0, -15), textcoords='offset points',
                        ha='center', fontsize=9, color='red', weight='bold')

    # 设置标题和标签
    ax1.set_title(f"{stock_name}({symbol}) 回测交易K线图", fontsize=14, weight='bold')
    ax1.set_ylabel('价格 (元)', fontsize=11)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='best')

    # 绘制成交量
    colors = ['red' if data['Close'].iloc[i] >= data['Open'].iloc[i] else 'green'
              for i in range(len(data))]
    ax2.bar(data.index, data['Volume'], color=colors, alpha=0.6)
    ax2.set_ylabel('成交量', fontsize=11)
    ax2.grid(True, alpha=0.3)

    # 格式化x轴日期
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 保存图表
    filename = f"{symbol}_{stock_name}_kline.png"
    filepath = os.path.join(output_dir, filename)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return filepath
