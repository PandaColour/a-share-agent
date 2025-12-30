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


def load_holdings_config():
    """加载持仓配置"""
    try:
        config_path = os.path.join("config", "hold_stock.json")
        if not os.path.exists(config_path):
            return []

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        return config.get('hold_stocks', [])
    except Exception as e:
        print(f"加载持仓配置失败: {e}")
        return []

def get_stock_current_price(symbol: str):
    """获取股票当前价格"""
    from datetime import datetime, timedelta

    try:
        # 统一处理股票代码
        if symbol.endswith(('.SZ', '.SH')):
            code = symbol[:-3]
        else:
            code = symbol

        # 方法1: 尝试实时行情（优先）
        try:
            data = ak.stock_zh_a_spot_em()
            stock_row = data[data['代码'] == code]
            if not stock_row.empty:
                price = float(stock_row.iloc[0]['最新价'])
                print(f"实时行情获取成功: {symbol} = {price}")
                return price
        except Exception as e:
            print(f"实时行情获取失败: {e}")

        # 方法2: 使用历史数据（获取到今天的数据）
        try:
            # 计算日期范围：从30天前到今天
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')

            data = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date)
            if not data.empty:
                price = float(data.iloc[-1]['收盘'])
                latest_date = data.iloc[-1]['日期']
                print(f"历史数据获取成功: {symbol} = {price} (日期: {latest_date})")
                return price
        except Exception as e:
            print(f"历史数据获取失败: {e}")

        # 方法3: 尝试单只股票历史数据（另一种接口）
        try:
            # 使用更近期的数据
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')

            data = ak.stock_zh_a_daily(symbol=f"sh{code}" if symbol.endswith('.SH') else f"sz{code}",
                                      start_date=start_date, end_date=end_date)
            if not data.empty:
                price = float(data.iloc[-1]['close'])
                print(f"单只股票数据获取成功: {symbol} = {price}")
                return price
        except Exception as e:
            print(f"单只股票数据获取失败: {e}")

        print(f"所有方法都失败了: {symbol}")

    except Exception as e:
        print(f"获取股票 {symbol} 价格失败: {e}")

    return None


class HoldingsWidget(QWidget):
    """持股跟踪模块"""

    def __init__(self):
        super().__init__()
        self.init_ui()
        # 不在启动时自动刷新，用户需要手动点击刷新按钮

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
        self.holdings_table.setColumnCount(10)
        self.holdings_table.setHorizontalHeaderLabels([
            "股票代码", "股票名称", "买入日期", "持股天数", "成本价", "当前价",
            "盈亏", "日均盈利", "风险提示", "操作"
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

        # 设置列宽 - 允许用户手动调整
        header = self.holdings_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # 所有列都可以手动调整

        # 设置初始列宽
        self.holdings_table.setColumnWidth(0, 100)  # 股票代码
        self.holdings_table.setColumnWidth(1, 100)  # 股票名称
        self.holdings_table.setColumnWidth(2, 100)  # 买入日期
        self.holdings_table.setColumnWidth(3, 80)   # 持股天数
        self.holdings_table.setColumnWidth(4, 80)   # 成本价
        self.holdings_table.setColumnWidth(5, 80)   # 当前价
        self.holdings_table.setColumnWidth(6, 120)  # 盈亏
        self.holdings_table.setColumnWidth(7, 90)   # 日均盈利
        self.holdings_table.setColumnWidth(8, 200)  # 风险提示
        self.holdings_table.setColumnWidth(9, 80)   # 操作

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
        self.status_label = QLabel("就绪 - 点击刷新按钮获取最新数据")
        self.status_label.setStyleSheet("color: #666666; padding: 5px;")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def refresh_holdings(self):
        """刷新持仓数据（同步方式）"""
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("正在刷新...")
        self.status_label.setStyleSheet("color: #FF9800; padding: 5px;")

        # 直接在主线程中处理，避免线程问题
        try:
            # 加载持仓配置
            hold_stocks = load_holdings_config()

            if not hold_stocks:
                self.show_error("未找到持仓配置或配置为空")
                self.refresh_btn.setEnabled(True)
                return

            # 处理每只股票的数据
            processed_stocks = []
            for stock in hold_stocks:
                # 复制原始数据
                processed_stock = stock.copy()

                # 获取当前价格
                symbol = processed_stock.get('symbol', '')
                current_price = get_stock_current_price(symbol)

                if current_price is None:
                    current_price = processed_stock.get('cost', 0.0)
                    print(f"使用成本价作为当前价格: {symbol}")

                processed_stock['current_price'] = current_price

                # 计算持仓指标
                cost = processed_stock.get('cost', 0.0)
                purchase_date_str = processed_stock.get('purchase_date', '')

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

                # 将计算结果更新到股票数据中，但过滤掉不需要显示的datetime对象
                display_metrics = {k: v for k, v in metrics.items() if k not in ['purchase_date', 'current_date']}
                processed_stock.update(display_metrics)
                processed_stocks.append(processed_stock)

            # 更新表格
            self.update_holdings_table(processed_stocks)

        except Exception as e:
            self.show_error(f"刷新失败: {str(e)}")
        finally:
            self.refresh_btn.setEnabled(True)

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

            # 平均日盈利
            daily_profit_item = QTableWidgetItem(f"¥{avg_daily_profit:+.2f}")
            daily_profit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if avg_daily_profit > 0:
                daily_profit_item.setForeground(QColor(244, 67, 54))  # 红色
            elif avg_daily_profit < 0:
                daily_profit_item.setForeground(QColor(76, 175, 80))  # 绿色
            self.holdings_table.setItem(row, 7, daily_profit_item)

            # 风险提示
            risk_item = QTableWidgetItem(risk_warning)
            risk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if '[警告]' in risk_warning:
                risk_item.setForeground(QColor(255, 87, 34))  # 深橙色警告
            elif '[目标]' in risk_warning:
                risk_item.setForeground(QColor(76, 175, 80))  # 绿色成功
            elif '[错误]' in risk_warning:
                risk_item.setForeground(QColor(244, 67, 54))  # 红色错误
            self.holdings_table.setItem(row, 8, risk_item)

            # 操作按钮
            buy_flag = stock.get('buy_flag', True)
            operation_btn = QPushButton("卖出" if buy_flag else "买入")
            operation_btn.setStyleSheet("""
                QPushButton {
                    background-color: %s;
                    color: white;
                    border-radius: 3px;
                    padding: 5px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: %s;
                }
            """ % (("#f44336", "#d32f2f") if buy_flag else ("#4caf50", "#388e3c")))
            operation_btn.clicked.connect(lambda checked, s=stock: self.handle_trade_action(s))
            self.holdings_table.setCellWidget(row, 9, operation_btn)

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

    def handle_trade_action(self, stock):
        """处理买入/卖出操作"""
        symbol = stock.get('symbol', '')
        name = stock.get('name', '')
        buy_flag = stock.get('buy_flag', True)

        # 确认对话框
        action_text = "卖出" if buy_flag else "买入"
        confirm = QMessageBox.question(
            self,
            f"{action_text}确认",
            f"确定要{action_text} {name}({symbol}) 吗?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            # 找到当前股票在表格中的行号
            row = -1
            for i in range(self.holdings_table.rowCount()):
                if self.holdings_table.item(i, 0).text() == symbol:
                    row = i
                    break

            if row == -1:
                raise ValueError(f"未找到股票 {symbol} 在表格中的位置")

            # 更新 hold_stock.json
            if buy_flag:
                # 卖出：设置 buy_flag = false
                self.update_hold_stock_json(symbol, {'buy_flag': False})
                # 更新stock对象
                stock['buy_flag'] = False
                success_msg = f"已标记 {name} 为卖出状态"
            else:
                # 买入：设置 buy_flag = true，更新日期和成本
                current_price = stock.get('current_price', 0.0)
                today = datetime.now().strftime('%Y-%m-%d')
                updates = {
                    'buy_flag': True,
                    'purchase_date': today,
                    'cost': current_price
                }
                self.update_hold_stock_json(symbol, updates)
                # 更新stock对象
                stock.update(updates)
                success_msg = f"已标记 {name} 为买入状态\n买入日期: {today}\n买入价格: ¥{current_price:.2f}"

            # 立即更新当前行的按钮状态
            self.update_row_button(row, stock)

            # 如果是买入操作，需要重新计算持仓指标并更新显示
            if not buy_flag:  # 刚买入（原来是false，现在是true）
                # 重新计算指标
                cost = stock.get('cost', 0.0)
                current_price = stock.get('current_price', cost)
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

                # 更新stock数据
                display_metrics = {k: v for k, v in metrics.items() if k not in ['purchase_date', 'current_date']}
                stock.update(display_metrics)

                # 更新表格中的数据显示
                self.update_row_data(row, stock)

            QMessageBox.information(self, "成功", success_msg)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"操作失败: {str(e)}")

    def update_row_button(self, row, stock):
        """更新指定行的操作按钮"""
        buy_flag = stock.get('buy_flag', True)
        operation_btn = QPushButton("卖出" if buy_flag else "买入")
        operation_btn.setStyleSheet("""
            QPushButton {
                background-color: %s;
                color: white;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: %s;
            }
        """ % (("#f44336", "#d32f2f") if buy_flag else ("#4caf50", "#388e3c")))
        operation_btn.clicked.connect(lambda checked, s=stock: self.handle_trade_action(s))
        self.holdings_table.setCellWidget(row, 9, operation_btn)

    def update_row_data(self, row, stock):
        """更新指定行的数据显示"""
        # 买入日期
        date_item = QTableWidgetItem(stock.get('purchase_date', ''))
        date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.holdings_table.setItem(row, 2, date_item)

        # 持股天数
        holding_days = stock.get('holding_days', 0)
        days_item = QTableWidgetItem(f"{holding_days}天")
        days_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.holdings_table.setItem(row, 3, days_item)

        # 成本价
        cost = stock.get('cost', 0.0)
        cost_item = QTableWidgetItem(f"¥{cost:.2f}")
        cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.holdings_table.setItem(row, 4, cost_item)

        # 获取指标
        profit = stock.get('profit', 0.0)
        profit_percent = stock.get('profit_percent', 0.0)
        current_price = stock.get('current_price', cost)
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

        # 平均日盈利
        daily_profit_item = QTableWidgetItem(f"¥{avg_daily_profit:+.2f}")
        daily_profit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if avg_daily_profit > 0:
            daily_profit_item.setForeground(QColor(244, 67, 54))  # 红色
        elif avg_daily_profit < 0:
            daily_profit_item.setForeground(QColor(76, 175, 80))  # 绿色
        self.holdings_table.setItem(row, 7, daily_profit_item)

        # 风险提示
        risk_item = QTableWidgetItem(risk_warning)
        risk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if '[警告]' in risk_warning:
            risk_item.setForeground(QColor(255, 87, 34))  # 深橙色警告
        elif '[目标]' in risk_warning:
            risk_item.setForeground(QColor(76, 175, 80))  # 绿色成功
        elif '[错误]' in risk_warning:
            risk_item.setForeground(QColor(244, 67, 54))  # 红色错误
        self.holdings_table.setItem(row, 8, risk_item)

    def update_hold_stock_json(self, symbol, updates):
        """更新 hold_stock.json 文件中指定股票的字段"""
        try:
            config_path = os.path.join("config", "hold_stock.json")

            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 查找并更新指定股票
            hold_stocks = config.get('hold_stocks', [])
            updated = False

            for stock in hold_stocks:
                if stock.get('symbol') == symbol:
                    stock.update(updates)
                    updated = True
                    break

            if not updated:
                raise ValueError(f"未找到股票 {symbol}")

            # 更新 last_updated 时间戳
            config['last_updated'] = datetime.now().strftime('%Y-%m-%d')

            # 写回配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            print(f"已更新 {symbol} 的配置: {updates}")

        except Exception as e:
            print(f"更新配置文件失败: {e}")
            raise