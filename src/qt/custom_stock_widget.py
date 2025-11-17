# -*- coding: utf-8 -*-
"""
自定义股票分析部件
"""
import os
import sys
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLineEdit, QTextEdit, QLabel,
                             QListWidget, QListWidgetItem, QMessageBox,
                             QProgressBar, QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap

from src.qt.stock_validator import StockValidator


class CustomStockAnalysisThread(QThread):
    """自定义股票分析线程"""
    output_signal = pyqtSignal(str)  # 输出信号
    finished_signal = pyqtSignal(bool, str)  # 完成信号
    progress_signal = pyqtSignal(int)  # 进度信号

    def __init__(self, stock_list):
        super().__init__()
        self.stock_list = stock_list
        self.process = None
        self.should_stop = False

    def run(self):
        """执行自定义股票分析"""
        try:
            if not self.stock_list:
                self.finished_signal.emit(False, "没有选择股票进行分析")
                return

            total_stocks = len(self.stock_list)
            self.output_signal.emit(f"开始分析 {total_stocks} 只股票...\n")

            for i, (stock_code, stock_name) in enumerate(self.stock_list):
                if self.should_stop:
                    self.output_signal.emit("\n分析已被用户停止\n")
                    break

                self.output_signal.emit(f"\n{'='*50}")
                self.output_signal.emit(f"正在分析第 {i+1}/{total_stocks} 只: {stock_name} ({stock_code})")
                self.output_signal.emit(f"{'='*50}")

                # 获取main.py路径
                main_py = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'main.py')

                # 构建命令 - 使用自定义分析模式
                cmd = [sys.executable, main_py, '--mode', 'custom', '--stocks', stock_code]

                # 执行命令并实时获取输出
                try:
                    self.process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        bufsize=1,
                        universal_newlines=True
                    )

                    # 实时读取输出
                    for line in self.process.stdout:
                        if self.should_stop:
                            break
                        self.output_signal.emit(line.rstrip())

                    # 等待进程完成
                    return_code = self.process.wait()

                    if return_code == 0:
                        self.output_signal.emit(f"\n✅ {stock_name} 分析完成\n")
                    else:
                        self.output_signal.emit(f"\n❌ {stock_name} 分析失败 (返回码: {return_code})\n")

                except Exception as e:
                    self.output_signal.emit(f"\n❌ 分析 {stock_name} 时出错: {str(e)}\n")

                # 更新进度
                progress = int((i + 1) / total_stocks * 100)
                self.progress_signal.emit(progress)

            self.output_signal.emit(f"\n{'='*50}")
            self.output_signal.emit("所有股票分析完成!")
            self.output_signal.emit(f"{'='*50}\n")

            if not self.should_stop:
                self.finished_signal.emit(True, "分析完成")
            else:
                self.finished_signal.emit(False, "分析已停止")

        except Exception as e:
            self.finished_signal.emit(False, f"分析过程中出错: {str(e)}")

    def stop(self):
        """停止分析"""
        self.should_stop = True
        if self.process:
            self.process.terminate()


class CustomStockWidget(QWidget):
    """自定义股票分析部件"""

    def __init__(self):
        super().__init__()
        self.stock_validator = StockValidator()
        self.analysis_thread = None
        self.stock_list = []  # [(代码, 名称), ...]
        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # === 标题 ===
        title_label = QLabel("自定义股票分析")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                padding: 10px;
                background-color: #ecf0f1;
                border-radius: 5px;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title_label)

        # === 股票输入区域 ===
        input_group = QGroupBox("添加股票")
        input_layout = QVBoxLayout()

        # 输入行
        input_row = QHBoxLayout()

        self.stock_input = QLineEdit()
        self.stock_input.setPlaceholderText("输入股票代码(如000001)或股票名称(如平安银行)")
        self.stock_input.setMinimumHeight(35)
        input_row.addWidget(self.stock_input)

        # 校验按钮
        self.validate_btn = QPushButton("校验股票")
        self.validate_btn.setMinimumHeight(35)
        self.validate_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        input_row.addWidget(self.validate_btn)

        input_layout.addLayout(input_row)

        # 校验结果
        self.validation_result = QLabel("")
        self.validation_result.setStyleSheet("""
            QLabel {
                color: #27ae60;
                padding: 5px;
                font-size: 12px;
            }
        """)
        input_layout.addWidget(self.validation_result)

        # 添加到列表按钮
        self.add_stock_btn = QPushButton("添加到分析列表")
        self.add_stock_btn.setEnabled(False)
        self.add_stock_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        input_layout.addWidget(self.add_stock_btn)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # === 股票列表和分析区域 ===
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：股票列表
        list_group = QGroupBox("待分析股票列表")
        list_layout = QVBoxLayout()

        # 列表控件
        self.stock_list_widget = QListWidget()
        self.stock_list_widget.setMinimumHeight(200)
        list_layout.addWidget(self.stock_list_widget)

        # 列表操作按钮
        list_buttons = QHBoxLayout()

        self.remove_btn = QPushButton("移除选中")
        self.remove_btn.setEnabled(False)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        list_buttons.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("清空列表")
        self.clear_btn.setEnabled(False)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        list_buttons.addWidget(self.clear_btn)

        list_layout.addLayout(list_buttons)

        list_group.setLayout(list_layout)
        splitter.addWidget(list_group)

        # 右侧：分析输出
        output_group = QGroupBox("分析输出")
        output_layout = QVBoxLayout()

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        output_layout.addWidget(self.progress_bar)

        # 输出文本框
        self.output_text = QTextEdit()
        self.output_text.setMinimumHeight(300)
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #34495e;
                padding: 5px;
            }
        """)
        output_layout.addWidget(self.output_text)

        output_group.setLayout(output_layout)
        splitter.addWidget(output_group)

        # 设置分割器比例
        splitter.setSizes([300, 500])
        layout.addWidget(splitter)

        # === 控制按钮 ===
        control_group = QGroupBox("分析控制")
        control_layout = QHBoxLayout()

        # 开始分析按钮
        self.start_btn = QPushButton("开始分析")
        self.start_btn.setEnabled(False)
        self.start_btn.setMinimumHeight(45)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        control_layout.addWidget(self.start_btn)

        # 停止分析按钮
        self.stop_btn = QPushButton("停止分析")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(45)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        control_layout.addWidget(self.stop_btn)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        self.setLayout(layout)

    def setup_connections(self):
        """设置信号连接"""
        # 校验相关
        self.validate_btn.clicked.connect(self.validate_stock)
        self.stock_input.returnPressed.connect(self.validate_stock)
        self.stock_validator.validation_result.connect(self.on_validation_result)

        # 列表相关
        self.add_stock_btn.clicked.connect(self.add_stock_to_list)
        self.stock_list_widget.itemSelectionChanged.connect(self.on_list_selection_changed)
        self.remove_btn.clicked.connect(self.remove_selected_stock)
        self.clear_btn.clicked.connect(self.clear_stock_list)

        # 分析相关
        self.start_btn.clicked.connect(self.start_analysis)
        self.stop_btn.clicked.connect(self.stop_analysis)

    def validate_stock(self):
        """校验股票代码"""
        input_text = self.stock_input.text().strip()
        if not input_text:
            self.validation_result.setText("❌ 请输入股票代码或名称")
            self.validation_result.setStyleSheet("color: #e74c3c; padding: 5px; font-size: 12px;")
            return

        self.validation_result.setText("🔄 正在校验...")
        self.validation_result.setStyleSheet("color: #f39c12; padding: 5px; font-size: 12px;")
        self.validate_btn.setEnabled(False)

        # 执行校验
        self.stock_validator.validate_stock_code_async(input_text)

    def on_validation_result(self, is_valid, message, full_code, stock_name):
        """处理校验结果"""
        self.validate_btn.setEnabled(True)

        if is_valid:
            self.validation_result.setText(f"✅ {message}")
            self.validation_result.setStyleSheet("color: #27ae60; padding: 5px; font-size: 12px;")

            # 保存校验结果
            self.current_valid_stock = {
                'code': full_code,
                'name': stock_name
            }
            self.add_stock_btn.setEnabled(True)
        else:
            self.validation_result.setText(f"❌ {message}")
            self.validation_result.setStyleSheet("color: #e74c3c; padding: 5px; font-size: 12px;")
            self.add_stock_btn.setEnabled(False)

    def add_stock_to_list(self):
        """添加股票到分析列表"""
        if hasattr(self, 'current_valid_stock'):
            stock_info = self.current_valid_stock

            # 检查是否已存在
            for i in range(self.stock_list_widget.count()):
                item = self.stock_list_widget.item(i)
                if item.data(Qt.ItemDataRole.UserRole)['code'] == stock_info['code']:
                    QMessageBox.warning(self, "重复添加", f"股票 {stock_info['name']} 已在列表中")
                    return

            # 添加到列表
            item = QListWidgetItem(f"{stock_info['name']} ({stock_info['code']})")
            item.setData(Qt.ItemDataRole.UserRole, stock_info)
            self.stock_list_widget.addItem(item)

            # 添加到内部列表
            self.stock_list.append((stock_info['code'], stock_info['name']))

            # 清空输入
            self.stock_input.clear()
            self.validation_result.clear()
            self.add_stock_btn.setEnabled(False)

            # 更新按钮状态
            self.start_btn.setEnabled(len(self.stock_list) > 0)
            self.clear_btn.setEnabled(True)

    def on_list_selection_changed(self):
        """处理列表选择变化"""
        has_selection = len(self.stock_list_widget.selectedItems()) > 0
        self.remove_btn.setEnabled(has_selection)

    def remove_selected_stock(self):
        """移除选中的股票"""
        selected_items = self.stock_list_widget.selectedItems()
        for item in selected_items:
            row = self.stock_list_widget.row(item)
            stock_info = item.data(Qt.ItemDataRole.UserRole)

            # 从列表中移除
            self.stock_list_widget.takeItem(row)

            # 从内部列表中移除
            self.stock_list = [(code, name) for code, name in self.stock_list
                              if code != stock_info['code']]

        # 更新按钮状态
        self.start_btn.setEnabled(len(self.stock_list) > 0)
        self.clear_btn.setEnabled(len(self.stock_list) > 0)

    def clear_stock_list(self):
        """清空股票列表"""
        self.stock_list_widget.clear()
        self.stock_list.clear()
        self.start_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

    def start_analysis(self):
        """开始分析"""
        if not self.stock_list:
            QMessageBox.warning(self, "警告", "请先添加要分析的股票")
            return

        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # 禁用控制按钮
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.validate_btn.setEnabled(False)
        self.add_stock_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

        # 清空输出
        self.output_text.clear()
        self.output_text.append(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.output_text.append(f"待分析股票数量: {len(self.stock_list)}")
        self.output_text.append("-" * 50)

        # 启动分析线程
        self.analysis_thread = CustomStockAnalysisThread(self.stock_list)
        self.analysis_thread.output_signal.connect(self.append_output)
        self.analysis_thread.finished_signal.connect(self.on_analysis_finished)
        self.analysis_thread.progress_signal.connect(self.progress_bar.setValue)
        self.analysis_thread.start()

    def stop_analysis(self):
        """停止分析"""
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.stop()
            self.output_text.append("\n正在停止分析...")
            self.stop_btn.setEnabled(False)

    def append_output(self, text):
        """添加输出文本"""
        self.output_text.append(text)
        # 滚动到底部
        self.output_text.verticalScrollBar().setValue(
            self.output_text.verticalScrollBar().maximum()
        )

    def on_analysis_finished(self, success, message):
        """分析完成处理"""
        self.progress_bar.setVisible(False)

        # 恢复按钮状态
        self.start_btn.setEnabled(len(self.stock_list) > 0)
        self.stop_btn.setEnabled(False)
        self.validate_btn.setEnabled(True)
        self.remove_btn.setEnabled(True)
        self.clear_btn.setEnabled(len(self.stock_list) > 0)

        # 显示完成消息
        self.output_text.append("-" * 50)
        self.output_text.append(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.output_text.append(f"分析结果: {message}")

        if success:
            self.output_text.append("✅ 分析完成！")
        else:
            self.output_text.append("❌ 分析失败！")