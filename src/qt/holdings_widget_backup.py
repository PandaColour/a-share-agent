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
import akshare as ak
from src.utils.trading_calendar import trading_calendar, calculate_position_metrics


class HoldingsRefreshThread(QThread):
    """刷新持仓数据的后台线程"""
    data_signal = pyqtSignal(list)  # 发送持仓数据
    error_signal = pyqtSignal(str)  # 发送错误信息

    def __init__(self):
        super().__init__()
        self.hold_stocks = []

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

            self.hold_stocks = config.get('hold_stocks', [])

            # 为每只股票获取实时价格并计算指标
            for stock in self.hold_stocks:
                try:
                    # 获取实时价格
                    symbol = stock.get('symbol', '')
                    if symbol.endswith('.SZ'):
                        code = symbol[:-3]
                        real_time_data = ak.stock_zh_a_spot_em()
                        stock_row = real_time_data[real_time_data['代码'] == code]
                        if not stock_row.empty:
                            current_price = float(stock_row.iloc[0]['最新价'])
                        else:
                            current_price = stock.get('cost', 0.0)
                    elif symbol.endswith('.SH'):
                        code = symbol[:-3]
                        real_time_data = ak.stock_zh_a_spot_em()
                        stock_row = real_time_data[real_time_data['代码'] == code]
                        if not stock_row.empty:
                            current_price = float(stock_row.iloc[0]['最新价'])
                        else:
                            current_price = stock.get('cost', 0.0)
                    else:
                        current_price = stock.get('cost', 0.0)

                    # 设置当前价格
                    stock['current_price'] = current_price

                    # 使用 trading_calendar 计算所有指标
                    cost = stock.get('cost', 0.0)
                    purchase_date_str = stock.get('purchase_date', '')

                    if purchase_date_str:
                        try:
                            purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d')
                        except ValueError:
                            purchase_date = datetime.now()
                    else:
                        purchase_date = datetime.now()

                    # 使用统一的方法计算所有持仓指标
                    metrics = calculate_position_metrics(
                        cost_price=cost,
                        current_price=current_price,
                        purchase_date=purchase_date
                    )

                    # 将计算结果更新到股票数据中
                    stock.update(metrics)

                except Exception as stock_error:
                    # 如果某只股票获取失败，使用默认值
                    cost = stock.get('cost', 0.0)
                    stock['current_price'] = cost

                    # 获取默认指标（当前价=成本价，无盈亏）
                    purchase_date = datetime.now()
                    metrics = calculate_position_metrics(cost, cost, purchase_date)
                    metrics['risk_warning'] = '[错误] 数据获取失败'
                    stock.update(metrics)

            self.data_signal.emit(self.hold_stocks)

        except Exception as e:
            self.error_signal.emit(f"刷新失败: {str(e)}")


class HoldingsWidget(QWidget):
    """持股跟踪模块"""

    def __init__(self):
        super().__init__()
        self.refresh_thread = None
        self.init_ui()
        # 初始加载数据 - 添加异常处理
        try:
            self.refresh_holdings()
        except Exception as e:
            # 如果刷新失败，显示错误信息但不阻止程序启动
            if hasattr(self, 'status_label'):
                self.status_label.setText("初始化数据加载失败")
                self.status_label.setStyleSheet("color: #f44336; padding: 5px;")
            print(f"持仓数据初始化失败: {e}")

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
        self.holdings_table.setColumnCount(11)
        self.holdings_table.setHorizontalHeaderLabels([
            "股票代码", "股票名称", "买入日期", "持股天数", "成本价", "当前价",
            "盈亏", "止损价格", "盈利目标", "日均盈利", "风险提示"
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
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)

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

        total_profit = 0.0

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

            # 持股天数（交易日）
            holding_days = stock.get('holding_days', 0)
            days_item = QTableWidgetItem(f"{holding_days}天")
            days_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.holdings_table.setItem(row, 3, days_item)

            # 成本价
            cost = stock.get('cost', 0.0)
            cost_item = QTableWidgetItem(f"¥{cost:.2f}")
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.holdings_table.setItem(row, 4, cost_item)

            # 获取所有指标（现在都包含在stock中）
            profit = stock.get('profit', 0.0)
            profit_percent = stock.get('profit_percent', 0.0)
            current_price = stock.get('current_price', cost)
            stop_loss_price = stock.get('stop_loss_price', cost * 0.9)
            profit_target = stock.get('profit_target', cost * 1.05)
            avg_daily_profit = stock.get('avg_daily_profit', 0.0)
            risk_warning = stock.get('risk_warning', '')

            # 当前价
            price_item = QTableWidgetItem(f"¥{current_price:.2f}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if current_price > cost:
                price_item.setForeground(QColor(244, 67, 54))  # 红色
            elif current_price < cost:
                price_item.setForeground(QColor(76, 175, 80))  # 绿色
            self.holdings_table.setItem(row, 5, price_item)

            # 盈亏
            profit_item = QTableWidgetItem(f"{profit:+.2f} ({profit_percent:+.2f}%)")
            profit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if profit > 0:
                profit_item.setForeground(QColor(244, 67, 54))  # 红色
            elif profit < 0:
                profit_item.setForeground(QColor(76, 175, 80))  # 绿色
            self.holdings_table.setItem(row, 6, profit_item)

            # 止损价格（成本价-10%）
            stop_loss_item = QTableWidgetItem(f"¥{stop_loss_price:.2f}")
            stop_loss_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            stop_loss_item.setForeground(QColor(255, 152, 0))  # 橙色警告
            self.holdings_table.setItem(row, 7, stop_loss_item)

            # 盈利目标（成本价+5%）
            target_item = QTableWidgetItem(f"¥{profit_target:.2f}")
            target_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            target_item.setForeground(QColor(156, 39, 176))  # 紫色目标
            self.holdings_table.setItem(row, 8, target_item)

            # 平均日盈利
            daily_profit_item = QTableWidgetItem(f"¥{avg_daily_profit:+.2f}")
            daily_profit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if avg_daily_profit > 0:
                daily_profit_item.setForeground(QColor(244, 67, 54))  # 红色
            elif avg_daily_profit < 0:
                daily_profit_item.setForeground(QColor(76, 175, 80))  # 绿色
            self.holdings_table.setItem(row, 9, daily_profit_item)

            # 风险提示
            risk_item = QTableWidgetItem(risk_warning)
            risk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if '[警告]' in risk_warning:
                risk_item.setForeground(QColor(255, 87, 34))  # 深橙色警告
            elif '[目标]' in risk_warning:
                risk_item.setForeground(QColor(76, 175, 80))  # 绿色成功
            elif '[错误]' in risk_warning:
                risk_item.setForeground(QColor(244, 67, 54))  # 红色错误
            self.holdings_table.setItem(row, 10, risk_item)

            # 累计总盈亏
            total_profit += profit

        # 更新统计信息
        total_profit_percent = (total_profit / sum(stock.get('cost', 0.0) for stock in holdings) * 100) if holdings else 0
        self.total_label.setText(f"总持仓: {len(holdings)}")
        self.profit_label.setText(f"总盈亏: {total_profit:+.2f} ({total_profit_percent:+.2f}%)")

        # 总盈亏颜色
        if total_profit > 0:
            self.profit_label.setStyleSheet("font-size: 12pt; font-weight: bold; padding: 5px; color: #F44336;")
        elif total_profit < 0:
            self.profit_label.setStyleSheet("font-size: 12pt; font-weight: bold; padding: 5px; color: #4CAF50;")
        else:
            self.profit_label.setStyleSheet("font-size: 12pt; font-weight: bold; padding: 5px; color: #666666;")

        # 更新状态
        self.status_label.setText(f"刷新完成 - {datetime.now().strftime('%H:%M:%S')}")
        self.status_label.setStyleSheet("color: #4CAF50; padding: 5px;")

    def show_error(self, error_msg):
        """显示错误"""
        QMessageBox.warning(self, "错误", error_msg)
        self.status_label.setText("刷新失败")
        self.status_label.setStyleSheet("color: #f44336; padding: 5px;")
