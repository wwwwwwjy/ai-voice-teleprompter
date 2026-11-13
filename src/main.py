"""
AI 语音提词器 — 入口文件
先弹启动浮窗，再加载主程序。
"""

import sys
import os
import faulthandler
import traceback
from datetime import datetime
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


_crash_log_handle = None


def _install_crash_logging():
    """把 Python 异常和原生崩溃信息写入用户目录，便于 Windows 排查。"""
    global _crash_log_handle
    log_dir = Path.home() / ".voice_teleprompter"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        _crash_log_handle = open(log_dir / "crash.log", "a", encoding="utf-8", buffering=1)
        _crash_log_handle.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] app start\n")
        faulthandler.enable(_crash_log_handle)
    except OSError:
        _crash_log_handle = None

    original_hook = sys.excepthook

    def log_exception(exc_type, exc_value, exc_tb):
        if _crash_log_handle is not None:
            traceback.print_exception(exc_type, exc_value, exc_tb, file=_crash_log_handle)
        original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = log_exception


def _set_splash_progress(app: QApplication, splash, text: str, value: int):
    splash.set_status(text)
    splash.update_progress(value)
    splash.show()
    splash.raise_()
    app.processEvents()


def main():
    _install_crash_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("AI 语音提词器")

    # ---- 立即显示浮窗 ----
    from ui.splash import SplashScreen
    splash = SplashScreen()
    splash.setWindowFlags(
        Qt.WindowType.FramelessWindowHint |
        Qt.WindowType.WindowStaysOnTopHint
    )
    splash.show()
    splash.raise_()
    splash.update_progress(8)
    app.processEvents()

    # ---- 加载主程序 ----
    _set_splash_progress(app, splash, "准备运行环境...", 18)

    _set_splash_progress(app, splash, "加载界面组件...", 35)
    from ui.main_window import MainWindow

    _set_splash_progress(app, splash, "初始化主窗口...", 62)
    window = MainWindow()

    _set_splash_progress(app, splash, "启动语音模型后台加载...", 82)
    window.show()

    _set_splash_progress(app, splash, "完成", 100)
    splash.close()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
