# -*- coding: utf-8 -*-
"""
持仓配置文件 I/O 工具
"""
import os
import json
from datetime import datetime

HOLD_STOCK_PATH = os.path.join("config", "hold_stock.json")


def load_hold_stocks():
    """加载持仓配置，返回股票列表"""
    if not os.path.exists(HOLD_STOCK_PATH):
        return []
    with open(HOLD_STOCK_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config.get('hold_stocks', [])


def _read_config():
    with open(HOLD_STOCK_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write_config(config):
    config['last_updated'] = datetime.now().strftime('%Y-%m-%d')
    with open(HOLD_STOCK_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def update_stock_in_hold_config(symbol, updates):
    """更新持仓配置中指定股票的字段"""
    config = _read_config()
    hold_stocks = config.get('hold_stocks', [])
    for stock in hold_stocks:
        if stock.get('symbol') == symbol:
            stock.update(updates)
            _write_config(config)
            return
    raise ValueError(f"未找到股票 {symbol}")


def add_stock_to_hold_config(stock_data):
    """添加新股票到持仓配置"""
    config = _read_config()
    config.setdefault('hold_stocks', []).append(stock_data)
    _write_config(config)
