# -*- coding: utf-8 -*-
"""
分析模块 - 包含选股、持股、全分析三个按钮
"""
import os
import sys
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QGroupBox, QLabel, QSpinBox, QMessageBox, QLineEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QTime
from PyQt6.QtGui import QFont

from src.qt.stock_validator import StockValidator


class AnalysisThread(QThread):
    """后台分析线程，避免阻塞UI"""
    output_signal = pyqtSignal(str)  # 输出信号
    finished_signal = pyqtSignal(bool, str)  # 完成信号(成功与否, 消息)

    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.process = None

    def run(self):
        """执行分析"""
        try:
            # 获取main.py路径
            main_py = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'main.py')

            # 构建命令
            cmd = [sys.executable, main_py, '--mode', self.mode]

            # 执行命令并实时获取输出
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
                self.output_signal.emit(line.rstrip())

            # 等待进程完成
            return_code = self.process.wait()

            if return_code == 0:
                self.finished_signal.emit(True, f"{self.mode}模式分析完成")
            else:
                self.finished_signal.emit(False, f"{self.mode}模式分析失败，返回码: {return_code}")

        except Exception as e:
            self.finished_signal.emit(False, f"执行出错: {str(e)}")

    def stop(self):
        """停止分析"""
        if self.process:
            self.process.terminate()


class AnalysisWidget(QWidget):
    """分析模块"""

    def __init__(self):
        super().__init__()
        self.analysis_thread = None
        self.scheduled_time = None  # 预定的执行时间
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_scheduled_time)
        self.stock_validator = StockValidator()  # 股票验证器
        self.current_valid_stock = None  # 当前校验通过的股票信息
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # 标题
        title_label = QLabel("股票分析")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # 按钮组
        button_group = QGroupBox("分析模式")
        button_layout = QHBoxLayout()

        # 选股按钮
        self.select_btn = QPushButton("选股分析")
        self.select_btn.setMinimumHeight(50)
        self.select_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.select_btn.clicked.connect(lambda: self.start_analysis('select'))
        button_layout.addWidget(self.select_btn)

        # 持股按钮
        self.hold_btn = QPushButton("持股分析")
        self.hold_btn.setMinimumHeight(50)
        self.hold_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0a6bc4;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.hold_btn.clicked.connect(lambda: self.start_analysis('hold'))
        button_layout.addWidget(self.hold_btn)

        # 全分析按钮
        self.both_btn = QPushButton("全分析")
        self.both_btn.setMinimumHeight(50)
        self.both_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e68900;
            }
            QPushButton:pressed {
                background-color: #cc7a00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.both_btn.clicked.connect(lambda: self.start_analysis('both'))
        button_layout.addWidget(self.both_btn)

        button_group.setLayout(button_layout)
        layout.addWidget(button_group)

        # 停止按钮
        self.stop_btn = QPushButton("停止分析")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_analysis)
        layout.addWidget(self.stop_btn)

        # 定时分析模块
        scheduled_group = QGroupBox("定时分析")
        scheduled_layout = QVBoxLayout()

        # 时间设置行
        time_layout = QHBoxLayout()

        time_label = QLabel("执行时间:")
        time_layout.addWidget(time_label)

        # 时
        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setValue(8)
        self.hour_spin.setSuffix(" 时")
        self.hour_spin.setMinimumWidth(80)
        time_layout.addWidget(self.hour_spin)

        # 分
        self.minute_spin = QSpinBox()
        self.minute_spin.setRange(0, 59)
        self.minute_spin.setValue(30)
        self.minute_spin.setSuffix(" 分")
        self.minute_spin.setMinimumWidth(80)
        time_layout.addWidget(self.minute_spin)

        # 秒
        self.second_spin = QSpinBox()
        self.second_spin.setRange(0, 59)
        self.second_spin.setValue(0)
        self.second_spin.setSuffix(" 秒")
        self.second_spin.setMinimumWidth(80)
        time_layout.addWidget(self.second_spin)

        time_layout.addStretch()

        # 启动/停止定时按钮
        self.schedule_btn = QPushButton("启动定时")
        self.schedule_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border-radius: 3px;
                padding: 5px 15px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:checked {
                background-color: #f44336;
            }
        """)
        self.schedule_btn.setCheckable(True)
        self.schedule_btn.clicked.connect(self.toggle_schedule)
        time_layout.addWidget(self.schedule_btn)

        scheduled_layout.addLayout(time_layout)

        # 状态显示
        self.schedule_status_label = QLabel("定时未启动")
        self.schedule_status_label.setStyleSheet("color: #666666; padding: 5px; font-size: 11px;")
        scheduled_layout.addWidget(self.schedule_status_label)

        scheduled_group.setLayout(scheduled_layout)
        layout.addWidget(scheduled_group)

        # 自定义股票分析模块
        custom_group = QGroupBox("自定义股票分析")
        custom_layout = QVBoxLayout()

        # 简化版自定义股票输入
        custom_input_layout = QHBoxLayout()

        self.custom_stock_input = QLineEdit()
        self.custom_stock_input.setPlaceholderText("输入股票代码(如000001)或名称(如平安银行)")
        custom_input_layout.addWidget(self.custom_stock_input)

        self.custom_analyze_btn = QPushButton("分析单股")
        self.custom_analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                padding: 5px 15px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.custom_analyze_btn.clicked.connect(self.start_custom_analysis)
        custom_input_layout.addWidget(self.custom_analyze_btn)

        custom_layout.addLayout(custom_input_layout)

        # 说明文字
        custom_info = QLabel("💡 提示: 输入6位股票代码(如000001)或股票名称(如平安银行)进行快速分析")
        custom_info.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 5px;")
        custom_layout.addWidget(custom_info)

        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)

        # 输出显示区域
        output_group = QGroupBox("分析输出")
        output_layout = QVBoxLayout()

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, Monaco, monospace;
                font-size: 10pt;
                border: 1px solid #3c3c3c;
            }
        """)
        output_layout.addWidget(self.output_text)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666666; padding: 5px;")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def start_analysis(self, mode):
        """启动分析"""
        # 禁用按钮
        self.select_btn.setEnabled(False)
        self.hold_btn.setEnabled(False)
        self.both_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        # 清空输出
        self.output_text.clear()

        # 更新状态
        mode_name = {'select': '选股', 'hold': '持股', 'both': '全'}[mode]
        self.status_label.setText(f"正在执行{mode_name}分析...")
        self.status_label.setStyleSheet("color: #FF9800; padding: 5px;")

        # 创建并启动线程
        self.analysis_thread = AnalysisThread(mode)
        self.analysis_thread.output_signal.connect(self.append_output)
        self.analysis_thread.finished_signal.connect(self.analysis_finished)
        self.analysis_thread.start()

        # 添加开始时间
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.append_output(f"=" * 60)
        self.append_output(f"开始{mode_name}分析 - {start_time}")
        self.append_output(f"=" * 60)

    def stop_analysis(self):
        """停止分析"""
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.stop()
            self.append_output("\n用户中断分析")
            self.status_label.setText("已停止")
            self.status_label.setStyleSheet("color: #f44336; padding: 5px;")

    def append_output(self, text):
        """添加输出"""
        self.output_text.append(text)
        # 自动滚动到底部
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def analysis_finished(self, success, message):
        """分析完成"""
        # 恢复按钮
        self.select_btn.setEnabled(True)
        self.hold_btn.setEnabled(True)
        self.both_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        # 更新状态
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.append_output(f"\n{message} - {end_time}")

        if success:
            self.status_label.setText(f"完成: {message}")
            self.status_label.setStyleSheet("color: #4CAF50; padding: 5px;")
        else:
            self.status_label.setText(f"失败: {message}")
            self.status_label.setStyleSheet("color: #f44336; padding: 5px;")

    def toggle_schedule(self):
        """启动/停止定时任务"""
        if self.schedule_btn.isChecked():
            # 启动定时
            hour = self.hour_spin.value()
            minute = self.minute_spin.value()
            second = self.second_spin.value()

            self.scheduled_time = QTime(hour, minute, second)

            # 禁用时间输入
            self.hour_spin.setEnabled(False)
            self.minute_spin.setEnabled(False)
            self.second_spin.setEnabled(False)

            # 启动定时器，每秒检查一次
            self.timer.start(1000)

            # 更新状态
            self.schedule_btn.setText("停止定时")
            time_str = self.scheduled_time.toString("HH:mm:ss")
            self.schedule_status_label.setText(f"⏰ 定时已启动，将在 {time_str} 执行全分析")
            self.schedule_status_label.setStyleSheet("color: #9C27B0; padding: 5px; font-size: 11px;")

            self.append_output(f"\n[定时任务] 设置在 {time_str} 执行全分析")
        else:
            # 停止定时
            self.timer.stop()
            self.scheduled_time = None

            # 启用时间输入
            self.hour_spin.setEnabled(True)
            self.minute_spin.setEnabled(True)
            self.second_spin.setEnabled(True)

            # 更新状态
            self.schedule_btn.setText("启动定时")
            self.schedule_status_label.setText("定时未启动")
            self.schedule_status_label.setStyleSheet("color: #666666; padding: 5px; font-size: 11px;")

            self.append_output("\n[定时任务] 已取消定时")

    def check_scheduled_time(self):
        """检查是否到达定时时间"""
        if self.scheduled_time is None:
            return

        current_time = QTime.currentTime()

        # 检查时分秒是否匹配（精确到秒）
        if (current_time.hour() == self.scheduled_time.hour() and
            current_time.minute() == self.scheduled_time.minute() and
            current_time.second() == self.scheduled_time.second()):

            # 到达定时时间，执行分析
            self.execute_scheduled_analysis()

    def execute_scheduled_analysis(self):
        """执行定时分析"""
        # 停止定时器，避免重复执行
        self.timer.stop()

        # 重置按钮状态
        self.schedule_btn.setChecked(False)
        self.schedule_btn.setText("启动定时")

        # 启用时间输入
        self.hour_spin.setEnabled(True)
        self.minute_spin.setEnabled(True)
        self.second_spin.setEnabled(True)

        # 更新状态
        time_str = self.scheduled_time.toString("HH:mm:ss")
        self.schedule_status_label.setText(f"✅ 定时任务已执行 ({time_str})")
        self.schedule_status_label.setStyleSheet("color: #4CAF50; padding: 5px; font-size: 11px;")

        # 清空定时时间
        self.scheduled_time = None

        # 执行 both 模式分析
        self.append_output(f"\n[定时任务] {time_str} 开始执行全分析...")
        self.start_analysis('both')

    def start_custom_analysis(self):
        """开始自定义股票分析"""
        input_text = self.custom_stock_input.text().strip()

        if not input_text:
            QMessageBox.warning(self, "输入错误", "请输入股票代码或名称")
            return

        # 验证股票代码
        is_valid, message, full_code, stock_name = self.stock_validator.validate_stock_code(input_text)

        if not is_valid:
            QMessageBox.warning(self, "验证失败", f"股票验证失败: {message}")
            return

        # 询问用户确认
        reply = QMessageBox.question(
            self,
            "确认分析",
            f"确定要分析 {stock_name} ({full_code}) 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # 开始分析
        self.append_output(f"\n{'='*60}")
        self.append_output(f"[自定义分析] 开始分析: {stock_name} ({full_code})")
        self.append_output(f"[自定义分析] 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.append_output(f"{'='*60}")

        # 获取main.py路径
        main_py = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'main.py')

        # 构建命令
        cmd = [sys.executable, main_py, '--mode', 'custom', '--stocks', full_code]

        # 启动分析线程
        custom_thread = CustomAnalysisThread(cmd)
        custom_thread.output_signal.connect(self.append_output)
        custom_thread.finished_signal.connect(self.on_custom_analysis_finished)
        custom_thread.start()

        # 禁用输入
        self.custom_stock_input.setEnabled(False)
        self.custom_analyze_btn.setEnabled(False)

    def on_custom_analysis_finished(self, success, message):
        """自定义分析完成处理"""
        self.append_output(f"\n{'='*60}")
        self.append_output(f"[自定义分析] 分析结果: {message}")
        self.append_output(f"[自定义分析] 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.append_output(f"{'='*60}")

        # 重新启用输入
        self.custom_stock_input.setEnabled(True)
        self.custom_analyze_btn.setEnabled(True)

        # 清空输入框
        self.custom_stock_input.clear()

        # 显示完成消息
        if success:
            QMessageBox.information(self, "分析完成", f"股票分析完成！\n{message}")
        else:
            QMessageBox.warning(self, "分析失败", f"股票分析失败！\n{message}")


class CustomAnalysisThread(QThread):
    """自定义分析线程"""

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd
        self.process = None

    def run(self):
        """执行分析"""
        try:
            # 执行命令并实时获取输出
            self.process = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                universal_newlines=True
            )

            # 实时读取输出
            for line in self.process.stdout:
                self.output_signal.emit(line.rstrip())

            # 等待进程完成
            return_code = self.process.wait()

            if return_code == 0:
                self.finished_signal.emit(True, "分析成功完成")
            else:
                self.finished_signal.emit(False, f"分析失败，返回码: {return_code}")

        except Exception as e:
            self.finished_signal.emit(False, f"执行出错: {str(e)}")

    # 定义信号
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

