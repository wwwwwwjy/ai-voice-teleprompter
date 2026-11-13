"""
文本预览组件 — 等比缩放全屏效果，预览即所得。
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QFontMetrics, QPaintEvent
)

from core.text_parser import parse_text

# 参考屏幕宽度（用于等比缩放）
REF_SCREEN_W = 1440


class TextPreview(QWidget):
    """主页实时预览，与全屏效果完全一致（等比缩放）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self._raw_text = ""
        self._lines: list[str] = []
        self._font_size = 36
        self._font_bold = False
        self._words_per_line = 20
        self._preserve_line_breaks = True
        self._max_width = 0
        self._scaled_font_size = 12
        self._scale = 0.3

    def update_preview(self, text: str, font_size: int, bold: bool,
                       words_per_line: int, preserve_line_breaks: bool = True):
        self._raw_text = text
        self._font_size = font_size
        self._font_bold = bold
        self._words_per_line = words_per_line
        self._preserve_line_breaks = preserve_line_breaks
        self._reparse()
        self.update()

    def _reparse(self):
        if not self._raw_text:
            self._lines = []
            return

        # 计算边界框内可用宽度
        margin = 8
        inner_margin = 12
        box_w = self.width() - 2 * margin
        inner_w = box_w - 2 * inner_margin
        if inner_w < 100:
            inner_w = 200

        # 等比缩放：预览框 ≈ 屏幕的缩小版
        self._scale = max(inner_w / REF_SCREEN_W, 0.15)
        self._scaled_font_size = max(int(self._font_size * self._scale), 8)

        # 用缩放后的字号创建字体测量
        font = QFont("PingFang SC", self._scaled_font_size)
        if self._font_bold:
            font.setBold(True)
        fm = QFontMetrics(font)

        # 和全屏完全相同的宽度比例公式
        width_ratio = 0.30 + (self._words_per_line / 100) * 0.68
        calculated = int(inner_w * width_ratio)
        self._max_width = min(calculated, inner_w)

        # 用缩放字号 + 等比宽度排版 → 换行结果与全屏一致
        self._lines = parse_text(
            self._raw_text, self._max_width, fm,
            preserve_line_breaks=self._preserve_line_breaks)

    def paintEvent(self, event: QPaintEvent | None):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        w = self.width()
        h = self.height()
        if w < 60 or h < 60:
            painter.end()
            return

        # 白色圆角边界框
        margin = 8
        box_x, box_y = margin, margin
        box_w, box_h = w - 2 * margin, h - 2 * margin

        pen = QPen(QColor(120, 120, 120), 2)
        painter.setPen(pen)
        painter.setBrush(QColor(26, 26, 26))
        painter.drawRoundedRect(box_x, box_y, box_w, box_h, 12, 12)

        if not self._lines:
            painter.setPen(QPen(QColor(100, 100, 100)))
            font = QFont("PingFang SC", 11)
            painter.setFont(font)
            painter.drawText(box_x, box_y, box_w, box_h,
                             Qt.AlignmentFlag.AlignCenter,
                             "实时预览")
            painter.end()
            return

        # 用缩放字号绘制
        font = QFont("PingFang SC", self._scaled_font_size)
        if self._font_bold:
            font.setBold(True)
        painter.setFont(font)

        line_h = max(int(self._scaled_font_size * 1.5), 8)
        inner_margin = 12
        inner_x = box_x + inner_margin
        inner_w = box_w - 2 * inner_margin
        inner_y = box_y + inner_margin
        inner_h = box_h - 2 * inner_margin

        text_start_x = inner_x + (inner_w - self._max_width) // 2
        max_lines = max(1, inner_h // line_h)

        painter.setPen(QPen(QColor(255, 255, 255)))
        for i in range(min(len(self._lines), max_lines)):
            line = self._lines[i]
            y = inner_y + i * line_h
            painter.drawText(text_start_x, y + line_h - 4, line)

        if len(self._lines) > max_lines:
            painter.setPen(QPen(QColor(120, 120, 120)))
            painter.setFont(QFont("PingFang SC", 9))
            painter.drawText(
                inner_x, inner_y, inner_w, inner_h,
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
                f"共 {len(self._lines)} 行")

        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reparse()
