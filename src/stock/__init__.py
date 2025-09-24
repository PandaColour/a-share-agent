# -*- coding: utf-8 -*-
"""
股票模块
提供股票选择和管理功能
"""

from .stock_selection_manager import StockSelectionManager

# 为了兼容旧的stock_list.py，提供便捷的函数接口
def get_all_stocks():
    """获取所有股票列表 (兼容旧的stock_list.py功能)"""
    manager = StockSelectionManager()
    return manager.get_all_stocks()

__all__ = ['StockSelectionManager', 'get_all_stocks']