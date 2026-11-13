"""
全屏悬浮控制条 — 滑块版
半透明 QWidget 覆盖层，使用滑块实时调节参数。
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal


class ControlsBar(QWidget):
    """全屏底部悬浮控制条（滑块版）"""

    font_size_changed = pyqtSignal(int)
    bold_toggled = pyqtSignal(bool)
    words_per_line_changed = pyqtSignal(int)
    scroll_speed_changed = pyqtSignal(int)
    pos_percentage_changed = pyqtSignal(int)
    voice_follow_toggled = pyqtSignal(bool)
    exit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._font_size = 36
        self._bold = False
        self._words_per_line = 20
        self._scroll_speed = 5
        self._pos_percentage = 50
        self._voice_follow = False

        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self.hide)

        self._init_ui()
        self._apply_style()

    def _init_ui(self):
        """初始化控制条 UI —— 全部使用滑块"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        # ---- 字体大小组 ----
        lbl_font = QLabel("Aa")
        lbl_font.setFixedWidth(24)
        lbl_font.setStyleSheet("color: #CCCCCC; background: transparent; font-size: 14px; font-weight: bold;")

        self.slider_font = QSlider(Qt.Orientation.Horizontal)
        self.slider_font.setRange(18, 200)
        self.slider_font.setValue(self._font_size)
        self.slider_font.setFixedWidth(80)
        self.slider_font.valueChanged.connect(self._on_font_slider)
        self.slider_font.sliderReleased.connect(
            lambda: self.font_size_changed.emit(self._font_size))

        self.lbl_font_val = QLabel(f"{self._font_size}pt")
        self.lbl_font_val.setFixedWidth(32)
        self.lbl_font_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_font_val.setStyleSheet("color: #CCCCCC; background: transparent; font-size: 11px;")

        layout.addWidget(lbl_font)
        layout.addWidget(self.slider_font)
        layout.addWidget(self.lbl_font_val)

        # 分隔
        layout.addWidget(self._sep())

        # ---- 粗细切换 ----
        self.btn_bold = QPushButton("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setFixedSize(32, 32)
        self.btn_bold.clicked.connect(lambda: self.bold_toggled.emit(self.btn_bold.isChecked()))
        layout.addWidget(self.btn_bold)

        # 分隔
        layout.addWidget(self._sep())

        # ---- 文本宽度组 ----
        lbl_width = QLabel("☰")
        lbl_width.setFixedWidth(24)
        lbl_width.setStyleSheet("color: #CCCCCC; background: transparent; font-size: 14px;")

        self.slider_wpl = QSlider(Qt.Orientation.Horizontal)
        self.slider_wpl.setRange(4, 100)
        self.slider_wpl.setValue(self._words_per_line)
        self.slider_wpl.setFixedWidth(80)
        self.slider_wpl.valueChanged.connect(self._on_wpl_slider)
        self.slider_wpl.sliderReleased.connect(
            lambda: self.words_per_line_changed.emit(self._words_per_line))

        self.lbl_wpl_val = QLabel(f"{self._words_per_line}")
        self.lbl_wpl_val.setFixedWidth(24)
        self.lbl_wpl_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_wpl_val.setStyleSheet("color: #CCCCCC; background: transparent; font-size: 11px;")

        layout.addWidget(lbl_width)
        layout.addWidget(self.slider_wpl)
        layout.addWidget(self.lbl_wpl_val)

        # 分隔
        layout.addWidget(self._sep())

        # ---- 速度组 ----
        lbl_speed = QLabel("⏱")
        lbl_speed.setFixedWidth(24)
        lbl_speed.setStyleSheet("color: #CCCCCC; background: transparent; font-size: 14px;")

        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(1, 30)
        self.slider_speed.setValue(self._scroll_speed)
        self.slider_speed.setFixedWidth(60)
        self.slider_speed.valueChanged.connect(self._on_speed_slider)
        self.slider_speed.sliderReleased.connect(
            lambda: self.scroll_speed_changed.emit(self._scroll_speed))

        self.lbl_speed_val = QLabel(f"{self._scroll_speed}")
        self.lbl_speed_val.setFixedWidth(20)
        self.lbl_speed_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_speed_val.setStyleSheet("color: #CCCCCC; background: transparent; font-size: 11px;")

        layout.addWidget(lbl_speed)
        layout.addWidget(self.slider_speed)
        layout.addWidget(self.lbl_speed_val)

        # 分隔
        layout.addWidget(self._sep())

        # ---- 提词位置组 ----
        lbl_pos = QLabel("📍")
        lbl_pos.setFixedWidth(24)
        lbl_pos.setStyleSheet("color: #CCCCCC; background: transparent; font-size: 14px;")

        self.slider_pos = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos.setRange(10, 90)
        self.slider_pos.setValue(self._pos_percentage)
        self.slider_pos.setFixedWidth(60)
        self.slider_pos.valueChanged.connect(self._on_pos_slider)
        self.slider_pos.sliderReleased.connect(
            lambda: self.pos_percentage_changed.emit(self._pos_percentage))

        self.lbl_pos_val = QLabel(f"{self._pos_percentage}%")
        self.lbl_pos_val.setFixedWidth(28)
        self.lbl_pos_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_pos_val.setStyleSheet("color: #CCCCCC; background: transparent; font-size: 11px;")

        layout.addWidget(lbl_pos)
        layout.addWidget(self.slider_pos)
        layout.addWidget(self.lbl_pos_val)

        # 分隔
        layout.addWidget(self._sep())

        # ---- 语音跟随 ----
        self.btn_voice = QPushButton("🎤")
        self.btn_voice.setCheckable(True)
        self.btn_voice.setFixedSize(32, 32)
        self.btn_voice.clicked.connect(
            lambda: self.voice_follow_toggled.emit(self.btn_voice.isChecked()))
        layout.addWidget(self.btn_voice)

        # 识别文字显示
        self.lbl_recog_text = QLabel("")
        self.lbl_recog_text.setStyleSheet(
            "color: #4A90D9; background: transparent; font-size: 11px;"
        )
        self.lbl_recog_text.setMaximumWidth(160)
        layout.addWidget(self.lbl_recog_text)

        layout.addStretch()

        # ---- 退出 ----
        self.btn_exit = QPushButton("✕")
        self.btn_exit.setFixedSize(32, 32)
        self.btn_exit.clicked.connect(self.exit_requested.emit)
        layout.addWidget(self.btn_exit)

    def _sep(self) -> QLabel:
        sep = QLabel("│")
        sep.setFixedWidth(12)
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sep.setStyleSheet("color: #444; background: transparent; font-size: 12px;")
        return sep

    # ---- 滑块回调（即时更新标签） ----

    def _on_font_slider(self, v: int):
        self._font_size = v
        self.lbl_font_val.setText(f"{v}pt")

    def _on_wpl_slider(self, v: int):
        self._words_per_line = v
        self.lbl_wpl_val.setText(f"{v}")

    def _on_speed_slider(self, v: int):
        self._scroll_speed = v
        self.lbl_speed_val.setText(f"{v}")

    def _on_pos_slider(self, v: int):
        self._pos_percentage = v
        self.lbl_pos_val.setText(f"{v}%")

    # ---- 样式 ----

    def _apply_style(self):
        self.setStyleSheet("""
            ControlsBar {
                background-color: rgba(0, 0, 0, 200);
                border-top: 1px solid #444444;
            }
            QPushButton {
                background-color: #3A3A3A;
                color: #CCCCCC;
                border: 1px solid #555555;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #555555;
                color: #FFFFFF;
            }
            QPushButton:checked {
                background-color: #4A90D9;
                color: #FFFFFF;
                border-color: #4A90D9;
            }
            QSlider::groove:horizontal {
                background: #3A3A3A;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #4A90D9;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #4A90D9;
                border-radius: 2px;
            }
        """)
        self._update_voice_style()

    def _update_voice_style(self):
        if self._voice_follow:
            self.btn_voice.setStyleSheet("""
                QPushButton {
                    background-color: #E05A5A; color: #FFFFFF;
                    border: 1px solid #E05A5A; border-radius: 4px; font-size: 14px;
                }
                QPushButton:hover { background-color: #F06A6A; }
            """)
        else:
            self.btn_voice.setStyleSheet("""
                QPushButton {
                    background-color: #3A3A3A; color: #CCCCCC;
                    border: 1px solid #E05A5A; border-radius: 4px; font-size: 14px;
                }
                QPushButton:hover { background-color: #555555; }
            """)

    # ---- 公共接口 ----

    def set_values(self, font_size: int, bold: bool, words_per_line: int,
                   scroll_speed: int, voice_follow: bool,
                   pos_percentage: int = 50):
        self._font_size = font_size
        self._bold = bold
        self._words_per_line = words_per_line
        self._scroll_speed = scroll_speed
        self._voice_follow = voice_follow
        self._pos_percentage = pos_percentage

        self.slider_font.blockSignals(True)
        self.slider_font.setValue(font_size)
        self.slider_font.blockSignals(False)

        self.slider_wpl.blockSignals(True)
        self.slider_wpl.setValue(words_per_line)
        self.slider_wpl.blockSignals(False)

        self.slider_speed.blockSignals(True)
        self.slider_speed.setValue(scroll_speed)
        self.slider_speed.blockSignals(False)

        self.slider_pos.blockSignals(True)
        self.slider_pos.setValue(pos_percentage)
        self.slider_pos.blockSignals(False)

        self.btn_bold.setChecked(bold)
        self.btn_voice.setChecked(voice_follow)

        self.lbl_font_val.setText(f"{font_size}pt")
        self.lbl_wpl_val.setText(f"{words_per_line}")
        self.lbl_speed_val.setText(f"{scroll_speed}")
        self.lbl_pos_val.setText(f"{pos_percentage}%")

        self._update_voice_style()

    def show_at_bottom(self):
        self.show()
        self.raise_()
        self._auto_hide_timer.start(3000)

    def set_width_capped(self, capped: bool):
        """文本宽度达到硬性上限时，标签变红提醒"""
        if capped:
            self.lbl_wpl_val.setStyleSheet(
                "color: #FF5555; background: transparent; font-size: 11px; font-weight: bold;"
            )
        else:
            self.lbl_wpl_val.setStyleSheet(
                "color: #CCCCCC; background: transparent; font-size: 11px;"
            )

    def show_max_width_toast(self):
        """显示'已达到最大宽度'的短暂提示"""
        if not hasattr(self, '_toast_label'):
            self._toast_label = QLabel("已达到最大宽度", self)
            self._toast_label.setStyleSheet("""
                background-color: rgba(200, 50, 50, 220); color: #FFFFFF;
                padding: 6px 14px; border-radius: 6px; font-size: 12px;
                font-weight: bold;
            """)
            self._toast_label.hide()
            self._toast_timer = QTimer(self)
            self._toast_timer.setSingleShot(True)
            self._toast_timer.timeout.connect(self._toast_label.hide)

        # 定位在宽度滑块上方
        slider_pos = self.slider_wpl.mapTo(self, self.slider_wpl.rect().topLeft())
        self._toast_label.move(slider_pos.x() + 10, -30)
        self._toast_label.show()
        self._toast_label.raise_()
        self._toast_timer.start(2000)

    def stay_visible(self):
        self._auto_hide_timer.stop()

    def set_recognition_active(self, active: bool):
        """语音识别活动指示灯"""
        if active:
            self.btn_voice.setStyleSheet("""
                QPushButton {
                    background-color: #FF4444; color: #FFFFFF;
                    border: 2px solid #FF6666; border-radius: 4px; font-size: 14px;
                }
            """)
        elif self._voice_follow:
            self._update_voice_style()

    def set_recognition_text(self, text: str):
        """显示识别到的文字（调试）"""
        short = text[:20] + "…" if len(text) > 20 else text
        self.lbl_recog_text.setText(short)

    def start_hide_timer(self):
        self._auto_hide_timer.start(3000)
