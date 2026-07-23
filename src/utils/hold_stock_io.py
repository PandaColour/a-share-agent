# -*- coding: utf-8 -*-
"""
持仓配置文件 I/O 工具
"""
import os
import json
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Union

HOLD_STOCK_PATH = os.path.join("config", "hold_stock.json")
BUY_STATUS = "buy"
SELL_STATUS = "sell"
WATCH_STATUS = "watch"
VALID_BUY_STATUSES = {BUY_STATUS, SELL_STATUS, WATCH_STATUS}


def normalize_buy_flag(value) -> str:
    """将旧布尔 buy_flag 和新字符串状态统一为 buy/sell/watch。"""
    if value is True:
        return BUY_STATUS
    if value is False:
        return SELL_STATUS

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in VALID_BUY_STATUSES:
            return normalized

    return BUY_STATUS


def is_buy_status(value) -> bool:
    return normalize_buy_flag(value) == BUY_STATUS


def is_sell_status(value) -> bool:
    return normalize_buy_flag(value) == SELL_STATUS


def is_watch_status(value) -> bool:
    return normalize_buy_flag(value) == WATCH_STATUS


def load_hold_stocks(hold_stock_path: Optional[Union[str, Path]] = None):
    """加载持仓配置，返回股票列表"""
    config_path = Path(hold_stock_path or HOLD_STOCK_PATH)
    if not config_path.exists():
        return []
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return normalize_hold_stocks(config.get('hold_stocks', []))


def normalize_hold_stocks(hold_stocks: List[Dict]) -> List[Dict]:
    """返回 buy_flag 已规范化的新持仓列表，不修改输入对象。"""
    normalized_stocks = []
    for stock in hold_stocks:
        normalized_stock = dict(stock)
        normalized_stock['buy_flag'] = normalize_buy_flag(stock.get('buy_flag', BUY_STATUS))
        normalized_stocks.append(normalized_stock)
    return normalized_stocks


def _read_config(hold_stock_path: Optional[Union[str, Path]] = None):
    config_path = Path(hold_stock_path or HOLD_STOCK_PATH)
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write_config(config, hold_stock_path: Optional[Union[str, Path]] = None):
    config['last_updated'] = datetime.now().strftime('%Y-%m-%d')
    config['hold_stocks'] = normalize_hold_stocks(config.get('hold_stocks', []))
    config_path = Path(hold_stock_path or HOLD_STOCK_PATH)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def update_stock_in_hold_config(symbol, updates, hold_stock_path: Optional[Union[str, Path]] = None):
    """更新持仓配置中指定股票的字段"""
    config = _read_config(hold_stock_path)
    hold_stocks = config.get('hold_stocks', [])
    for stock in hold_stocks:
        if stock.get('symbol') == symbol:
            if 'buy_flag' in updates:
                updates = dict(updates)
                updates['buy_flag'] = normalize_buy_flag(updates['buy_flag'])
            stock.update(updates)
            _write_config(config, hold_stock_path)
            return
    raise ValueError(f"未找到股票 {symbol}")


def add_stock_to_hold_config(stock_data, hold_stock_path: Optional[Union[str, Path]] = None):
    """添加新股票到持仓配置"""
    config = _read_config(hold_stock_path)
    normalized_stock = dict(stock_data)
    normalized_stock['buy_flag'] = normalize_buy_flag(normalized_stock.get('buy_flag', BUY_STATUS))
    config.setdefault('hold_stocks', []).append(normalized_stock)
    _write_config(config, hold_stock_path)


def add_buy_recommendations_to_watch(analysis_results: List[Dict],
                                     as_of_date: Optional[str] = None,
                                     hold_stock_path: Optional[Union[str, Path]] = None) -> Dict:
    """把分析结果中新增的买入推荐加入 hold_stock.json 的 watch 状态。"""
    config = _read_config(hold_stock_path)
    hold_stocks = config.setdefault('hold_stocks', [])
    hold_stocks[:] = normalize_hold_stocks(hold_stocks)
    stock_by_symbol = {stock.get('symbol'): stock for stock in hold_stocks}
    watch_date = as_of_date or date.today().strftime('%Y-%m-%d')

    added_symbols = []
    updated_symbols = []
    skipped_symbols = []

    for result in analysis_results:
        symbol = result.get('股票代码') or result.get('symbol')
        if not symbol:
            continue

        if result.get('操作建议') != '买入':
            continue

        current_price = _parse_price(result.get('当前价格'))

        existing_stock = stock_by_symbol.get(symbol)
        if existing_stock:
            if is_sell_status(existing_stock.get('buy_flag')):
                existing_stock.update({
                    'purchase_date': watch_date,
                    'cost': current_price,
                    'buy_flag': WATCH_STATUS
                })
                updated_symbols.append(symbol)
                continue

            skipped_symbols.append(symbol)
            continue

        stock = {
            'symbol': symbol,
            'name': result.get('股票名称') or result.get('name') or symbol,
            'purchase_date': watch_date,
            'cost': current_price,
            'buy_flag': WATCH_STATUS
        }

        hold_stocks.append(stock)
        stock_by_symbol[symbol] = stock
        added_symbols.append(symbol)

    if added_symbols or updated_symbols:
        _write_config(config, hold_stock_path)
    else:
        config['hold_stocks'] = normalize_hold_stocks(config.get('hold_stocks', []))

    return {
        'added_count': len(added_symbols),
        'added_symbols': added_symbols,
        'updated_count': len(updated_symbols),
        'updated_symbols': updated_symbols,
        'skipped_count': len(skipped_symbols),
        'skipped_symbols': skipped_symbols
    }


def _parse_price(price_value) -> float:
    if price_value is None:
        return 0.0

    if isinstance(price_value, (int, float)):
        return float(price_value)

    price_text = str(price_value).strip()
    if not price_text or price_text.upper() == 'N/A':
        return 0.0

    try:
        return float(price_text.replace('元', '').replace(',', ''))
    except ValueError:
        return 0.0
