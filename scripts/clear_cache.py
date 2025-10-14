# -*- coding: utf-8 -*-
"""
清除Python缓存文件

当遇到导入问题或奇怪的行为时运行此脚本
"""

import os
import shutil
from pathlib import Path

def clear_python_cache(root_dir="."):
    """清除所有Python缓存文件"""
    root_path = Path(root_dir).resolve()

    pycache_dirs = []
    pyc_files = []

    print(f"扫描目录: {root_path}")
    print("-" * 60)

    # 查找__pycache__目录和.pyc文件
    for path in root_path.rglob("*"):
        if path.name == "__pycache__" and path.is_dir():
            pycache_dirs.append(path)
        elif path.suffix == ".pyc":
            pyc_files.append(path)

    # 删除__pycache__目录
    print(f"\n找到 {len(pycache_dirs)} 个 __pycache__ 目录")
    for pycache_dir in pycache_dirs:
        try:
            shutil.rmtree(pycache_dir)
            print(f"  删除: {pycache_dir.relative_to(root_path)}")
        except Exception as e:
            print(f"  失败: {pycache_dir.relative_to(root_path)} - {e}")

    # 删除.pyc文件
    print(f"\n找到 {len(pyc_files)} 个 .pyc 文件")
    for pyc_file in pyc_files:
        try:
            pyc_file.unlink()
            print(f"  删除: {pyc_file.relative_to(root_path)}")
        except Exception as e:
            print(f"  失败: {pyc_file.relative_to(root_path)} - {e}")

    print("\n" + "=" * 60)
    print(f"清理完成！")
    print(f"  删除了 {len(pycache_dirs)} 个缓存目录")
    print(f"  删除了 {len(pyc_files)} 个编译文件")
    print("=" * 60)

if __name__ == "__main__":
    import sys

    # 获取项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    print("\n" + "=" * 60)
    print("Python 缓存清理工具")
    print("=" * 60)

    clear_python_cache(project_root)

    print("\n提示: 清理后首次导入模块可能会稍慢，因为需要重新编译")
