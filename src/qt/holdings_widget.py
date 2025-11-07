# -*- coding: utf-8 -*-
"""
持股跟踪模块 - 显示持仓股票的实时状态
"""
import os
import json
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTableWidget, QTableWidgetItem, QGroupBox, QLabel,
                             QHeaderView, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class HoldingsRefreshThread(QThread):
    """刷新持仓数据的后台线程"""
    data_signal = pyqtSignal(list)  # 发送持仓数据
    error_signal = pyqtSignal(str)  # 发送错误信息

    def run(self):
        """刷新持仓数据"""
        try:
            # 读取持仓配置
            config_path = os.path.join("config", "hold_stock.json")
            if not os.path.exists(config_path):
                self.error_signal.emit("未找到持仓配置文件")
                return

            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            hold_stocks = config.get('hold_stocks', [])

            # 这里可以添加获取实时价格的逻辑
            # 目前先返回配置中的数据
            self.data_signal.emit(hold_stocks)

        except Exception as e:
            self.error_signal.emit(f"刷新失败: {str(e)}")


class HoldingsWidget(QWidget):
    """持股跟踪模块"""

    def __init__(self):
        super().__init__()
        self.refresh_thread = None
        self.init_ui()
        # 初始加载数据
        self.refresh_holdings()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # 标题和工具栏
        header_layout = QHBoxLayout()

        title_label = QLabel("持股跟踪")
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
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_holdings)
        header_layout.addWidget(self.refresh_btn)

        layout.addLayout(header_layout)

        # 持仓表格
        holdings_group = QGroupBox("持仓列表")
        holdings_layout = QVBoxLayout()

        self.holdings_table = QTableWidget()
        self.holdings_table.setColumnCount(6)
        self.holdings_table.setHorizontalHeaderLabels([
            "股票代码", "股票名称", "买入日期", "成本价", "当前价", "盈亏"
        ])

        # 设置表格样式
        self.holdings_table.setStyleSheet("""
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

        # 设置列宽
        header = self.holdings_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        # 禁止编辑
        self.holdings_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        holdings_layout.addWidget(self.holdings_table)
        holdings_group.setLayout(holdings_layout)
        layout.addWidget(holdings_group)

        # 统计信息
        stats_layout = QHBoxLayout()

        self.total_label = QLabel("总持仓: 0")
        self.total_label.setStyleSheet("font-size: 12pt; padding: 5px;")
        stats_layout.addWidget(self.total_label)

        stats_layout.addStretch()

        self.profit_label = QLabel("总盈亏: --")
        self.profit_label.setStyleSheet("font-size: 12pt; font-weight: bold; padding: 5px;")
        stats_layout.addWidget(self.profit_label)

        layout.addLayout(stats_layout)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666666; padding: 5px;")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def refresh_holdings(self):
        """刷新持仓数据"""
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("正在刷新...")
        self.status_label.setStyleSheet("color: #FF9800; padding: 5px;")

        # 启动刷新线程
        self.refresh_thread = HoldingsRefreshThread()
        self.refresh_thread.data_signal.connect(self.update_holdings_table)
        self.refresh_thread.error_signal.connect(self.show_error)
        self.refresh_thread.finished.connect(lambda: self.refresh_btn.setEnabled(True))
        self.refresh_thread.start()

    def update_holdings_table(self, holdings):
        """更新持仓表格"""
        self.holdings_table.setRowCount(len(holdings))

        for row, stock in enumerate(holdings):
            # 股票代码
            symbol_item = QTableWidgetItem(stock.get('symbol', ''))
            symbol_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.holdings_table.setItem(row, 0, symbol_item)

            # 股票名称
            name_item = QTableWidgetItem(stock.get('name', ''))
            self.holdings_table.setItem(row, 1, name_item)

            # 买入日期
            date_item = QTableWidgetItem(stock.get('purchase_date', ''))
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.holdings_table.setItem(row, 2, date_item)

            # 成本价
            cost = stock.get('cost', 0.0)
            cost_item = QTableWidgetItem(f"¥{cost:.2f}")
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.holdings_table.setItem(row, 3, cost_item)

            # 当前价（待实现实时价格获取）
            current_price = cost  # 暂时用成本价
            price_item = QTableWidgetItem(f"¥{current_price:.2f}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.holdings_table.setItem(row, 4, price_item)

            # 盈亏
            profit = current_price - cost
            profit_percent = (profit / cost * 100) if cost > 0 else 0
            profit_item = QTableWidgetItem(f"{profit:+.2f} ({profit_percent:+.2f}%)")
            profit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            # 根据盈亏设置颜色
            if profit > 0:
                profit_item.setForeground(QColor(244, 67, 54))  # 红色（中国股市涨用红色）
            elif profit < 0:
                profit_item.setForeground(QColor(76, 175, 80))  # 绿色（中国股市跌用绿色）

            self.holdings_table.setItem(row, 5, profit_item)

        # 更新统计信息
        self.total_label.setText(f"总持仓: {len(holdings)}")

        # 更新状态
        self.status_label.setText(f"刷新完成 - {datetime.now().strftime('%H:%M:%S')}")
        self.status_label.setStyleSheet("color: #4CAF50; padding: 5px;")

    def show_error(self, error_msg):
        """显示错误"""
        QMessageBox.warning(self, "错误", error_msg)
        self.status_label.setText("刷新失败")
        self.status_label.setStyleSheet("color: #f44336; padding: 5px;")
