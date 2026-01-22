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
    为回测中交易的股票生成K线图（同时生成LONG和SHORT两种版本）

    Args:
        results: 回测结果字典
        historical_data: 历史数据 {symbol: DataFrame}（包含扩展的长历史数据）
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

    # 获取回测配置（用于SHORT-KLINE裁剪）
    backtest_config = results.get('backtest_config', {})
    start_date = backtest_config.get('start_date')
    end_date = backtest_config.get('end_date')

    # 为每只交易股票生成图表
    chart_files = []
    total_stocks = len(trades_by_symbol)

    logger.info(f"开始为 {total_stocks} 只股票生成K线图（LONG和SHORT两种版本）...")

    for idx, (symbol, symbol_trades) in enumerate(trades_by_symbol.items(), 1):
        try:
            logger.info(f"[{idx}/{total_stocks}] 生成 {symbol} 的K线图")

            # 获取该股票的历史数据
            if symbol not in historical_data:
                logger.warning(f"股票 {symbol} 没有历史数据，跳过")
                continue

            data_long = historical_data[symbol]  # 完整的长历史数据
            stock_name = symbol_to_name.get(symbol, symbol)

            # 生成LONG-KLINE图（使用完整历史数据）
            if use_mplfinance:
                chart_file_long = _generate_mplfinance_chart(
                    symbol, stock_name, data_long, symbol_trades, charts_dir, chart_type='LONG'
                )
            else:
                chart_file_long = _generate_matplotlib_chart(
                    symbol, stock_name, data_long, symbol_trades, charts_dir, chart_type='LONG'
                )

            if chart_file_long:
                chart_files.append(chart_file_long)
                logger.info(f"  ✓ 已生成LONG-KLINE: {os.path.basename(chart_file_long)}")

            # 生成SHORT-KLINE图（裁剪为回测期间+前1个月）
            if start_date and end_date:
                data_short = _prepare_short_kline_data(data_long, start_date, end_date)

                if data_short is not None and len(data_short) > 0:
                    if use_mplfinance:
                        chart_file_short = _generate_mplfinance_chart(
                            symbol, stock_name, data_short, symbol_trades, charts_dir, chart_type='SHORT'
                        )
                    else:
                        chart_file_short = _generate_matplotlib_chart(
                            symbol, stock_name, data_short, symbol_trades, charts_dir, chart_type='SHORT'
                        )

                    if chart_file_short:
                        chart_files.append(chart_file_short)
                        logger.info(f"  ✓ 已生成SHORT-KLINE: {os.path.basename(chart_file_short)}")
                else:
                    logger.warning(f"  股票 {symbol} SHORT-KLINE数据不足，跳过")
            else:
                logger.warning(f"  缺少回测配置，跳过SHORT-KLINE生成")

        except Exception as e:
            logger.error(f"生成 {symbol} 图表失败: {e}")
            continue

    logger.info(f"K线图生成完成，共 {len(chart_files)} 个文件")
    return chart_files


def _prepare_short_kline_data(data, start_date: str, end_date: str):
    """
    为SHORT-KLINE裁剪数据：保留回测开始日期前1个月 到 回测结束日期

    Args:
        data: 完整的历史数据DataFrame
        start_date: 回测开始日期 "YYYY-MM-DD"
        end_date: 回测结束日期 "YYYY-MM-DD"

    Returns:
        裁剪后的数据DataFrame
    """
    import pandas as pd
    from datetime import datetime, timedelta

    try:
        # 计算SHORT-KLINE的开始日期（回测开始前1个月）
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        short_start_dt = start_dt - timedelta(days=30)  # 向前扩展1个月
        short_start = short_start_dt.strftime("%Y-%m-%d")

        # 转换为Timestamp确保比较正确
        short_start_ts = pd.Timestamp(short_start)
        end_date_ts = pd.Timestamp(end_date)

        # 裁剪数据并创建副本（避免视图问题）
        data_short = data[(data.index >= short_start_ts) & (data.index <= end_date_ts)].copy()

        # 使用print确保输出（日志可能被过滤）
        print(f"\n[SHORT-KLINE裁剪] 目标范围: {short_start} 至 {end_date}")
        print(f"[SHORT-KLINE裁剪] 原始数据: {len(data)} 条, 裁剪后: {len(data_short)} 条")
        if len(data) > 0:
            print(f"[SHORT-KLINE裁剪] 原始数据范围: {data.index[0]} 至 {data.index[-1]}")
        if len(data_short) > 0:
            print(f"[SHORT-KLINE裁剪] 裁剪后范围: {data_short.index[0]} 至 {data_short.index[-1]}")

        logger.info(f"SHORT-KLINE数据裁剪: {short_start} 至 {end_date}, 共 {len(data_short)} 条记录")
        logger.info(f"  原始数据: {len(data)} 条, 裁剪后: {len(data_short)} 条")
        if len(data_short) > 0:
            logger.info(f"  实际范围: {data_short.index[0]} 至 {data_short.index[-1]}")

        return data_short

    except Exception as e:
        logger.error(f"裁剪SHORT-KLINE数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def _generate_mplfinance_chart(symbol: str, stock_name: str, data, trades: List[Dict],
                               output_dir: str, chart_type: str = 'LONG') -> str:
    """
    使用mplfinance生成专业K线图

    Args:
        symbol: 股票代码
        stock_name: 股票名称
        data: K线数据
        trades: 交易记录
        output_dir: 输出目录
        chart_type: 图表类型 'LONG' 或 'SHORT'

    Returns:
        生成的图表文件路径
    """
    import pandas as pd
    import mplfinance as mpf

    # 准备买卖点标记
    buy_dates = []
    buy_prices = []
    sell_dates = []
    sell_prices = []

    # 准备被跳过的买点标记
    missed_buy_dates = []
    missed_buy_prices = []

    for trade in trades:
        trade_date = pd.to_datetime(trade.get('date', ''))
        trade_price = trade.get('price', 0)

        if trade.get('action') == '买入':
            buy_dates.append(trade_date)
            buy_prices.append(trade_price)
        elif trade.get('action') == '卖出':
            sell_dates.append(trade_date)
            sell_prices.append(trade_price)

            # 提取持仓期间的重复买点
            missed_signals = trade.get('missed_buy_signals', [])
            for missed in missed_signals:
                missed_date = pd.to_datetime(missed['date'])
                missed_price = missed['price']
                missed_buy_dates.append(missed_date)
                missed_buy_prices.append(missed_price)

    # 创建买卖点Series
    buy_series = pd.Series(index=buy_dates, data=buy_prices)
    sell_series = pd.Series(index=sell_dates, data=sell_prices)
    missed_buy_series = pd.Series(index=missed_buy_dates, data=missed_buy_prices)

    # 准备附加图层
    apds = []
    if not buy_series.empty:
        # 真实买点：绿色实心向上三角形
        apds.append(mpf.make_addplot(buy_series, type='scatter', markersize=120,
                                     marker='^', color='green', label='真实买点'))
    if not missed_buy_series.empty:
        # 被跳过买点：橙色空心向上三角形
        apds.append(mpf.make_addplot(missed_buy_series, type='scatter', markersize=100,
                                     marker='^', color='orange', alpha=0.6,
                                     markerfacecolor='none', markeredgewidth=2,
                                     label='被跳过买点'))
    if not sell_series.empty:
        # 真实卖点：红色实心向下三角形
        apds.append(mpf.make_addplot(sell_series, type='scatter', markersize=120,
                                     marker='v', color='red', label='卖出'))


    # 图表样式
    mc = mpf.make_marketcolors(up='red', down='green', edge='inherit',
                               wick='inherit', volume='in')
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=False)

    # 生成文件名（添加chart_type标识）
    filename = f"{symbol}_{stock_name}_kline_{chart_type}.png"
    filepath = os.path.join(output_dir, filename)

    # 标题中添加类型标识
    title_suffix = "（完整历史）" if chart_type == 'LONG' else "（回测期间+1月）"
    chart_title = f"{stock_name}({symbol}) 回测交易K线图 {title_suffix}"

    # 绘制K线图
    mpf.plot(data, type='candle', style=s, addplot=apds if apds else None,
             title=chart_title,
             ylabel='价格',
             volume=True,
             savefig=dict(fname=filepath, dpi=150, bbox_inches='tight'))

    return filepath


def _generate_matplotlib_chart(symbol: str, stock_name: str, data, trades: List[Dict],
                               output_dir: str, chart_type: str = 'LONG') -> str:
    """
    使用matplotlib生成简化K线图（当mplfinance不可用时）

    Args:
        symbol: 股票代码
        stock_name: 股票名称
        data: K线数据
        trades: 交易记录
        output_dir: 输出目录
        chart_type: 图表类型 'LONG' 或 'SHORT'

    Returns:
        生成的图表文件路径
    """
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    # 创建图表
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10),
                                    gridspec_kw={'height_ratios': [3, 1]})

    # 绘制收盘价折线图（简化版K线）
    ax1.plot(data.index, data['Close'], label='收盘价', linewidth=1.5, color='blue')

    # 准备被跳过的买点数据
    missed_buy_dates = []
    missed_buy_prices = []

    # 标注买卖点
    for trade in trades:
        trade_date = pd.to_datetime(trade.get('date', ''))
        trade_price = trade.get('price', 0)

        if trade.get('action') == '买入':
            # 真实买点：绿色实心向上三角形
            ax1.scatter(trade_date, trade_price, marker='^', color='green',
                       s=250, zorder=5, edgecolors='darkgreen', linewidth=1.5,
                       label='真实买点' if '真实买点' not in [t.get_label() for t in ax1.get_children()] else '')
            ax1.annotate('买', xy=(trade_date, trade_price),
                        xytext=(0, 12), textcoords='offset points',
                        ha='center', fontsize=10, color='green', weight='bold')

        elif trade.get('action') == '卖出':
            # 真实卖点：红色实心向下三角形
            ax1.scatter(trade_date, trade_price, marker='v', color='red',
                       s=250, zorder=5, edgecolors='darkred', linewidth=1.5,
                       label='卖出' if '卖出' not in [t.get_label() for t in ax1.get_children()] else '')
            ax1.annotate('卖', xy=(trade_date, trade_price),
                        xytext=(0, -18), textcoords='offset points',
                        ha='center', fontsize=10, color='red', weight='bold')

            # 收集持仓期间的重复买点
            missed_signals = trade.get('missed_buy_signals', [])
            for missed in missed_signals:
                missed_date = pd.to_datetime(missed['date'])
                missed_price = missed['price']
                missed_buy_dates.append(missed_date)
                missed_buy_prices.append(missed_price)

    # 标注被跳过的买点（橙色空心三角形）
    if missed_buy_dates:
        ax1.scatter(missed_buy_dates, missed_buy_prices, marker='^',
                   facecolors='none', edgecolors='orange', s=200, linewidth=2.5,
                   zorder=4, alpha=0.8, label='被跳过买点')
        for missed_date, missed_price in zip(missed_buy_dates, missed_buy_prices):
            ax1.annotate('跳', xy=(missed_date, missed_price),
                        xytext=(0, 12), textcoords='offset points',
                        ha='center', fontsize=8, color='orange', weight='bold', alpha=0.7)


    # 设置标题和标签
    title_suffix = "（完整历史）" if chart_type == 'LONG' else "（回测期间+1月）"
    chart_title = f"{stock_name}({symbol}) 回测交易K线图 {title_suffix}"
    ax1.set_title(chart_title, fontsize=14, weight='bold')
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

    # 保存图表（添加chart_type标识）
    filename = f"{symbol}_{stock_name}_kline_{chart_type}.png"
    filepath = os.path.join(output_dir, filename)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return filepath
