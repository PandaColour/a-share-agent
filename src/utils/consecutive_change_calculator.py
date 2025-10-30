#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
连续涨跌计算器
用于计算股票的连续涨跌天数和连续涨跌幅度
"""

import pandas as pd
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


def calculate_consecutive_changes(data: pd.DataFrame) -> Dict[str, any]:
    """
    计算股票的连续涨跌统计

    Args:
        data: 股票历史数据 DataFrame，必须包含 'Close' 列

    Returns:
        dict: 包含连续涨跌日和连续涨跌幅度的字典
        {
            'consecutive_days': int,  # 连续涨跌天数（正数表示涨，负数表示跌）
            'consecutive_change': float,  # 连续涨跌幅度（百分比）
            'consecutive_change_amount': float,  # 连续涨跌金额
            'start_price': float,  # 连续变化开始时的价格
            'end_price': float,  # 连续变化结束时的价格（当前价格）
        }
    """
    try:
        if data is None or data.empty or 'Close' not in data.columns:
            logger.warning("数据为空或缺少Close列，无法计算连续涨跌")
            return {
                'consecutive_days': 0,
                'consecutive_change': 0.0,
                'consecutive_change_amount': 0.0,
                'start_price': 0.0,
                'end_price': 0.0
            }

        # 确保数据按日期排序
        if not data.index.is_monotonic_increasing:
            data = data.sort_index()

        # 至少需要2天的数据
        if len(data) < 2:
            logger.warning("数据少于2天，无法计算连续涨跌")
            return {
                'consecutive_days': 0,
                'consecutive_change': 0.0,
                'consecutive_change_amount': 0.0,
                'start_price': 0.0,
                'end_price': 0.0
            }

        # 计算每日涨跌
        # 使用 shift() 计算前一天价格，然后判断涨跌
        data_copy = data[['Close']].copy()
        data_copy['prev_close'] = data_copy['Close'].shift(1)
        data_copy['change'] = data_copy['Close'] - data_copy['prev_close']
        data_copy['change_direction'] = 0  # 0表示平，1表示涨，-1表示跌

        # 设置涨跌方向
        data_copy.loc[data_copy['change'] > 0, 'change_direction'] = 1
        data_copy.loc[data_copy['change'] < 0, 'change_direction'] = -1

        # 从最后一天开始往前回溯，找到连续同方向的天数
        last_direction = data_copy['change_direction'].iloc[-1]

        # 如果最后一天是平盘，返回0
        if last_direction == 0:
            end_price = data_copy['Close'].iloc[-1]
            return {
                'consecutive_days': 0,
                'consecutive_change': 0.0,
                'consecutive_change_amount': 0.0,
                'start_price': end_price,
                'end_price': end_price
            }

        # 从倒数第二天开始往前找，直到方向不同
        consecutive_days = 1  # 至少包含最后一天
        consecutive_start_idx = len(data_copy) - 1

        for i in range(len(data_copy) - 2, 0, -1):  # 从倒数第二天开始，到第二天结束（第一天没有前一天数据）
            if data_copy['change_direction'].iloc[i] == last_direction:
                consecutive_days += 1
                consecutive_start_idx = i
            else:
                break

        # 计算连续涨跌幅度
        end_price = data_copy['Close'].iloc[-1]
        start_price = data_copy['prev_close'].iloc[consecutive_start_idx]  # 连续变化开始那天的前一天收盘价

        change_amount = end_price - start_price
        change_percent = (change_amount / start_price * 100) if start_price > 0 else 0.0

        # 根据方向设置正负号
        if last_direction < 0:
            consecutive_days = -consecutive_days

        result = {
            'consecutive_days': consecutive_days,
            'consecutive_change': change_percent,
            'consecutive_change_amount': change_amount,
            'start_price': start_price,
            'end_price': end_price
        }

        logger.debug(f"连续涨跌计算结果: {result}")
        return result

    except Exception as e:
        logger.error(f"计算连续涨跌失败: {e}")
        return {
            'consecutive_days': 0,
            'consecutive_change': 0.0,
            'consecutive_change_amount': 0.0,
            'start_price': 0.0,
            'end_price': 0.0
        }


def format_consecutive_days(days: int) -> str:
    """
    格式化连续涨跌天数显示

    Args:
        days: 连续天数（正数表示涨，负数表示跌）

    Returns:
        str: 格式化后的字符串，如 "+3天" 或 "-2天"
    """
    if days == 0:
        return "0天(平盘)"
    elif days > 0:
        return f"+{days}天"
    else:
        return f"{days}天"


def format_consecutive_change(change_percent: float) -> str:
    """
    格式化连续涨跌幅度显示

    Args:
        change_percent: 涨跌幅度百分比

    Returns:
        str: 格式化后的字符串，如 "+5.23%" 或 "-3.45%"
    """
    if change_percent >= 0:
        return f"+{change_percent:.2f}%"
    else:
        return f"{change_percent:.2f}%"
