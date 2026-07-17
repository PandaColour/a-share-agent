# -*- coding: utf-8 -*-
"""
主窗口 - 左侧菜单栏 + 右侧工作区布局
"""
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QStackedWidget, QPushButton, QFrame,
                             QStatusBar, QMessageBox, QLabel)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont

from src.qt.analysis_widget import AnalysisWidget
from src.qt.holdings_widget import HoldingsWidget
from src.qt.backtest_widget import BacktestWidget
from src.qt.media_widget import MediaWidget
from src.qt.stock_comparison_widget import StockComparisonWidget
from src.qt.research_mode_widget import ResearchModeWidget


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("A股量化交易系统")
        self.setGeometry(100, 100, 1120, 720)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局 - 水平布局（左右结构）
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 左侧菜单栏 ===
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)

        # === 右侧工作区 ===
        self.stacked_widget = QStackedWidget()

        # 创建页面
        self.analysis_widget = AnalysisWidget()
        self.holdings_widget = HoldingsWidget()
        self.backtest_widget = BacktestWidget()
        self.media_widget = MediaWidget()
        self.comparison_widget = StockComparisonWidget()
        self.research_widget = ResearchModeWidget()

        # 添加到堆叠窗口
        self.stacked_widget.addWidget(self.analysis_widget)   # index 0
        self.stacked_widget.addWidget(self.holdings_widget)   # index 1
        self.stacked_widget.addWidget(self.backtest_widget)   # index 2
        self.stacked_widget.addWidget(self.media_widget)      # index 3
        self.stacked_widget.addWidget(self.comparison_widget) # index 4
        self.stacked_widget.addWidget(self.research_widget)   # index 5

        main_layout.addWidget(self.stacked_widget)

        central_widget.setLayout(main_layout)

        # 创建菜单栏
        self.create_menu_bar()

        # 创建状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")

        # 设置窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
        """)

    def create_sidebar(self):
        """创建左侧菜单栏"""
        sidebar = QFrame()
        sidebar.setFrameShape(QFrame.Shape.StyledPanel)
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                border-right: 1px solid #34495e;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        title_label = QLabel("A股量化系统")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 20px 10px;
                background-color: #1a252f;
            }
        """)
        layout.addWidget(title_label)

        # 菜单按钮样式
        button_style = """
            QPushButton {
                color: #ecf0f1;
                background-color: transparent;
                border: none;
                text-align: left;
                padding: 15px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QPushButton:checked {
                background-color: #3498db;
                border-left: 4px solid #2980b9;
            }
        """

        # 分析按钮
        self.analysis_btn = QPushButton("📊 股票分析")
        self.analysis_btn.setCheckable(True)
        self.analysis_btn.setChecked(True)
        self.analysis_btn.setStyleSheet(button_style)
        self.analysis_btn.clicked.connect(lambda: self.switch_page(0))
        layout.addWidget(self.analysis_btn)

        # 持股跟踪按钮
        self.holdings_btn = QPushButton("💼 持股跟踪")
        self.holdings_btn.setCheckable(True)
        self.holdings_btn.setStyleSheet(button_style)
        self.holdings_btn.clicked.connect(lambda: self.switch_page(1))
        layout.addWidget(self.holdings_btn)

        # 历史回测按钮
        self.backtest_btn = QPushButton("📈 历史回测")
        self.backtest_btn.setCheckable(True)
        self.backtest_btn.setStyleSheet(button_style)
        self.backtest_btn.clicked.connect(lambda: self.switch_page(2))
        layout.addWidget(self.backtest_btn)

        # 因子研究按钮
        self.research_btn = QPushButton("🔬 因子研究")
        self.research_btn.setCheckable(True)
        self.research_btn.setStyleSheet(button_style)
        self.research_btn.clicked.connect(lambda: self.switch_page(5))
        layout.addWidget(self.research_btn)

        # 自媒体内容按钮
        self.media_btn = QPushButton("📱 自媒体")
        self.media_btn.setCheckable(True)
        self.media_btn.setStyleSheet(button_style)
        self.media_btn.clicked.connect(lambda: self.switch_page(3))
        layout.addWidget(self.media_btn)

        # 股票对比按钮
        self.comparison_btn = QPushButton("🔄 股票对比")
        self.comparison_btn.setCheckable(True)
        self.comparison_btn.setStyleSheet(button_style)
        self.comparison_btn.clicked.connect(lambda: self.switch_page(4))
        layout.addWidget(self.comparison_btn)

        # 添加弹性空间
        layout.addStretch()

        # 底部信息
        info_label = QLabel("v1.0")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("""
            QLabel {
                color: #7f8c8d;
                font-size: 10px;
                padding: 10px;
            }
        """)
        layout.addWidget(info_label)

        sidebar.setLayout(layout)
        return sidebar

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        # 退出
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")

        # 切换到分析
        analysis_action = QAction("股票分析(&A)", self)
        analysis_action.setShortcut("Ctrl+1")
        analysis_action.triggered.connect(lambda: self.switch_page(0))
        view_menu.addAction(analysis_action)

        # 切换到持股
        holdings_action = QAction("持股跟踪(&H)", self)
        holdings_action.setShortcut("Ctrl+2")
        holdings_action.triggered.connect(lambda: self.switch_page(1))
        view_menu.addAction(holdings_action)

        # 切换到回测
        backtest_action = QAction("历史回测(&B)", self)
        backtest_action.setShortcut("Ctrl+3")
        backtest_action.triggered.connect(lambda: self.switch_page(2))
        view_menu.addAction(backtest_action)

        # 切换到因子研究
        research_action = QAction("因子研究(&R)", self)
        research_action.setShortcut("Ctrl+6")
        research_action.triggered.connect(lambda: self.switch_page(5))
        view_menu.addAction(research_action)

        # 切换到自媒体
        media_action = QAction("自媒体内容(&M)", self)
        media_action.setShortcut("Ctrl+4")
        media_action.triggered.connect(lambda: self.switch_page(3))
        view_menu.addAction(media_action)

        # 切换到股票对比
        comparison_action = QAction("股票对比(&C)", self)
        comparison_action.setShortcut("Ctrl+5")
        comparison_action.triggered.connect(lambda: self.switch_page(4))
        view_menu.addAction(comparison_action)

        view_menu.addSeparator()

        # 刷新
        refresh_action = QAction("刷新当前页(&R)", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_current)
        view_menu.addAction(refresh_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        # 关于
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def switch_page(self, index):
        """切换页面"""
        # 更新按钮状态
        self.analysis_btn.setChecked(index == 0)
        self.holdings_btn.setChecked(index == 1)
        self.backtest_btn.setChecked(index == 2)
        self.media_btn.setChecked(index == 3)
        self.comparison_btn.setChecked(index == 4)
        self.research_btn.setChecked(index == 5)

        # 切换页面
        self.stacked_widget.setCurrentIndex(index)

        # 更新状态栏
        page_names = ["股票分析", "持股跟踪", "历史回测", "自媒体内容", "股票对比", "因子研究"]
        self.statusBar.showMessage(f"当前页面: {page_names[index]}")

    def refresh_current(self):
        """刷新当前页面"""
        current_index = self.stacked_widget.currentIndex()

        if current_index == 0:
            # 分析页面无需刷新（每次分析都是新的）
            self.statusBar.showMessage("分析页面无需刷新")
        elif current_index == 1:
            # 刷新持股数据
            self.holdings_widget.refresh_holdings()
            self.statusBar.showMessage("已刷新持股数据")
        elif current_index == 4:
            # 刷新股票对比数据
            self.comparison_widget.load_comparison_data()
            self.statusBar.showMessage("已刷新股票对比数据")

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于",
            "<h2>A股量化交易系统</h2>"
            "<p>版本: 1.0</p>"
            "<p>基于TradingAgents框架的A股量化交易系统</p>"
            "<p>功能:</p>"
            "<ul>"
            "<li>📊 股票分析 - 智能选股和分析 (Ctrl+1)</li>"
            "<li>💼 持股跟踪 - 实时监控持仓 (Ctrl+2)</li>"
            "<li>📈 历史回测 - 策略回测验证 (Ctrl+3)</li>"
            "<li>📱 自媒体内容 - 小红书文案生成 (Ctrl+4)</li>"
            "<li>🔄 股票对比 - 动态选股与持仓对比 (Ctrl+5)</li>"
            "<li>🔬 因子研究 - 研究模式说明和启用方式 (Ctrl+6)</li>"
            "</ul>"
            "<p>快捷键:</p>"
            "<ul>"
            "<li>Ctrl+1: 切换到股票分析</li>"
            "<li>Ctrl+2: 切换到持股跟踪</li>"
            "<li>Ctrl+3: 切换到历史回测</li>"
            "<li>Ctrl+4: 切换到自媒体内容</li>"
            "<li>Ctrl+5: 切换到股票对比</li>"
            "<li>Ctrl+6: 切换到因子研究</li>"
            "<li>F5: 刷新当前页</li>"
            "<li>Ctrl+Q: 退出程序</li>"
            "</ul>"
            "<p>© 2025 A-Share Agent</p>"
        )

    def closeEvent(self, event):
        """关闭事件"""
        # 检查是否有正在运行的分析或回测
        analysis_running = (hasattr(self.analysis_widget, 'analysis_thread') and
                          self.analysis_widget.analysis_thread and
                          self.analysis_widget.analysis_thread.isRunning())

        backtest_running = (hasattr(self.backtest_widget, 'backtest_thread') and
                          self.backtest_widget.backtest_thread and
                          self.backtest_widget.backtest_thread.isRunning())

        if analysis_running or backtest_running:
            running_tasks = []
            if analysis_running:
                running_tasks.append("分析")
            if backtest_running:
                running_tasks.append("回测")

            reply = QMessageBox.question(
                self,
                "确认退出",
                f"{'、'.join(running_tasks)}正在运行中，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # 停止所有运行中的线程
                if analysis_running:
                    self.analysis_widget.analysis_thread.stop()
                    self.analysis_widget.analysis_thread.wait()

                if backtest_running:
                    self.backtest_widget.backtest_thread.stop()
                    self.backtest_widget.backtest_thread.wait()

                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
