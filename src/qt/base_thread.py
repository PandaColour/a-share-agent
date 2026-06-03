# -*- coding: utf-8 -*-
"""
基础线程类 - 提供子进程执行的公共逻辑
"""
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal


class SubprocessThread(QThread):
    """子进程执行线程基类，封装 subprocess.Popen 的通用执行逻辑"""
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.process = None

    def build_command(self):
        """子类重写以返回命令列表"""
        raise NotImplementedError

    def run(self):
        try:
            cmd = self.build_command()
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                universal_newlines=True
            )

            for line in self.process.stdout:
                line = line.rstrip()
                self._on_output_line(line)
                self.output_signal.emit(line)

            return_code = self.process.wait()
            self._on_completion(return_code)

        except Exception as e:
            self.finished_signal.emit(False, f"执行出错: {str(e)}")

    def _on_output_line(self, line):
        """子类可重写以拦截/处理每行输出"""

    def _on_completion(self, return_code):
        if return_code == 0:
            self.finished_signal.emit(True, "完成")
        else:
            self.finished_signal.emit(False, f"失败，返回码: {return_code}")

    def stop(self):
        if self.process:
            self.process.terminate()
