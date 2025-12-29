# -*- coding: utf-8 -*-
"""
回测模块 - 历史回测功能界面
"""
import os
import sys
import subprocess
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QTextEdit, QGroupBox, QLabel,
                             QSpinBox, QMessageBox, QDateEdit, QRadioButton,
                             QButtonGroup, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont


class BacktestThread(QThread):
    """后台回测线程，避免阻塞UI"""
    output_signal = pyqtSignal(str)  # 输出信号
    finished_signal = pyqtSignal(bool, str, str)  # 完成信号(成功与否, 消息, 输出目录)

    def __init__(self, params):
        super().__init__()
        self.params = params
        self.process = None
        self.output_dir = None

    def run(self):
        """执行回测"""
        try:
            # 获取main.py路径
            main_py = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'main.py')

            # 构建命令
            cmd = [sys.executable, main_py, '--mode', 'backtest']

            # 添加参数
            if self.params['mode'] == 'months':
                cmd.extend(['--months', str(self.params['months'])])
            else:  # date_range
                cmd.extend(['--start-date', self.params['start_date']])
                cmd.extend(['--end-date', self.params['end_date']])

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
                line_stripped = line.rstrip()
                self.output_signal.emit(line_stripped)

                # 尝试捕获输出目录
                if "输出目录:" in line_stripped:
                    try:
                        self.output_dir = line_stripped.split("输出目录:")[-1].strip()
                    except:
                        pass

            # 等待进程完成
            return_code = self.process.wait()

            if return_code == 0:
                self.finished_signal.emit(True, "回测完成", self.output_dir or "")
            else:
                self.finished_signal.emit(False, f"回测失败，返回码: {return_code}", "")

        except Exception as e:
            self.finished_signal.emit(False, f"执行出错: {str(e)}", "")

    def stop(self):
        """停止回测"""
        if self.process:
            self.process.terminate()


class BacktestWidget(QWidget):
    """回测模块"""

    def __init__(self):
        super().__init__()
        self.backtest_thread = None
        self.latest_output_dir = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # 标题
        title_label = QLabel("历史回测")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # 参数设置组
        params_group = QGroupBox("回测参数")
        params_layout = QVBoxLayout()

        # 模式选择
        mode_layout = QHBoxLayout()
        mode_label = QLabel("回测方式:")
        mode_layout.addWidget(mode_label)

        self.mode_group = QButtonGroup()
        self.months_radio = QRadioButton("回测最近N个月")
        self.months_radio.setChecked(True)
        self.months_radio.toggled.connect(self.on_mode_changed)
        self.mode_group.addButton(self.months_radio)
        mode_layout.addWidget(self.months_radio)

        self.date_range_radio = QRadioButton("指定日期范围")
        self.date_range_radio.toggled.connect(self.on_mode_changed)
        self.mode_group.addButton(self.date_range_radio)
        mode_layout.addWidget(self.date_range_radio)

        mode_layout.addStretch()
        params_layout.addLayout(mode_layout)

        # 月数设置（默认显示）
        self.months_widget = QWidget()
        months_layout = QHBoxLayout()
        months_layout.setContentsMargins(0, 0, 0, 0)
        months_label = QLabel("回测月数:")
        months_layout.addWidget(months_label)

        self.months_spin = QSpinBox()
        self.months_spin.setMinimum(1)
        self.months_spin.setMaximum(36)
        self.months_spin.setValue(3)
        self.months_spin.setSuffix(" 个月")
        months_layout.addWidget(self.months_spin)

        # 快捷选择
        quick_1m = QPushButton("1个月")
        quick_1m.clicked.connect(lambda: self.months_spin.setValue(1))
        months_layout.addWidget(quick_1m)

        quick_3m = QPushButton("3个月")
        quick_3m.clicked.connect(lambda: self.months_spin.setValue(3))
        months_layout.addWidget(quick_3m)

        quick_6m = QPushButton("6个月")
        quick_6m.clicked.connect(lambda: self.months_spin.setValue(6))
        months_layout.addWidget(quick_6m)

        quick_1y = QPushButton("1年")
        quick_1y.clicked.connect(lambda: self.months_spin.setValue(12))
        months_layout.addWidget(quick_1y)

        months_layout.addStretch()
        self.months_widget.setLayout(months_layout)
        params_layout.addWidget(self.months_widget)

        # 日期范围设置（默认隐藏）
        self.date_range_widget = QWidget()
        date_range_layout = QGridLayout()
        date_range_layout.setContentsMargins(0, 0, 0, 0)

        start_label = QLabel("开始日期:")
        date_range_layout.addWidget(start_label, 0, 0)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-3))
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        date_range_layout.addWidget(self.start_date_edit, 0, 1)

        end_label = QLabel("结束日期:")
        date_range_layout.addWidget(end_label, 0, 2)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        date_range_layout.addWidget(self.end_date_edit, 0, 3)

        # 预设按钮
        preset_label = QLabel("快捷选择:")
        date_range_layout.addWidget(preset_label, 1, 0)

        preset_layout = QHBoxLayout()

        preset_q1 = QPushButton("Q1 (1-3月)")
        preset_q1.clicked.connect(lambda: self.set_date_range("2024-01-01", "2024-03-31"))
        preset_layout.addWidget(preset_q1)

        preset_q2 = QPushButton("Q2 (4-6月)")
        preset_q2.clicked.connect(lambda: self.set_date_range("2024-04-01", "2024-06-30"))
        preset_layout.addWidget(preset_q2)

        preset_q3 = QPushButton("Q3 (7-9月)")
        preset_q3.clicked.connect(lambda: self.set_date_range("2024-07-01", "2024-09-30"))
        preset_layout.addWidget(preset_q3)

        preset_q4 = QPushButton("Q4 (10-12月)")
        preset_q4.clicked.connect(lambda: self.set_date_range("2024-10-01", "2024-12-31"))
        preset_layout.addWidget(preset_q4)

        preset_layout.addStretch()
        date_range_layout.addLayout(preset_layout, 1, 1, 1, 3)

        self.date_range_widget.setLayout(date_range_layout)
        self.date_range_widget.setVisible(False)
        params_layout.addWidget(self.date_range_widget)

        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # 控制按钮
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("🚀 开始回测")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.start_btn.clicked.connect(self.start_backtest)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️ 停止回测")
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c1170a;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_backtest)
        button_layout.addWidget(self.stop_btn)

        self.view_result_btn = QPushButton("📊 查看结果")
        self.view_result_btn.setMinimumHeight(50)
        self.view_result_btn.setEnabled(False)
        self.view_result_btn.setStyleSheet("""
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
        self.view_result_btn.clicked.connect(self.view_results)
        button_layout.addWidget(self.view_result_btn)

        layout.addLayout(button_layout)

        # 输出日志
        log_group = QGroupBox("回测日志")
        log_layout = QVBoxLayout()

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #3e3e3e;
                border-radius: 3px;
            }
        """)
        log_layout.addWidget(self.log_output)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        self.setLayout(layout)

    def on_mode_changed(self):
        """模式切换"""
        if self.months_radio.isChecked():
            self.months_widget.setVisible(True)
            self.date_range_widget.setVisible(False)
        else:
            self.months_widget.setVisible(False)
            self.date_range_widget.setVisible(True)

    def set_date_range(self, start_date, end_date):
        """设置日期范围"""
        self.start_date_edit.setDate(QDate.fromString(start_date, "yyyy-MM-dd"))
        self.end_date_edit.setDate(QDate.fromString(end_date, "yyyy-MM-dd"))

    def start_backtest(self):
        """开始回测"""
        # 禁用开始按钮，启用停止按钮
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.view_result_btn.setEnabled(False)

        # 清空日志
        self.log_output.clear()
        self.log_output.append("正在启动回测...")

        # 收集参数
        params = {}
        if self.months_radio.isChecked():
            params['mode'] = 'months'
            params['months'] = self.months_spin.value()
            self.log_output.append(f"回测方式: 最近 {params['months']} 个月")
        else:
            params['mode'] = 'date_range'
            params['start_date'] = self.start_date_edit.date().toString("yyyy-MM-dd")
            params['end_date'] = self.end_date_edit.date().toString("yyyy-MM-dd")
            self.log_output.append(f"回测方式: {params['start_date']} 至 {params['end_date']}")

        # 创建并启动回测线程
        self.backtest_thread = BacktestThread(params)
        self.backtest_thread.output_signal.connect(self.append_log)
        self.backtest_thread.finished_signal.connect(self.on_backtest_finished)
        self.backtest_thread.start()

    def stop_backtest(self):
        """停止回测"""
        if self.backtest_thread and self.backtest_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "确认停止",
                "确定要停止回测吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.log_output.append("\n正在停止回测...")
                self.backtest_thread.stop()
                self.backtest_thread.wait()
                self.log_output.append("回测已停止")

                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)

    def append_log(self, text):
        """追加日志"""
        self.log_output.append(text)
        # 自动滚动到底部
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def on_backtest_finished(self, success, message, output_dir):
        """回测完成回调"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if success:
            self.log_output.append(f"\n✅ {message}")
            if output_dir:
                self.latest_output_dir = output_dir
                self.log_output.append(f"结果保存在: {output_dir}")
                self.view_result_btn.setEnabled(True)

            QMessageBox.information(self, "回测完成", message)
        else:
            self.log_output.append(f"\n❌ {message}")
            QMessageBox.warning(self, "回测失败", message)

    def view_results(self):
        """查看回测结果"""
        if not self.latest_output_dir:
            QMessageBox.warning(self, "提示", "没有可查看的回测结果")
            return

        # 使用系统文件管理器打开输出目录
        try:
            if sys.platform == 'win32':
                os.startfile(self.latest_output_dir)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', self.latest_output_dir])
            else:  # Linux
                subprocess.run(['xdg-open', self.latest_output_dir])
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开目录: {str(e)}")
