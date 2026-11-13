"""
启动加载画面 — 秒显示，加载完成后自动关闭。
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont


class SplashScreen(QWidget):
    """启动浮窗，纯 PyQt6 组件，无任何重库依赖。"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(380, 160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(12)

        # 标题
        title = QLabel("AI 语音提词器")
        title.setFont(QFont("PingFang SC", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #FFFFFF; background: transparent;")
        layout.addWidget(title)

        # 状态文字
        self._status = QLabel("正在启动...")
        self._status.setFont(QFont("PingFang SC", 12))
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("color: #AAAAAA; background: transparent;")
        layout.addWidget(self._status)

        # 进度条
        self._bar = QProgressBar()
        self._bar.setRange(0, 0)  # 不确定进度（来回跑）
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(4)
        self._bar.setStyleSheet("""
            QProgressBar {
                background-color: #333333;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #4A90D9;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self._bar)

        # 底部署名
        brand = QLabel("汪同学出品")
        brand.setFont(QFont("PingFang SC", 10))
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet("color: #666666; background: transparent;")
        layout.addWidget(brand)

        self.setStyleSheet("background-color: #1A1A1A; border-radius: 12px;")
        self._center_on_screen()

    def _center_on_screen(self):
        try:
            screen = self.screen()
            if screen is None:
                from PyQt6.QtWidgets import QApplication
                screen = QApplication.primaryScreen()
            geo = screen.geometry() if screen else self.frameGeometry()
            x = (geo.width() - self.width()) // 2
            y = (geo.height() - self.height()) // 2
            self.move(x, y)
        except Exception:
            pass  # 如果无法居中，保持默认位置

    def _start_loading(self):
        """这个方法由 main.py 在导入主窗口前调用。"""
        pass

    def set_status(self, text: str):
        self._status.setText(text)

    def update_progress(self, value: int, maximum: int = 100):
        self._bar.setRange(0, maximum)
        self._bar.setValue(value)
