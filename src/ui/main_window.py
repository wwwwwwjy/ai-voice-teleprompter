"""
主窗口 — 控制面板
左侧文件列表 + 右侧文本编辑、参数调节、全屏启动。
"""

import os
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QSlider, QLabel, QPlainTextEdit, QButtonGroup,
    QFileDialog, QMessageBox, QFrame, QListWidget, QListWidgetItem,
    QAbstractItemView, QLineEdit, QCheckBox, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ui.fullscreen import FullscreenWindow
from ui.settings_dialog import SettingsDialog
from ui.updates import UpdateController
from ui.text_preview import TextPreview
from utils.config import (
    load_config, save_config, save_last_text, load_last_text, get_scripts_dir
)
from utils.file_io import (
    IMPORTABLE_SUFFIXES, read_importable_document, read_text_file, write_text_file,
)
from speech.recognizer import SpeechRecognizer


class MainWindow(QMainWindow):
    """提词器主控制面板"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("汪同学的AI语音提词器")
        self.setMinimumSize(900, 600)

        # 从磁盘加载配置
        self._config = load_config()
        self.scripts_dir = get_scripts_dir(self._config)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

        self.font_size = self._config.get("font_size", 36)
        self.font_bold = self._config.get("font_bold", False)
        self.words_per_line = self._config.get("words_per_line", 20)
        self.scroll_speed = self._config.get("scroll_speed", 5)
        self.pos_percentage = self._config.get("pos_percentage", 50)
        self.voice_follow_enabled = self._config.get("voice_follow_enabled", False)
        self.preserve_line_breaks = self._config.get("preserve_line_breaks", True)
        win_w = self._config.get("window_width", 1100)
        win_h = self._config.get("window_height", 700)
        self.resize(win_w, win_h)

        self._current_file_path: str | None = None

        self._init_ui()
        self._apply_theme()
        self._refresh_file_list()

        # 加载上次编辑的文本
        last_text = load_last_text()
        if last_text:
            self.text_editor.setPlainText(self._format_loaded_text(last_text))
            self._refresh_preview()

        self._init_recognizer()
        self.updater = UpdateController(self)
        if self._config.get("auto_check_updates", True):
            QTimer.singleShot(1500, self.updater.check)

    # ================================================================
    # 初始化
    # ================================================================

    def _init_recognizer(self):
        """初始化语音识别器，模型在后台子线程加载（秒开界面）"""
        self.recognizer = SpeechRecognizer(self)
        self.recognizer.status_changed.connect(self._on_recognizer_status)
        self.recognizer.partial_result.connect(self._on_recognizer_partial)
        self.recognizer.final_result.connect(self._on_recognizer_final)
        self.recognizer.error_occurred.connect(self._on_recognizer_error)
        self.recognizer.debug_info.connect(self._on_recognizer_debug)
        self.recognizer.model_ready.connect(self._on_model_ready)
        self.recognizer.set_device(self._config.get("mic_device", ""))

        # Windows 上延迟到用户开启语音跟随时再加载，避免原生语音库
        # 在主界面刚出现时拖慢或影响整个进程。
        if sys.platform == "win32":
            self.lbl_voice_status.setText("🎤 语音模型待命")
        else:
            self.lbl_voice_status.setText("🎤 加载中...")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, self.recognizer.load_model_async)

    def _on_model_ready(self, success: bool, data: str):
        if success:
            name = Path(data).name if data else "已加载"
            self.lbl_voice_status.setText(f"🎤 {name}")
        else:
            self.lbl_voice_status.setText("⚠️ 模型未找到")

    def _init_ui(self):
        """初始化界面布局 —— 左侧文件列表 + 右侧主区域"""
        central = QWidget()
        self.setCentralWidget(central)

        # ---- 使用水平分割器 ----
        splitter = QSplitter(Qt.Orientation.Horizontal, central)

        # ====== 左侧：文件列表 ======
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        # 标题
        lbl_files = QLabel("📂 文稿")
        lbl_files.setStyleSheet("color: #CCCCCC; font-size: 13px; font-weight: bold; background: transparent;")
        left_layout.addWidget(lbl_files)

        # 快速保存输入框 + 按钮
        save_row = QHBoxLayout()
        self.input_filename = QLineEdit()
        self.input_filename.setPlaceholderText("文件名...")
        self.input_filename.setStyleSheet("""
            QLineEdit {
                background-color: #2D2D2D; color: #FFFFFF;
                border: 1px solid #444; border-radius: 4px;
                padding: 4px 8px; font-size: 12px;
            }
        """)
        self.btn_quick_save = QPushButton("💾")
        self.btn_quick_save.setFixedSize(32, 28)
        self.btn_quick_save.setToolTip("保存当前内容为新文件")
        self.btn_quick_save.clicked.connect(self._on_quick_save)
        save_row.addWidget(self.input_filename)
        save_row.addWidget(self.btn_quick_save)
        left_layout.addLayout(save_row)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.file_list.itemClicked.connect(self._on_file_selected)
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: #252525;
                color: #CCCCCC;
                border: 1px solid #3A3A3A;
                border-radius: 6px;
                font-size: 13px;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #3A3A3A;
                color: #FFFFFF;
            }
            QListWidget::item:selected {
                background-color: #4A90D9;
                color: #FFFFFF;
            }
        """)
        left_layout.addWidget(self.file_list)

        file_actions = QHBoxLayout()
        self.btn_import_files = QPushButton("导入")
        self.btn_export_files = QPushButton("导出")
        self.chk_multi_select = QCheckBox("多选")
        self.chk_multi_select.toggled.connect(self._on_multi_select_toggled)
        self.btn_import_files.setToolTip("批量导入 TXT、Word、RTF 或 ODT 文稿")
        self.btn_export_files.setToolTip("导出所选文稿")
        self.btn_import_files.clicked.connect(self._on_import_files)
        self.btn_export_files.clicked.connect(self._on_export_files)
        file_actions.addWidget(self.btn_import_files)
        file_actions.addWidget(self.btn_export_files)
        file_actions.addWidget(self.chk_multi_select)
        left_layout.addLayout(file_actions)

        manage_actions = QHBoxLayout()
        self.btn_rename_file = QPushButton("✏️ 重命名")
        self.btn_rename_file.clicked.connect(self._on_rename_file)
        # 删除按钮
        self.btn_delete_file = QPushButton("🗑 删除")
        self.btn_delete_file.clicked.connect(self._on_delete_file)
        manage_actions.addWidget(self.btn_rename_file)
        manage_actions.addWidget(self.btn_delete_file)
        left_layout.addLayout(manage_actions)

        left_panel.setFixedWidth(200)
        splitter.addWidget(left_panel)

        # ====== 右侧面板：上固定 + 下左右分栏 ======
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 8, 8, 0)
        right_layout.setSpacing(4)

        # ---- 固定顶部：工具栏 ----
        toolbar = QHBoxLayout()
        self.btn_open = QPushButton("📁 打开")
        self.btn_save = QPushButton("💾 保存")
        self.btn_paste = QPushButton("📋 粘贴")
        self.btn_open.clicked.connect(self._on_open)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_paste.clicked.connect(self._on_paste)
        toolbar.addWidget(self.btn_open)
        toolbar.addWidget(self.btn_save)
        toolbar.addWidget(self.btn_paste)
        toolbar.addStretch()

        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setFixedSize(36, 36)
        self.btn_settings.setToolTip("设置")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setStyleSheet("""
            QPushButton {
                background-color: #3A3A3A; color: #CCCCCC;
                border: 1px solid #4A4A4A; border-radius: 6px;
                font-size: 22px; padding: 0px;
            }
            QPushButton:hover { background-color: #4A4A4A; color: #FFFFFF; }
        """)
        self.btn_settings.clicked.connect(self._on_settings)
        toolbar.addWidget(self.btn_settings)

        right_layout.addLayout(toolbar)
        right_layout.addWidget(self._make_divider())

        # ---- 固定：设置区域 ----
        right_layout.addLayout(self._make_settings())
        right_layout.addWidget(self._make_divider())

        # ---- 固定：操作按钮 + 语音状态 ----
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.btn_start = QPushButton("🔵 开始全屏提词")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self._on_start_fullscreen)

        self.btn_voice = QPushButton("🔴 开启语音跟随")
        self.btn_voice.setMinimumHeight(40)
        self.btn_voice.setCheckable(True)
        self.btn_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_voice.clicked.connect(self._on_voice_toggle)

        action_row.addWidget(self.btn_start)
        action_row.addWidget(self.btn_voice)
        right_layout.addLayout(action_row)

        # ---- 下方左右分栏：编辑区 ←→ 预览区 ----
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：文本编辑区（可折叠）
        self._editor_container = QWidget()
        editor_container_layout = QVBoxLayout(self._editor_container)
        editor_container_layout.setContentsMargins(0, 0, 4, 0)
        self.text_editor = QPlainTextEdit()
        self.text_editor.setPlaceholderText("在这里粘贴你的稿件内容...")
        self.text_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.text_editor.setFont(QFont("PingFang SC", 14))
        self.text_editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 8px;
                padding: 12px;
                font-size: 15px;
                font-family: 'PingFang SC';
                selection-background-color: #4A90D9;
            }
        """)
        self.text_editor.textChanged.connect(self._on_text_changed)
        editor_container_layout.addWidget(self.text_editor)
        bottom_splitter.addWidget(self._editor_container)

        # 右侧：实时预览
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(4, 0, 0, 0)
        preview_layout.setSpacing(0)

        lbl_preview = QLabel("全屏实时预览")
        lbl_preview.setFixedHeight(14)
        lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_preview.setStyleSheet("color: #666; font-size: 10px; background: transparent; padding: 0px; margin: 0px;")
        preview_layout.addWidget(lbl_preview)

        self.text_preview = TextPreview()
        preview_layout.addWidget(self.text_preview)

        bottom_splitter.addWidget(preview_panel)
        bottom_splitter.setSizes([400, 400])
        bottom_splitter.setStretchFactor(0, 1)
        bottom_splitter.setStretchFactor(1, 1)

        right_layout.addWidget(bottom_splitter)

        # ---- 底部迷你状态栏（单行居中，零多余高度） ----
        self.lbl_voice_status = QLabel("")
        self.lbl_voice_status.setFixedHeight(14)
        self.lbl_voice_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_voice_status.setStyleSheet(
            "color: #555; font-size: 10px; background: transparent; padding: 0px; margin: 0px;"
        )
        self.lbl_file_status = QLabel("")
        self.lbl_file_status.setFixedHeight(14)
        self.lbl_file_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_file_status.setStyleSheet(
            "color: #444; font-size: 10px; background: transparent; padding: 0px; margin: 0px;"
        )
        # 单行水平 layout，无任何多余空间
        status_bar = QHBoxLayout()
        status_bar.setContentsMargins(0, 0, 0, 0)
        status_bar.setSpacing(0)
        status_bar.addStretch()
        status_bar.addWidget(self.lbl_voice_status)
        status_bar.addWidget(self.lbl_file_status)
        status_bar.addStretch()
        right_layout.addLayout(status_bar)

        # 作者署名
        self.lbl_brand = QLabel("汪同学出品")
        self.lbl_brand.setFixedHeight(14)
        self.lbl_brand.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_brand.setStyleSheet(
            "color: #555; font-size: 10px; background: transparent; padding: 0px; margin: 0px;"
        )
        right_layout.addWidget(self.lbl_brand)

        splitter.addWidget(right_panel)

        # 主分割器比例
        splitter.setSizes([200, 1000])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # 主布局
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(splitter)

    def _make_settings(self) -> QVBoxLayout:
        """创建设置区域（扩大滑块范围）"""
        settings = QVBoxLayout()
        settings.setSpacing(6)

        # 字体大小: 18-200
        row1 = QHBoxLayout()
        lbl_font = QLabel("字体大小")
        lbl_font.setFixedWidth(70)
        self.slider_font_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_font_size.setRange(18, 200)
        self.slider_font_size.setValue(self.font_size)
        self.slider_font_size.valueChanged.connect(self._on_font_size_change)
        self.lbl_font_size_val = QLabel(f"{self.font_size} pt")
        self.lbl_font_size_val.setFixedWidth(55)
        self.lbl_font_size_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        row1.addWidget(lbl_font)
        row1.addWidget(self.slider_font_size)
        row1.addWidget(self.lbl_font_size_val)
        settings.addLayout(row1)

        # 文字粗细
        row2 = QHBoxLayout()
        lbl_weight = QLabel("文字粗细")
        lbl_weight.setFixedWidth(70)
        self.btn_weight_normal = QPushButton("常规")
        self.btn_weight_bold = QPushButton("加粗")
        self.btn_weight_normal.setCheckable(True)
        self.btn_weight_bold.setCheckable(True)
        self.btn_weight_normal.setChecked(not self.font_bold)
        self.btn_weight_bold.setChecked(self.font_bold)
        self.weight_group = QButtonGroup()
        self.weight_group.addButton(self.btn_weight_normal, 0)
        self.weight_group.addButton(self.btn_weight_bold, 1)
        self.weight_group.buttonClicked.connect(self._on_weight_change)
        row2.addWidget(lbl_weight)
        row2.addWidget(self.btn_weight_normal)
        row2.addWidget(self.btn_weight_bold)
        row2.addStretch()
        settings.addLayout(row2)

        # 文本宽度: 4-100（控制屏幕占比）
        row3 = QHBoxLayout()
        lbl_wpl = QLabel("文本宽度")
        lbl_wpl.setFixedWidth(70)
        self.slider_wpl = QSlider(Qt.Orientation.Horizontal)
        self.slider_wpl.setRange(4, 100)
        self.slider_wpl.setValue(self.words_per_line)
        self.slider_wpl.valueChanged.connect(self._on_wpl_change)
        self.lbl_wpl_val = QLabel(f"{self.words_per_line}")
        self.lbl_wpl_val.setFixedWidth(40)
        self.lbl_wpl_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        row3.addWidget(lbl_wpl)
        row3.addWidget(self.slider_wpl)
        row3.addWidget(self.lbl_wpl_val)
        settings.addLayout(row3)

        # 滚动速度: 1-30
        row4 = QHBoxLayout()
        lbl_speed = QLabel("滚动速度")
        lbl_speed.setFixedWidth(70)
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(1, 30)
        self.slider_speed.setValue(self.scroll_speed)
        self.slider_speed.valueChanged.connect(self._on_speed_change)
        self.lbl_speed_val = QLabel(f"{self.scroll_speed}")
        self.lbl_speed_val.setFixedWidth(40)
        self.lbl_speed_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        row4.addWidget(lbl_speed)
        row4.addWidget(self.slider_speed)
        row4.addWidget(self.lbl_speed_val)
        settings.addLayout(row4)

        # 提词位置: 10-90（高亮行在屏幕垂直方向的百分比 %）
        row5 = QHBoxLayout()
        lbl_pos = QLabel("提词位置")
        lbl_pos.setFixedWidth(70)
        self.slider_pos = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos.setRange(10, 90)
        self.slider_pos.setValue(self.pos_percentage)
        self.slider_pos.valueChanged.connect(self._on_pos_change)
        self.lbl_pos_val = QLabel(f"{self.pos_percentage}%")
        self.lbl_pos_val.setFixedWidth(40)
        self.lbl_pos_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        row5.addWidget(lbl_pos)
        row5.addWidget(self.slider_pos)
        row5.addWidget(self.lbl_pos_val)
        settings.addLayout(row5)

        return settings

    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        return line

    # ================================================================
    # 主题
    # ================================================================

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1A1A1A; }
            QLabel {
                color: #CCCCCC; font-size: 13px;
                font-family: 'PingFang SC', sans-serif;
            }
            QPushButton {
                background-color: #3A3A3A; color: #CCCCCC;
                border: 1px solid #4A4A4A; border-radius: 6px;
                padding: 8px 14px; font-size: 13px;
                font-family: 'PingFang SC', sans-serif;
            }
            QPushButton:hover { background-color: #4A4A4A; }
            QPushButton:checked {
                background-color: #4A90D9; color: #FFFFFF; border-color: #4A90D9;
            }
            QSlider::groove:horizontal {
                background: #3A3A3A; height: 6px; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #4A90D9; width: 16px; height: 16px;
                margin: -5px 0; border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background: #4A90D9; border-radius: 3px;
            }
            QFrame { color: #3A3A3A; }
        """)

        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #4A90D9; color: #FFFFFF; border: none;
                border-radius: 8px; padding: 12px 28px;
                font-size: 16px; font-weight: bold;
                font-family: 'PingFang SC', sans-serif;
            }
            QPushButton:hover { background-color: #5A9FE9; }
            QPushButton:pressed { background-color: #3A80C9; }
        """)

        self.text_editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 8px;
                padding: 12px;
                font-size: 15px;
                font-family: 'PingFang SC';
                selection-background-color: #4A90D9;
            }
        """)

        self._update_voice_button_style()

    def _update_voice_button_style(self):
        if self.voice_follow_enabled:
            self.btn_voice.setStyleSheet("""
                QPushButton {
                    background-color: #E05A5A; color: #FFFFFF; border: none;
                    border-radius: 8px; padding: 12px 28px;
                    font-size: 16px; font-weight: bold;
                }
                QPushButton:hover { background-color: #F06A6A; }
            """)
            self.btn_voice.setText("🔴 关闭语音跟随")
        else:
            self.btn_voice.setStyleSheet("""
                QPushButton {
                    background-color: #C0392B; color: #FFFFFF;
                    border: none; border-radius: 8px;
                    padding: 12px 28px; font-size: 16px; font-weight: bold;
                }
                QPushButton:hover { background-color: #E05A5A; }
            """)
            self.btn_voice.setText("🔴 开启语音跟随")

    # ================================================================
    # 文件列表操作
    # ================================================================

    def _refresh_file_list(self):
        """刷新文件列表"""
        self.file_list.clear()
        if not self.scripts_dir.exists():
            return
        txt_files = sorted(self.scripts_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        for fp in txt_files:
            item = QListWidgetItem(fp.name)
            item.setData(Qt.ItemDataRole.UserRole, str(fp))
            self.file_list.addItem(item)

    def _on_file_selected(self, item: QListWidgetItem):
        """点击文件列表项 → 加载内容"""
        if self.chk_multi_select.isChecked():
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        try:
            content = read_text_file(path)
            self.text_editor.setPlainText(self._format_loaded_text(content))
            self._current_file_path = path
            self.input_filename.setText(Path(path).stem)
            self.lbl_file_status.setText(Path(path).name)
        except Exception as e:
            QMessageBox.warning(self, "读取失败", str(e))

    def _on_quick_save(self):
        """快速保存到 scripts 目录"""
        name = self.input_filename.text().strip()
        if not name:
            QMessageBox.information(self, "提示", "请先在左侧输入文件名。")
            return
        if not name.endswith(".txt"):
            name += ".txt"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        path = str(self.scripts_dir / name)
        try:
            write_text_file(path, self.text_editor.toPlainText())
            self._current_file_path = path
            self._refresh_file_list()
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def _on_delete_file(self):
        """删除一个或多个选中的文件。"""
        items = self.file_list.selectedItems()
        if not items:
            return
        names = "、".join(item.text() for item in items[:3])
        if len(items) > 3:
            names += f" 等 {len(items)} 个文件"
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除「{names}」吗？此操作无法撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            failures = []
            for item in items:
                path = item.data(Qt.ItemDataRole.UserRole)
                try:
                    os.remove(path)
                    if self._current_file_path == path:
                        self._current_file_path = None
                        self.input_filename.clear()
                except OSError as e:
                    failures.append(f"{item.text()}：{e}")
            self._refresh_file_list()
            if failures:
                QMessageBox.warning(self, "部分文件删除失败", "\n".join(failures))

    def _on_multi_select_toggled(self, enabled: bool):
        self.file_list.clearSelection()
        mode = (QAbstractItemView.SelectionMode.ExtendedSelection if enabled
                else QAbstractItemView.SelectionMode.SingleSelection)
        self.file_list.setSelectionMode(mode)
        self.btn_rename_file.setEnabled(not enabled)

    def _selected_file_paths(self) -> list[Path]:
        return [Path(item.data(Qt.ItemDataRole.UserRole))
                for item in self.file_list.selectedItems()]

    def _on_rename_file(self):
        paths = self._selected_file_paths()
        if len(paths) != 1:
            QMessageBox.information(self, "提示", "请先选择一个文稿进行重命名。")
            return
        source = paths[0]
        name, accepted = QInputDialog.getText(
            self, "重命名文稿", "文件名：", text=source.stem)
        name = name.strip()
        if not accepted or not name:
            return
        if not name.lower().endswith(".txt"):
            name += ".txt"
        target = source.with_name(name)
        if target.exists() and target != source:
            QMessageBox.warning(self, "重命名失败", "同名文稿已存在。")
            return
        try:
            source.rename(target)
            if self._current_file_path == str(source):
                self._current_file_path = str(target)
                self.input_filename.setText(target.stem)
            self._refresh_file_list()
        except OSError as e:
            QMessageBox.warning(self, "重命名失败", str(e))

    def _on_import_files(self):
        filters = "支持的文稿 (*.txt *.doc *.docx *.rtf *.odt);;所有文件 (*)"
        paths, _ = QFileDialog.getOpenFileNames(
            self, "批量导入文稿", str(self.scripts_dir), filters)
        if not paths:
            return
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        imported, failures = [], []
        for raw_path in paths:
            source = Path(raw_path)
            if source.suffix.lower() not in IMPORTABLE_SUFFIXES:
                failures.append(f"{source.name}：不支持的文件类型")
                continue
            try:
                content = read_importable_document(str(source))
                target = self._next_available_script_path(source.stem)
                write_text_file(str(target), content)
                imported.append(target.name)
            except (OSError, ValueError) as e:
                failures.append(f"{source.name}：{e}")
        self._refresh_file_list()
        message = f"已导入 {len(imported)} 个文稿。"
        if failures:
            message += "\n\n以下文件未导入：\n" + "\n".join(failures)
        QMessageBox.information(self, "导入完成", message)

    def _on_export_files(self):
        paths = self._selected_file_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先选择要导出的文稿。")
            return
        target_dir = QFileDialog.getExistingDirectory(self, "选择导出文件夹")
        if not target_dir:
            return
        exported, failures = [], []
        destination = Path(target_dir)
        for source in paths:
            try:
                target = destination / source.name
                if target.exists():
                    target = self._next_available_path(destination, source.stem, source.suffix)
                write_text_file(str(target), read_text_file(str(source)))
                exported.append(target.name)
            except OSError as e:
                failures.append(f"{source.name}：{e}")
        message = f"已导出 {len(exported)} 个文稿到：\n{destination}"
        if failures:
            message += "\n\n以下文件未导出：\n" + "\n".join(failures)
        QMessageBox.information(self, "导出完成", message)

    def _next_available_script_path(self, stem: str) -> Path:
        return self._next_available_path(self.scripts_dir, stem, ".txt")

    @staticmethod
    def _next_available_path(directory: Path, stem: str, suffix: str) -> Path:
        candidate = directory / f"{stem}{suffix}"
        index = 2
        while candidate.exists():
            candidate = directory / f"{stem} ({index}){suffix}"
            index += 1
        return candidate

    # ================================================================
    # 槽函数
    # ================================================================

    def _on_font_size_change(self, value: int):
        self.font_size = value
        self.lbl_font_size_val.setText(f"{value} pt")
        self._refresh_preview()

    def _on_weight_change(self, btn):
        self.font_bold = (self.weight_group.id(btn) == 1)
        self._refresh_preview()

    def _on_wpl_change(self, value: int):
        self.words_per_line = value
        self.lbl_wpl_val.setText(f"{value}")
        self._refresh_preview()

    def _on_speed_change(self, value: int):
        self.scroll_speed = value
        self.lbl_speed_val.setText(f"{value}")

    def _on_pos_change(self, value: int):
        self.pos_percentage = value
        self.lbl_pos_val.setText(f"{value}%")

    def _on_text_changed(self):
        """文本编辑区内容变化 → 更新预览"""
        self._refresh_preview()

    def _refresh_preview(self):
        """刷新实时预览"""
        if hasattr(self, 'text_preview'):
            text = self.text_editor.toPlainText()
            self.text_preview.update_preview(
                text, self.font_size, self.font_bold, self.words_per_line,
                self.preserve_line_breaks
            )

    def _format_loaded_text(self, text: str) -> str:
        """按当前设置载入文本；关闭换行时恢复原版连续排版。"""
        if self.preserve_line_breaks:
            return text.replace("\r\n", "\n").replace("\r", "\n")
        return text.replace("\r\n", "").replace("\n", "").replace("\r", "")

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开文本文件", str(self.scripts_dir),
            "文本文件 (*.txt);;所有文件 (*)"
        )
        if path:
            try:
                content = read_text_file(path)
                self.text_editor.setPlainText(self._format_loaded_text(content))
                self._current_file_path = path
                self.input_filename.setText(Path(path).stem)
                self._refresh_file_list()
            except Exception as e:
                QMessageBox.warning(self, "打开失败", str(e))

    def _on_save(self):
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        default_path = str(self.scripts_dir / "稿件.txt")
        if self._current_file_path:
            default_path = self._current_file_path
        path, _ = QFileDialog.getSaveFileName(
            self, "保存文本文件", default_path,
            "文本文件 (*.txt);;所有文件 (*)"
        )
        if path:
            try:
                write_text_file(path, self.text_editor.toPlainText())
                self._current_file_path = path
                self.input_filename.setText(Path(path).stem)
                self._refresh_file_list()
            except Exception as e:
                QMessageBox.warning(self, "保存失败", str(e))

    def _on_paste(self):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if clipboard:
            text = clipboard.text()
            if text:
                self.text_editor.setPlainText(self._format_loaded_text(text))

    def _on_settings(self):
        """打开设置对话框"""
        dlg = SettingsDialog(self, updater=self.updater)
        accepted = dlg.exec()
        dlg.deleteLater()
        if self.updater.dialog is dlg:
            self.updater.dialog = None
        if not accepted:
            return

        old_model_path = self._config.get("model_path", "")
        self._config = load_config()
        old_preserve_line_breaks = self.preserve_line_breaks
        self.preserve_line_breaks = self._config.get("preserve_line_breaks", True)
        self.scripts_dir = get_scripts_dir(self._config)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self._refresh_file_list()
        self.recognizer.set_device(self._config.get("mic_device", ""))

        if old_preserve_line_breaks != self.preserve_line_breaks:
            current_text = self.text_editor.toPlainText()
            self.text_editor.setPlainText(self._format_loaded_text(current_text))
            self._refresh_preview()

        if self._config.get("model_path", "") != old_model_path:
            self.lbl_voice_status.setText("🎤 加载中...")
            self.recognizer.clear_model()
            self.recognizer.load_model_async()

    def _on_start_fullscreen(self):
        text = self.text_editor.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "提示", "请先输入文本内容。")
            if self.voice_follow_enabled:
                self.voice_follow_enabled = False
                self._update_voice_button_style()
            return
        self.recognizer.set_reference_text(text)
        self.hide()
        self._fullscreen = FullscreenWindow()
        self._fullscreen.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._fullscreen.load_settings(self.get_settings())
        self._fullscreen.load_text(text)
        # 全屏语音跟随开关 → 同步主窗口识别器
        self._fullscreen.voice_follow_changed.connect(self._on_fullscreen_voice_toggle)
        self._fullscreen.destroyed.connect(self._on_fullscreen_closed)
        self._fullscreen.showFullScreen()

    def _on_fullscreen_closed(self):
        """全屏关闭：同步设置回主窗口，始终关闭语音跟随"""
        if self._fullscreen is not None:
            settings = self._fullscreen.get_settings()
            self.font_size = settings["font_size"]
            self.font_bold = settings["font_bold"]
            self.words_per_line = settings["words_per_line"]
            self.scroll_speed = settings["scroll_speed"]
            self.pos_percentage = settings.get("pos_percentage", 50)
            self.preserve_line_breaks = settings.get(
                "preserve_line_breaks", self.preserve_line_breaks)
            # 始终关闭语音跟随（退出全屏即停止）
            self.voice_follow_enabled = False
            self.recognizer.stop()
            # 更新主窗口控件
            self.slider_font_size.setValue(self.font_size)
            self.btn_weight_bold.setChecked(self.font_bold)
            self.btn_weight_normal.setChecked(not self.font_bold)
            self.slider_wpl.setValue(self.words_per_line)
            self.slider_speed.setValue(self.scroll_speed)
            self.slider_pos.setValue(self.pos_percentage)
            self._update_voice_button_style()
        self._fullscreen = None
        self._refresh_preview()
        self.show()

    def _on_fullscreen_voice_toggle(self, checked: bool):
        """全屏中切换了语音跟随 → 同步主窗口状态"""
        self.voice_follow_enabled = checked
        self._update_voice_button_style()
        if checked:
            self.recognizer.set_reference_text(self.text_editor.toPlainText())
            self.recognizer.start()
        else:
            self.recognizer.stop()

    def _on_voice_toggle(self):
        """切换语音跟随 —— 自动进入全屏"""
        self.voice_follow_enabled = not self.voice_follow_enabled
        self._update_voice_button_style()
        if self.voice_follow_enabled:
            text = self.text_editor.toPlainText().strip()
            if not text:
                QMessageBox.information(self, "提示", "请先输入文本内容。")
                self.voice_follow_enabled = False
                self._update_voice_button_style()
                return
            self.recognizer.set_reference_text(text)
            self.recognizer.start()
            # 自动进入全屏
            self._on_start_fullscreen()
        else:
            self.recognizer.stop()

    # ---- 语音回调 ----

    def _on_recognizer_status(self, running: bool):
        if running:
            self.lbl_voice_status.setText("🎤 收音中...")
            self.lbl_voice_status.setStyleSheet("color: #E05A5A; font-size: 10px; background: transparent;")
        else:
            path = self.recognizer.model_path
            name = Path(path).name if path else "已加载"
            self.lbl_voice_status.setText(f"🎤 {name}")
            self.lbl_voice_status.setStyleSheet("color: #555; font-size: 10px; background: transparent;")

    def _on_recognizer_debug(self, info: str):
        """显示识别器调试信息"""
        current = self.lbl_voice_status.text()
        self.lbl_voice_status.setText(f"{current} | {info}")
        # 3秒后恢复
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self.lbl_voice_status.setText(current))

    def _on_recognizer_partial(self, text: str):
        """实时部分结果 → 全屏"""
        fs = getattr(self, '_fullscreen', None)
        if fs is not None:
            try:
                fs.set_recognition_active(True)
                fs.set_recognition_text(text)
                fs.on_recognized_text(text, is_final=False)
            except RuntimeError:
                pass

    def _on_recognizer_final(self, text: str):
        """最终结果 → 全屏"""
        fs = getattr(self, '_fullscreen', None)
        if fs is not None:
            try:
                fs.set_recognition_active(False)
                fs.set_recognition_text(text)
                fs.on_recognized_text(text, is_final=True)
            except RuntimeError:
                pass

    def _on_recognizer_error(self, error: str):
        QMessageBox.warning(self, "语音识别错误", error)
        self.voice_follow_enabled = False
        self._update_voice_button_style()

    def get_settings(self) -> dict:
        return {
            "font_size": self.font_size,
            "font_bold": self.font_bold,
            "words_per_line": self.words_per_line,
            "scroll_speed": self.scroll_speed,
            "pos_percentage": self.pos_percentage,
            "voice_follow_enabled": self.voice_follow_enabled,
            "preserve_line_breaks": self.preserve_line_breaks,
        }

    def closeEvent(self, event):
        config = load_config()
        config.update({
            "font_size": self.font_size,
            "font_bold": self.font_bold,
            "words_per_line": self.words_per_line,
            "scroll_speed": self.scroll_speed,
            "pos_percentage": self.pos_percentage,
            "voice_follow_enabled": False,
            "window_width": self.width(),
            "window_height": self.height(),
            "scripts_dir": str(self.scripts_dir),
            "preserve_line_breaks": self.preserve_line_breaks,
        })
        save_config(config)
        if config.get("auto_save", True):
            text = self.text_editor.toPlainText()
            save_last_text(text)
        self.recognizer.stop()
        super().closeEvent(event)
