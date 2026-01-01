# -*- coding: utf-8 -*-
"""
自媒体内容生成模块
"""
import os
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QGroupBox, QLabel,
                             QLineEdit, QFileDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from src.content.xiaohongshu_generator import XiaohongshuContentGenerator
from src.ai_models.factory import AIModelFactory
from config.config_manager import get_config

logger = logging.getLogger(__name__)


class ContentGenerationThread(QThread):
    """内容生成线程"""
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, output_dir, ai_client=None):
        super().__init__()
        self.output_dir = output_dir
        self.ai_client = ai_client

    def run(self):
        """执行内容生成"""
        try:
            self.output_signal.emit("开始生成小红书文案...")

            # 初始化生成器
            generator = XiaohongshuContentGenerator(ai_client=self.ai_client)

            # 生成文案
            content = generator.generate_content(
                output_dir=self.output_dir,
                holdings_csv="holdings_analysis.csv",
                analysis_csv="analysis_summary.csv"
            )

            if content:
                self.output_signal.emit("✅ 文案生成成功")
                self.output_signal.emit(f"文件保存位置:")
                self.output_signal.emit(f"  - {os.path.join(self.output_dir, 'xiaohongshu_content.md')}")
                self.output_signal.emit(f"  - {os.path.join(self.output_dir, 'xiaohongshu_content.txt')}")
                self.finished_signal.emit(True, "文案生成成功")
            else:
                self.output_signal.emit("⚠️ 文案生成失败")
                self.finished_signal.emit(False, "文案生成失败")

        except Exception as e:
            error_msg = f"生成失败: {str(e)}"
            logger.error(error_msg)
            self.output_signal.emit(f"❌ {error_msg}")
            self.finished_signal.emit(False, error_msg)


class MediaWidget(QWidget):
    """自媒体内容生成模块"""

    def __init__(self):
        super().__init__()
        self.generation_thread = None
        self.ai_client = None
        self.init_ui()
        self.init_ai_client()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # 标题
        title_label = QLabel("自媒体内容生成")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # 配置组
        config_group = QGroupBox("配置")
        config_layout = QVBoxLayout()

        # 输出目录选择
        dir_layout = QHBoxLayout()
        dir_label = QLabel("输出目录:")
        dir_label.setFixedWidth(80)
        dir_layout.addWidget(dir_label)

        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("选择包含分析结果的输出目录...")
        self.dir_input.setReadOnly(True)
        dir_layout.addWidget(self.dir_input)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.browse_btn)

        config_layout.addLayout(dir_layout)

        # 说明文字
        info_label = QLabel(
            "💡 提示：选择包含 holdings_analysis.csv 和 analysis_summary.csv 的目录\n"
            "通常是 outputs/YYYYMMDD_HHMMSS/ 格式的目录"
        )
        info_label.setStyleSheet("color: #666666; padding: 5px; font-size: 11px;")
        config_layout.addWidget(info_label)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 生成按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.generate_btn = QPushButton("生成小红书文案")
        self.generate_btn.setMinimumHeight(50)
        self.generate_btn.setMinimumWidth(200)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF2442;
                color: white;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E01E3B;
            }
            QPushButton:pressed {
                background-color: #C51A34;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.generate_btn.clicked.connect(self.start_generation)
        self.generate_btn.setEnabled(False)
        button_layout.addWidget(self.generate_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # 输出显示区域
        output_group = QGroupBox("生成日志")
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

    def init_ai_client(self):
        """初始化AI客户端 - 必须使用 Claude Code SDK"""
        try:
            # 加载配置
            config = get_config()
            ai_models_config = config.get('system_settings', {}).get('ai_models', {})
            models = ai_models_config.get('models', {})

            # 检查 Claude SDK 配置
            claude_config = models.get('claude_sonnet')
            if not claude_config:
                error_msg = "❌ 错误: 未找到 Claude SDK 配置！请在 config/unified_config.json 中配置 claude_sonnet 模型"
                self.append_output(error_msg)
                logger.error(error_msg)
                raise RuntimeError("Claude SDK 配置缺失")

            # 必须使用 Claude Code SDK（支持新闻搜索）
            self.append_output(f"🔍 初始化 Claude Agent SDK（支持新闻搜索）...")
            self.ai_client = AIModelFactory.create_model('claude_sonnet', models)

            if not self.ai_client or not self.ai_client.is_available():
                error_msg = "❌ 错误: Claude Agent SDK 不可用！请确保已安装: pip install claude-agent-sdk"
                self.append_output(error_msg)
                logger.error(error_msg)
                raise RuntimeError("Claude Agent SDK 初始化失败")

            self.append_output(f"✅ Claude Agent SDK 初始化成功")
            self.append_output(f"💡 Claude 将自动搜索最新新闻来生成高质量文案")

        except Exception as e:
            error_msg = f"❌ Claude Agent SDK 初始化失败: {str(e)}"
            self.append_output(error_msg)
            logger.error(error_msg)
            self.ai_client = None
            # 禁用生成按钮
            self.generate_btn.setEnabled(False)
            self.generate_btn.setText("Claude SDK 不可用")

    def browse_directory(self):
        """浏览选择目录"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            "outputs",
            QFileDialog.Option.ShowDirsOnly
        )

        if directory:
            self.dir_input.setText(directory)
            self.generate_btn.setEnabled(True)
            self.append_output(f"📁 已选择目录: {directory}")

            # 检查目录中是否存在必需文件
            holdings_csv = os.path.join(directory, "holdings_analysis.csv")
            analysis_csv = os.path.join(directory, "analysis_summary.csv")

            if os.path.exists(holdings_csv):
                self.append_output(f"✅ 找到 holdings_analysis.csv")
            else:
                self.append_output(f"⚠️ 未找到 holdings_analysis.csv")

            if os.path.exists(analysis_csv):
                self.append_output(f"✅ 找到 analysis_summary.csv")
            else:
                self.append_output(f"⚠️ 未找到 analysis_summary.csv")

    def start_generation(self):
        """开始生成文案"""
        output_dir = self.dir_input.text()

        if not output_dir:
            self.append_output("❌ 请先选择输出目录")
            return

        if not os.path.isdir(output_dir):
            self.append_output("❌ 所选目录不存在")
            return

        # 必须有可用的 Claude SDK
        if not self.ai_client:
            self.append_output("❌ Claude Agent SDK 不可用，无法生成文案")
            self.append_output("💡 请确保已安装: pip install claude-agent-sdk")
            return

        # 禁用按钮
        self.generate_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)

        # 更新状态
        self.status_label.setText("正在生成文案...")
        self.status_label.setStyleSheet("color: #FF2442; padding: 5px;")

        # 清空部分输出（保留初始化日志）
        self.append_output("\n" + "=" * 60)
        self.append_output("开始生成小红书文案（使用 Claude Agent SDK）")
        self.append_output("=" * 60)

        # 创建并启动线程
        self.generation_thread = ContentGenerationThread(output_dir, self.ai_client)
        self.generation_thread.output_signal.connect(self.append_output)
        self.generation_thread.finished_signal.connect(self.generation_finished)
        self.generation_thread.start()

    def generation_finished(self, success, message):
        """生成完成"""
        # 恢复按钮
        self.generate_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)

        # 更新状态
        self.append_output(f"\n{message}")

        if success:
            self.status_label.setText(f"完成: {message}")
            self.status_label.setStyleSheet("color: #4CAF50; padding: 5px;")
        else:
            self.status_label.setText(f"失败: {message}")
            self.status_label.setStyleSheet("color: #f44336; padding: 5px;")

        self.append_output("=" * 60 + "\n")

    def append_output(self, text):
        """添加输出"""
        self.output_text.append(text)
        # 自动滚动到底部
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
