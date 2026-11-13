"""
设置对话框
麦克风选择、跟随灵敏度、文稿目录等基础设置。
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QComboBox, QSlider, QLabel, QLineEdit,
    QGroupBox, QCheckBox, QFileDialog, QMessageBox, QScrollArea, QWidget,
    QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette, QPixmap

from utils.config import load_config, save_config
from speech.follower import JUMP_THRESHOLD as DEFAULT_JUMP_THRESHOLD


def _resource_path(relative_path: str) -> Path:
    """Return a source-tree or PyInstaller bundled resource path."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return bundle_root / relative_path


class DonationDialog(QDialog):
    """Read-only donation QR codes bundled with the application."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DonationDialog")
        self.setWindowTitle("请作者喝一杯咖啡")
        self.setModal(True)
        self.setMinimumSize(720, 570)
        self.setStyleSheet("""
            QDialog#DonationDialog { background-color: #1E1E1E; }
            QDialog#DonationDialog QLabel { background: transparent; }
            QDialog#DonationDialog QPushButton {
                background-color: #3A3A3A; color: #DDDDDD;
                border: 1px solid #555555; border-radius: 6px;
                padding: 7px 18px;
            }
            QDialog#DonationDialog QPushButton:hover {
                background-color: #4A4A4A; color: #FFFFFF;
            }
        """)

        layout = QVBoxLayout(self)
        title = QLabel("☕ 感谢支持汪同学的 AI 语音提词器")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title)

        hint = QLabel("请选择支付宝或微信扫码支持作者")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #999999; font-size: 12px;")
        layout.addWidget(hint)

        codes = QHBoxLayout()
        codes.setSpacing(18)
        codes.addWidget(self._make_code_panel(
            "支付宝", "resources/donation/alipay.png", "#1677FF"))
        codes.addWidget(self._make_code_panel(
            "微信", "resources/donation/wechat-qr.png", "#07C160"))
        layout.addLayout(codes)

        close_button = QPushButton("关闭")
        close_button.setMinimumSize(100, 36)
        close_button.clicked.connect(self.accept)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(close_button)
        close_row.addStretch()
        layout.addLayout(close_row)

    def _make_code_panel(self, title: str, resource: str, color: str) -> QWidget:
        panel = QFrame()
        panel.setFixedSize(330, 390)
        panel.setStyleSheet(
            "QFrame { background-color: #252525; border: 1px solid #444444; "
            "border-radius: 10px; }")
        panel_layout = QVBoxLayout(panel)

        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"border: none; color: {color}; font-size: 17px; font-weight: bold;")
        panel_layout.addWidget(label)

        image = QLabel()
        image.setFixedSize(310, 310)
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setStyleSheet("border: none; background: transparent;")
        pixmap = QPixmap(str(_resource_path(resource)))
        if pixmap.isNull():
            image.setText("二维码资源加载失败")
        else:
            image.setPixmap(pixmap.scaled(
                300, 300,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            ))
        panel_layout.addWidget(image, 1)
        return panel


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("⚙ 设置")
        self.setMinimumSize(560, 520)
        self.resize(600, 560)

        self._config = load_config()

        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 使用滚动区域避免内容被截断
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setObjectName("SettingsViewport")

        content = QWidget()
        content.setObjectName("SettingsContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(14)

        # ====== 音频设备 ======
        grp_audio = QGroupBox("🎤 麦克风")
        grp_audio.setMinimumHeight(70)
        form_audio = QFormLayout(grp_audio)
        form_audio.setContentsMargins(12, 18, 12, 10)
        form_audio.setSpacing(8)

        self.combo_mic = QComboBox()
        self.combo_mic.setMinimumWidth(300)
        self.combo_mic.setMinimumHeight(30)
        self._populate_mic_list()
        form_audio.addRow("输入设备:", self.combo_mic)
        layout.addWidget(grp_audio)

        # ====== 语音跟随 ======
        grp_voice = QGroupBox("🎯 语音跟随")
        grp_voice.setMinimumHeight(85)
        form_voice = QFormLayout(grp_voice)
        form_voice.setContentsMargins(12, 18, 12, 10)
        form_voice.setSpacing(6)

        self.slider_jump = QSlider(Qt.Orientation.Horizontal)
        self.slider_jump.setRange(2, 15)
        self.slider_jump.setMinimumHeight(24)
        self.slider_jump.setValue(
            self._config.get("jump_threshold", DEFAULT_JUMP_THRESHOLD))
        self.slider_jump.valueChanged.connect(self._on_jump_change)
        self.lbl_jump = QLabel(f"{self.slider_jump.value()} 字")
        self.lbl_jump.setFixedWidth(36)
        row_jump = QHBoxLayout()
        row_jump.addWidget(self.slider_jump)
        row_jump.addWidget(self.lbl_jump)
        form_voice.addRow("跳段灵敏度:", row_jump)

        lbl_hint = QLabel("偏移超过此字数视为跳段，越小越灵敏")
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet("color: #777; font-size: 11px; background: transparent;")
        form_voice.addRow("", lbl_hint)
        layout.addWidget(grp_voice)

        # ====== 文稿 ======
        grp_scripts = QGroupBox("📂 文稿")
        grp_scripts.setMinimumHeight(170)
        form_scripts = QFormLayout(grp_scripts)
        form_scripts.setContentsMargins(12, 18, 12, 10)
        form_scripts.setSpacing(8)

        self.line_scripts_dir = QLineEdit()
        self.line_scripts_dir.setMinimumHeight(30)
        self.line_scripts_dir.setText(
            self._config.get("scripts_dir",
                             str(Path.home() / ".voice_teleprompter" / "scripts")))
        self.btn_browse_dir = QPushButton("浏览...")
        self.btn_browse_dir.setMinimumHeight(30)
        self.btn_browse_dir.clicked.connect(self._on_browse_dir)
        row_dir = QHBoxLayout()
        row_dir.addWidget(self.line_scripts_dir)
        row_dir.addWidget(self.btn_browse_dir)
        form_scripts.addRow("文稿目录:", row_dir)

        self.chk_auto_save = QCheckBox("退出时自动保存当前文稿")
        self.chk_auto_save.setChecked(self._config.get("auto_save", True))
        form_scripts.addRow("", self.chk_auto_save)

        self.chk_preserve_line_breaks = QCheckBox("开启自由换行与段落保留")
        self.chk_preserve_line_breaks.setChecked(
            self._config.get("preserve_line_breaks", True))
        self.chk_preserve_line_breaks.setToolTip(
            "开启后保留粘贴文本的换行和空段；关闭后按原版连续排版")
        form_scripts.addRow("排版方式:", self.chk_preserve_line_breaks)

        lbl_line_break_hint = QLabel(
            "关闭：忽略所有手动换行，按原版连续排版；开启：保留并可自由调整段落。")
        lbl_line_break_hint.setWordWrap(True)
        lbl_line_break_hint.setStyleSheet(
            "color: #777; font-size: 11px; background: transparent;")
        form_scripts.addRow("", lbl_line_break_hint)
        layout.addWidget(grp_scripts)

        # ====== 模型 ======
        grp_model = QGroupBox("🧠 语音模型")
        grp_model.setMinimumHeight(70)
        form_model = QFormLayout(grp_model)
        form_model.setContentsMargins(12, 18, 12, 10)
        form_model.setSpacing(8)

        self.line_model_path = QLineEdit()
        self.line_model_path.setMinimumHeight(30)
        self.line_model_path.setText(self._config.get("model_path", ""))
        self.line_model_path.setPlaceholderText("留空 = 自动查找 models/ 目录")
        self.btn_browse_model = QPushButton("浏览...")
        self.btn_browse_model.setMinimumHeight(30)
        self.btn_browse_model.clicked.connect(self._on_browse_model)
        row_model = QHBoxLayout()
        row_model.addWidget(self.line_model_path)
        row_model.addWidget(self.btn_browse_model)
        form_model.addRow("模型路径:", row_model)
        layout.addWidget(grp_model)

        # ====== 支持作者（内置固定内容，不写入配置） ======
        donation_row = QHBoxLayout()
        donation_row.addStretch()
        self.btn_donation = QPushButton("☕ 请作者喝一杯咖啡")
        self.btn_donation.setObjectName("DonationButton")
        self.btn_donation.setMinimumSize(190, 38)
        self.btn_donation.setToolTip("查看作者的支付宝和微信收款码")
        self.btn_donation.clicked.connect(self._show_donation_dialog)
        donation_row.addWidget(self.btn_donation)
        layout.addLayout(donation_row)

        layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # ====== 底部按钮 ======
        footer = QWidget()
        footer.setObjectName("SettingsFooter")
        btn_row = QHBoxLayout(footer)
        btn_row.setContentsMargins(20, 0, 20, 12)
        btn_row.addStretch()

        self.btn_save = QPushButton("保存设置")
        self.btn_save.setMinimumSize(120, 36)
        self.btn_save.clicked.connect(self._on_save)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setMinimumSize(80, 36)
        self.btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_cancel)
        main_layout.addWidget(footer)

    def _populate_mic_list(self):
        import sounddevice as sd
        self.combo_mic.clear()
        saved_device = self._config.get("mic_device", "")
        selected_idx = 0

        try:
            devices = sd.query_devices()
            for dev in devices:
                if dev['max_input_channels'] > 0:
                    name = dev['name']
                    self.combo_mic.addItem(f"  {name}", name)
                    if name == saved_device:
                        selected_idx = self.combo_mic.count() - 1
        except Exception:
            self.combo_mic.addItem("  默认设备", "")

        self.combo_mic.setCurrentIndex(selected_idx)

    def _on_jump_change(self, v: int):
        self.lbl_jump.setText(f"{v} 字")

    def _on_browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择文稿目录")
        if path:
            self.line_scripts_dir.setText(path)

    def _on_browse_model(self):
        path = QFileDialog.getExistingDirectory(self, "选择模型目录")
        if path:
            self.line_model_path.setText(path)

    def _on_save(self):
        self._config["mic_device"] = self.combo_mic.currentData()
        self._config["jump_threshold"] = self.slider_jump.value()
        self._config["scripts_dir"] = self.line_scripts_dir.text()
        self._config["auto_save"] = self.chk_auto_save.isChecked()
        self._config["preserve_line_breaks"] = (
            self.chk_preserve_line_breaks.isChecked())
        self._config["model_path"] = self.line_model_path.text()

        save_config(self._config)
        QMessageBox.information(self, "设置已保存",
                                "设置已保存，部分更改下次启动时生效。")
        self.accept()

    def _show_donation_dialog(self):
        DonationDialog(self).exec()

    def _apply_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#1E1E1E"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#2D2D2D"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#252525"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#CCCCCC"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#3A3A3A"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#CCCCCC"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#4A90D9"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        self.setStyleSheet("""
            QDialog#SettingsDialog {
                background-color: #1E1E1E;
            }
            QWidget#SettingsContent,
            QWidget#SettingsFooter,
            QWidget#SettingsViewport {
                background-color: #1E1E1E;
            }
            QGroupBox {
                color: #CCCCCC;
                background-color: #1E1E1E;
                border: 1px solid #3A3A3A;
                border-radius: 8px;
                margin-top: 16px;
                padding: 20px 12px 12px 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 16px;
                top: 2px;
                padding: 0 6px;
                color: #CCCCCC;
                background-color: #1E1E1E;
            }
            QLabel {
                color: #CCCCCC;
                font-size: 13px;
                background: transparent;
            }
            QComboBox {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                min-height: 22px;
            }
            QComboBox::drop-down {
                background-color: #2D2D2D;
                border-left: 1px solid #444;
                width: 24px;
            }
            QComboBox::down-arrow {
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #2D2D2D;
                color: #FFFFFF;
                selection-background-color: #4A90D9;
                border: 1px solid #444;
            }
            QLineEdit {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                min-height: 20px;
            }
            QLineEdit:disabled,
            QComboBox:disabled {
                background-color: #252525;
                color: #777777;
                border-color: #3A3A3A;
            }
            QCheckBox {
                color: #CCCCCC;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px; height: 18px;
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #2D2D2D;
            }
            QCheckBox::indicator:checked {
                background-color: #4A90D9;
                border-color: #4A90D9;
            }
            QPushButton {
                background-color: #3A3A3A;
                color: #CCCCCC;
                border: 1px solid #4A4A4A;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #4A4A4A;
                color: #FFFFFF;
            }
            QPushButton#DonationButton {
                background-color: #6A4B2A;
                color: #FFE8BF;
                border-color: #9B7041;
                font-weight: bold;
            }
            QPushButton#DonationButton:hover {
                background-color: #805D35;
                color: #FFFFFF;
            }
            QSlider::groove:horizontal {
                background: #3A3A3A; height: 6px; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #4A90D9; width: 14px; height: 14px;
                margin: -4px 0; border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #4A90D9; border-radius: 3px;
            }
            QScrollArea {
                border: none;
                background-color: #1E1E1E;
            }
            QScrollBar:vertical {
                background-color: #1E1E1E;
                width: 12px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 6px;
                min-height: 28px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #666666;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
                border: none;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #4A90D9;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5A9FE9; }
        """)
