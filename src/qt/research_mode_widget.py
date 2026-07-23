# -*- coding: utf-8 -*-
"""
研究模式说明页
"""
import os
import sys

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QGroupBox, QTextEdit, QPushButton, QMessageBox,
                             QListWidget, QLineEdit)
from PyQt6.QtCore import Qt

from src.qt.base_thread import SubprocessThread
from src.utils.factor_registry import FactorRegistryManager


class ResearchFactorThread(SubprocessThread):
    """后台研究线程，通过 main.py 保持命令行和GUI行为一致"""

    def build_command(self):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        main_py = os.path.join(project_root, 'main.py')
        return [sys.executable, main_py, '--mode', 'research', '--research-generate-factors']

    def _on_completion(self, return_code):
        if return_code == 0:
            self.finished_signal.emit(True, "研究模式执行完成")
        else:
            self.finished_signal.emit(False, f"研究模式执行失败，返回码: {return_code}")


class ResearchModeWidget(QWidget):
    """运行因子研究并辅助维护生产因子注册表"""

    def __init__(self):
        super().__init__()
        self.research_thread = None
        self.registry_manager = FactorRegistryManager()
        self.init_ui()
        self.load_registry()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title_label = QLabel("因子研究模式")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: bold;
                color: #2c3e50;
                padding-bottom: 8px;
            }
        """)
        layout.addWidget(title_label)

        summary = QLabel("生成候选因子后，可在下方配置区将已验证因子加入生产稳定因子库。")
        summary.setWordWrap(True)
        summary.setStyleSheet("""
            QLabel {
                color: #34495e;
                font-size: 14px;
                line-height: 1.5;
                padding: 8px 0;
            }
        """)
        layout.addWidget(summary)

        action_group = QGroupBox("执行研究模式")
        action_layout = QVBoxLayout()
        action_layout.setSpacing(10)

        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("启动研究模式")
        self.start_btn.setMinimumHeight(42)
        self.start_btn.clicked.connect(self.start_research)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: white;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7d3c98;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setMinimumHeight(42)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_research)
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
                background-color: #cccccc;
                color: #666666;
            }
        """)
        button_layout.addWidget(self.stop_btn)
        action_layout.addLayout(button_layout)

        self.status_label = QLabel("研究模式未启动")
        self.status_label.setStyleSheet("color: #666666; padding: 4px;")
        action_layout.addWidget(self.status_label)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(180)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1f2933;
                color: #e5e7eb;
                border: 1px solid #34495e;
                border-radius: 4px;
                font-family: Menlo, Consolas, monospace;
                font-size: 12px;
                padding: 8px;
            }
        """)
        action_layout.addWidget(self.output_text)
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        registry_group = QGroupBox("生产因子配置")
        registry_layout = QVBoxLayout()
        registry_layout.setSpacing(10)

        add_layout = QHBoxLayout()
        self.factor_input = QLineEdit()
        self.factor_input.setPlaceholderText("输入候选因子名称")
        add_layout.addWidget(self.factor_input, 1)

        add_candidate_btn = QPushButton("添加候选")
        add_candidate_btn.clicked.connect(self.add_candidate_factor)
        add_layout.addWidget(add_candidate_btn)
        registry_layout.addLayout(add_layout)

        lists_layout = QHBoxLayout()
        self.candidate_list = self.create_factor_list("候选因子")
        self.active_list = self.create_factor_list("生产因子")
        self.disabled_list = self.create_factor_list("禁用因子")
        lists_layout.addWidget(self.create_factor_column("候选因子", self.candidate_list))
        lists_layout.addWidget(self.create_factor_column("生产因子", self.active_list))
        lists_layout.addWidget(self.create_factor_column("禁用因子", self.disabled_list))
        registry_layout.addLayout(lists_layout)

        registry_buttons = QHBoxLayout()
        promote_btn = QPushButton("加入生产")
        promote_btn.clicked.connect(lambda: self.move_selected_factor("active_factors"))
        registry_buttons.addWidget(promote_btn)

        candidate_btn = QPushButton("移到候选")
        candidate_btn.clicked.connect(lambda: self.move_selected_factor("candidate_factors"))
        registry_buttons.addWidget(candidate_btn)

        disable_btn = QPushButton("禁用")
        disable_btn.clicked.connect(lambda: self.move_selected_factor("disabled_factors"))
        registry_buttons.addWidget(disable_btn)

        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self.save_registry_from_ui)
        registry_buttons.addWidget(save_btn)

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.load_registry)
        registry_buttons.addWidget(refresh_btn)
        registry_layout.addLayout(registry_buttons)

        self.registry_status_label = QLabel("配置文件: config/factor_registry.json")
        self.registry_status_label.setStyleSheet("color: #666666; padding: 4px;")
        registry_layout.addWidget(self.registry_status_label)

        registry_group.setLayout(registry_layout)
        layout.addWidget(registry_group)

        layout.addStretch()
        self.setLayout(layout)

    def start_research(self):
        """启动研究模式，复用 main.py 独立入口"""
        if self.research_thread and self.research_thread.isRunning():
            QMessageBox.warning(self, "提示", "研究模式正在运行，请稍后再试")
            return

        self.output_text.clear()
        self.append_output("[因子研究] 启动 main.py --mode research --research-generate-factors")
        self.append_output("[因子研究] 新因子仅用于研究验证，不建议直接用于生产日批")

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("研究模式运行中...")
        self.status_label.setStyleSheet("color: #8e44ad; padding: 4px;")

        self.research_thread = ResearchFactorThread()
        self.research_thread.output_signal.connect(self.append_output)
        self.research_thread.finished_signal.connect(self.research_finished)
        self.research_thread.start()

    def stop_research(self):
        """停止研究模式子进程"""
        if self.research_thread and self.research_thread.isRunning():
            self.research_thread.stop()
            self.append_output("[因子研究] 已请求停止")
            self.status_label.setText("正在停止研究模式...")

    def research_finished(self, success, message):
        """研究模式执行结束"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.append_output(f"[因子研究] {message}")

        if success:
            self.status_label.setText("研究模式执行完成")
            self.status_label.setStyleSheet("color: #27ae60; padding: 4px;")
        else:
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: #c0392b; padding: 4px;")

    def append_output(self, text):
        self.output_text.append(text)
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def create_factor_list(self, title):
        factor_list = QListWidget()
        factor_list.setObjectName(title)
        factor_list.setMinimumHeight(150)
        factor_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #dfe4ea;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        factor_list.setToolTip(title)
        return factor_list

    def create_factor_column(self, title, factor_list):
        column = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; color: #2c3e50; padding: 4px;")
        layout.addWidget(title_label)
        layout.addWidget(factor_list)
        column.setLayout(layout)
        return column

    def load_registry(self):
        try:
            registry = self.registry_manager.load()
            self.populate_factor_list(self.candidate_list, registry["candidate_factors"])
            self.populate_factor_list(self.active_list, registry["active_factors"])
            self.populate_factor_list(self.disabled_list, registry["disabled_factors"])
            self.registry_status_label.setText("配置已加载: config/factor_registry.json")
        except Exception as e:
            self.registry_status_label.setText(f"配置加载失败: {e}")

    def populate_factor_list(self, target_list, factors):
        target_list.clear()
        target_list.addItems(factors)

    def add_candidate_factor(self):
        factor_name = self.factor_input.text().strip()
        if not factor_name:
            QMessageBox.warning(self, "提示", "请输入因子名称")
            return
        try:
            self.registry_manager.move_factor(factor_name, "candidate_factors")
            self.factor_input.clear()
            self.load_registry()
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def move_selected_factor(self, target_key):
        factor_name = self.get_selected_factor_name()
        if not factor_name:
            QMessageBox.warning(self, "提示", "请先选择一个因子")
            return
        try:
            self.registry_manager.move_factor(factor_name, target_key)
            self.load_registry()
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def get_selected_factor_name(self):
        for factor_list in (self.candidate_list, self.active_list, self.disabled_list):
            selected = factor_list.selectedItems()
            if selected:
                return selected[0].text()
        return ""

    def save_registry_from_ui(self):
        registry = {
            "candidate_factors": self.get_list_items(self.candidate_list),
            "active_factors": self.get_list_items(self.active_list),
            "disabled_factors": self.get_list_items(self.disabled_list),
            "version": self.registry_manager.load().get("version")
        }
        try:
            self.registry_manager.save(registry)
            self.load_registry()
            self.registry_status_label.setText("配置已保存: config/factor_registry.json")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def get_list_items(self, factor_list):
        return [factor_list.item(i).text() for i in range(factor_list.count())]
