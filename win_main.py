#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股量化交易系统 - PyQt6图形界面入口
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase
from src.qt.main_window import MainWindow


PREFERRED_UI_FONTS = (
    "PingFang SC",
    "Helvetica Neue",
    "Arial",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "WenQuanYi Micro Hei",
)


def choose_application_font_family(available_families):
    """从已安装字体里选择一个真实存在的界面字体。"""
    available = set(available_families)
    for family in PREFERRED_UI_FONTS:
        if family in available:
            return family
    return ""


def configure_application_font(app):
    """避免 Qt/Fusion 使用缺失的 Sans Serif 默认别名。"""
    family = choose_application_font_family(QFontDatabase.families())
    if family:
        app.setFont(QFont(family))


def main():
    """主函数"""
    # 启用高DPI缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # 创建应用
    app = QApplication(sys.argv)
    configure_application_font(app)
    app.setApplicationName("A股量化交易系统")
    app.setOrganizationName("A-Share Agent")

    # 设置应用样式
    app.setStyle("Fusion")

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
