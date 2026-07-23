# -*- coding: utf-8 -*-
"""
股票对比模块 - 对比 dynamic_stock.json 和 hold_stock.json
显示仅在 dynamic 中的股票，支持一键加入持仓
"""
import os
import json
from datetime import datetime

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTableWidget, QTableWidgetItem, QGroupBox, QLabel,
                             QHeaderView, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from src.utils.hold_stock_io import BUY_STATUS, load_hold_stocks, add_stock_to_hold_config


def load_dynamic_stocks():
    """加载动态选股数据"""
    config_path = os.path.join("config", "dynamic_stock.json")
    if not os.path.exists(config_path):
        return []
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('stocks', [])


class StockComparisonWidget(QWidget):
    """股票对比模块 - 显示仅在动态选股中的股票"""

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_comparison_data()

    def init_ui(self):
        layout = QVBoxLayout()

        # 标题和工具栏
        header_layout = QHBoxLayout()

        title_label = QLabel("股票对比")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 3px;
                padding: 5px 15px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.refresh_btn.clicked.connect(self.load_comparison_data)
        header_layout.addWidget(self.refresh_btn)

        layout.addLayout(header_layout)

        # 说明标签
        hint_label = QLabel('以下股票在动态选股结果中，但不在当前持仓中。点击"保存"可将其加入持仓。')
        hint_label.setStyleSheet("color: #666666; padding: 5px;")
        layout.addWidget(hint_label)

        # 对比表格
        table_group = QGroupBox("仅动态选股中的股票")
        table_layout = QVBoxLayout()

        self.comparison_table = QTableWidget()
        self.comparison_table.setColumnCount(8)
        self.comparison_table.setHorizontalHeaderLabels([
            "股票代码", "股票名称", "市场", "行业板块", "来源", "评分", "涨跌幅(%)", "操作"
        ])

        self.comparison_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                gridline-color: #ddd;
                background-color: white;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)

        header = self.comparison_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.comparison_table.setColumnWidth(0, 100)
        self.comparison_table.setColumnWidth(1, 100)
        self.comparison_table.setColumnWidth(2, 60)
        self.comparison_table.setColumnWidth(3, 120)
        self.comparison_table.setColumnWidth(4, 80)
        self.comparison_table.setColumnWidth(5, 60)
        self.comparison_table.setColumnWidth(6, 80)
        self.comparison_table.setColumnWidth(7, 80)

        self.comparison_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        table_layout.addWidget(self.comparison_table)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # 统计信息
        stats_layout = QHBoxLayout()

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("font-size: 11pt; padding: 5px; color: #666666;")
        stats_layout.addWidget(self.stats_label)

        stats_layout.addStretch()

        layout.addLayout(stats_layout)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666666; padding: 5px;")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def load_comparison_data(self):
        """加载并对比两个数据源"""
        dynamic_stocks = load_dynamic_stocks()
        hold_stocks = load_hold_stocks()

        hold_symbols = {s.get('symbol', '') for s in hold_stocks}

        # 找出仅在 dynamic 中但不在 hold 中的股票
        only_in_dynamic = [s for s in dynamic_stocks if s.get('symbol', '') not in hold_symbols]

        self.update_comparison_table(only_in_dynamic)

        total_dynamic = len(dynamic_stocks)
        total_hold = len(hold_stocks)
        self.stats_label.setText(
            f"动态选股共 {total_dynamic} 只，持仓共 {total_hold} 只，"
            f"仅在动态中: {len(only_in_dynamic)} 只"
        )

        self.status_label.setText(f"刷新完成 - {datetime.now().strftime('%H:%M:%S')}")
        self.status_label.setStyleSheet("color: #4CAF50; padding: 5px;")

    def update_comparison_table(self, stocks):
        """更新对比表格"""
        self.comparison_table.setRowCount(len(stocks))

        for row, stock in enumerate(stocks):
            # 股票代码
            symbol_item = QTableWidgetItem(stock.get('symbol', ''))
            symbol_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.comparison_table.setItem(row, 0, symbol_item)

            # 股票名称
            name_item = QTableWidgetItem(stock.get('name', ''))
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.comparison_table.setItem(row, 1, name_item)

            # 市场
            market = stock.get('market', '')
            market_item = QTableWidgetItem(market)
            market_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.comparison_table.setItem(row, 2, market_item)

            # 行业板块
            sector = stock.get('sector', '')
            sector_item = QTableWidgetItem(sector)
            sector_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.comparison_table.setItem(row, 3, sector_item)

            # 来源
            source = stock.get('source', '')
            source_item = QTableWidgetItem(source)
            source_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.comparison_table.setItem(row, 4, source_item)

            # 评分
            score = stock.get('score', 0.0)
            score_item = QTableWidgetItem(f"{score:.1f}")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.comparison_table.setItem(row, 5, score_item)

            # 涨跌幅
            change_pct = stock.get('change_pct', 0.0)
            change_item = QTableWidgetItem(f"{change_pct:+.2f}%")
            change_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if change_pct > 0:
                change_item.setForeground(QColor(244, 67, 54))
            elif change_pct < 0:
                change_item.setForeground(QColor(76, 175, 80))
            self.comparison_table.setItem(row, 6, change_item)

            # 保存按钮
            save_btn = QPushButton("保存")
            save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4caf50;
                    color: white;
                    border-radius: 3px;
                    padding: 5px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #388e3c;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #666666;
                }
            """)
            save_btn.clicked.connect(lambda checked, s=stock, b=save_btn: self.handle_save_stock(s, b))
            self.comparison_table.setCellWidget(row, 7, save_btn)

    def handle_save_stock(self, stock, btn):
        """将动态选股中的股票保存到持仓"""
        symbol = stock.get('symbol', '')
        name = stock.get('name', '')

        confirm = QMessageBox.question(
            self,
            "保存确认",
            f"确定要将 {name}({symbol}) 加入持仓吗？\n\n"
            f"加入后该股票的 buy_flag 将设为 buy。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self._add_to_hold(stock)
            btn.setEnabled(False)
            btn.setText("已保存")
            QMessageBox.information(self, "成功", f"已将 {name}({symbol}) 加入持仓！")
            self.status_label.setText(f"已保存 {name}({symbol}) 到持仓")
            self.status_label.setStyleSheet("color: #4CAF50; padding: 5px;")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")

    def _add_to_hold(self, stock):
        """将股票添加到 hold_stock.json"""
        new_stock = {
            "symbol": stock.get('symbol', ''),
            "name": stock.get('name', ''),
            "purchase_date": datetime.now().strftime('%Y-%m-%d'),
            "cost": round(stock.get('price', 0.0), 3),
            "buy_flag": BUY_STATUS
        }
        add_stock_to_hold_config(new_stock)
