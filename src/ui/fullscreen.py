"""
全屏提词窗口
全屏显示文字，平滑滚动动画，逐字渐变高亮。
"""

from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QFontMetrics,
    QKeyEvent, QMouseEvent, QPaintEvent, QShowEvent, QResizeEvent, QWheelEvent
)
import time

from core.text_parser import parse_text
from core.scroller import Scroller
from core.prompter import PrompterState, CharState
from ui.controls import ControlsBar
from speech.follower import TextFollower
from utils.config import load_config


class FullscreenWindow(QMainWindow):
    """全屏提词窗口"""

    voice_follow_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("汪同学的AI语音提词器 — 全屏")

        self._raw_text = ""

        self.scroller = Scroller(self)
        self.state = PrompterState()
        cfg = load_config()
        self.follower = TextFollower(jump_threshold=cfg.get("jump_threshold", 5))

        self.font_size = 36
        self.font_bold = False
        self.words_per_line = 20
        self.scroll_speed = 5
        self.pos_percentage = 50
        self.voice_follow_enabled = False
        self.preserve_line_breaks = True
        self._paused = False

        self._line_height = 0
        self._base_y = 0
        self._max_text_width = 0
        self._last_recognized_text = ""
        self._last_voice_activity = 0.0
        self._last_voice_match = 0.0
        self._voice_assist_remainder = 0.0

        # 平滑滚动：目标偏移 + 定时器内插
        self._scroll_target = 0.0
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(16)  # ~60fps
        self._scroll_timer.timeout.connect(self._tick_scroll)

        self._voice_assist_timer = QTimer(self)
        self._voice_assist_timer.setInterval(100)
        self._voice_assist_timer.timeout.connect(self._tick_voice_assist)

        self._init_ui()
        self._create_controls()

    # ================================================================
    # UI 初始化
    # ================================================================

    def _init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #1A1A1A;")
        self.setMouseTracking(True)

    def _create_controls(self):
        self.controls = ControlsBar(self)
        self.controls.hide()
        self.controls.font_size_changed.connect(self._on_font_size_change)
        self.controls.bold_toggled.connect(self._on_bold_toggle)
        self.controls.words_per_line_changed.connect(self._on_wpl_change)
        self.controls.scroll_speed_changed.connect(self._on_speed_change)
        self.controls.pos_percentage_changed.connect(self._on_pos_change)
        self.controls.voice_follow_toggled.connect(self._on_voice_toggle)
        self.controls.exit_requested.connect(self.close)

    # ================================================================
    # 公共接口
    # ================================================================

    def load_settings(self, settings: dict):
        self.font_size = settings.get("font_size", 36)
        self.font_bold = settings.get("font_bold", False)
        self.words_per_line = settings.get("words_per_line", 20)
        self.scroll_speed = settings.get("scroll_speed", 5)
        self.pos_percentage = settings.get("pos_percentage", 50)
        self.voice_follow_enabled = settings.get("voice_follow_enabled", False)
        self.preserve_line_breaks = settings.get("preserve_line_breaks", True)
        self.controls.set_values(
            self.font_size, self.font_bold, self.words_per_line,
            self.scroll_speed, self.voice_follow_enabled,
            self.pos_percentage)

    def load_text(self, text: str):
        self._raw_text = text
        self.scroller.speed = self.scroll_speed
        self._calc_max_text_width()
        self._reparse_and_render()
        if self.voice_follow_enabled:
            self.scroller.pause()
            self._start_voice_assist()
        else:
            self.scroller.start()
        self._start_render_timer()
        self._start_timecode()
        self._position_controls()

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

    # ================================================================
    # 文字排版
    # ================================================================

    def _calc_max_text_width(self):
        screen_w = self.width()
        usable_w = max(200, screen_w - 40)
        width_ratio = 0.30 + (self.words_per_line / 100) * 0.68
        self._max_text_width = min(int(usable_w * width_ratio), usable_w)

    @property
    def is_width_capped(self) -> bool:
        return getattr(self, '_width_capped', False)

    def _reparse_and_render(self):
        if not self._raw_text:
            return
        font = QFont("PingFang SC", self.font_size)
        if self.font_bold:
            font.setBold(True)
        fm = QFontMetrics(font)
        self._calc_max_text_width()
        lines = parse_text(
            self._raw_text, self._max_text_width, fm,
            preserve_line_breaks=self.preserve_line_breaks)
        self.state.load_text(self._raw_text, lines)
        self.follower.load_document(lines)
        self.scroller.reset()
        self._scroll_target = 0.0
        self._voice_assist_remainder = 0.0
        if lines:
            self.state.char_states[0] = CharState.READING
        self._recalc_layout()

    def _recalc_layout(self):
        self._line_height = int(self.font_size * 1.6)
        self._base_y = int(self.height() * self.pos_percentage / 100)

    def _position_controls(self):
        bar_h = 54
        self.controls.setGeometry(0, self.height() - bar_h, self.width(), bar_h)
        self.controls.raise_()

    # ================================================================
    # 定时器
    # ================================================================

    def _start_render_timer(self):
        if not hasattr(self, '_render_timer'):
            self._render_timer = QTimer(self)
            self._render_timer.timeout.connect(self.update)
        self._render_timer.start(16)

    def _start_timecode(self):
        self._elapsed_seconds = 0
        if not hasattr(self, '_timecode_timer'):
            self._timecode_timer = QTimer(self)
            self._timecode_timer.timeout.connect(self._tick_timecode)
        self._timecode_timer.start(1000)

    def _tick_timecode(self):
        self._elapsed_seconds += 1
        self.update()

    # ================================================================
    # 平滑滚动（定时器内插，线程安全）
    # ================================================================

    def _scroll_to_line(self, line_idx: int):
        """设置滚动目标，由定时器平滑内插。"""
        if self._line_height <= 0 or self.height() <= 0:
            return
        line_idx = max(0, min(line_idx, max(0, len(self.state.lines) - 1)))
        raw = line_idx * self._line_height
        target = max(0.0, raw - (self.height() * self.pos_percentage / 100))
        self._scroll_target = target
        if not self._scroll_timer.isActive():
            self._scroll_timer.start()

    def _tick_scroll(self):
        """每帧内插滚动偏移，逼近目标。"""
        current = self.scroller.offset_y
        target = self._scroll_target
        diff = target - current

        if abs(diff) < 0.5:
            self.scroller.offset_y = target
            self._scroll_timer.stop()
        else:
            # ease: 每帧移动 8% 的距离
            step = diff * 0.08
            if abs(step) < 0.5:
                step = 0.5 if diff > 0 else -0.5
            self.scroller.offset_y = current + step

        self.update()

    # ================================================================
    # 语音跟随
    # ================================================================

    def on_recognized_text(self, text: str, is_final: bool = False):
        """主线程接收识别结果，线程安全。"""
        if not self.voice_follow_enabled or not text:
            return

        self._last_voice_activity = time.monotonic()
        try:
            result = self.follower.feed_text(text, is_final=is_final)
        except Exception:
            return

        if result is None:
            return

        self._last_voice_match = time.monotonic()
        self._voice_assist_remainder = 0.0
        line_idx = max(0, min(result["line_idx"], max(0, len(self.state.lines) - 1)))
        char_idx = max(0, result["char_idx"])
        self.state.set_current_position(line_idx, char_idx)
        self._scroll_to_line(line_idx)
        self.update()

    def _start_voice_assist(self):
        self._last_voice_activity = 0.0
        self._last_voice_match = time.monotonic()
        self._voice_assist_remainder = 0.0
        if not self._voice_assist_timer.isActive():
            self._voice_assist_timer.start()

    def _stop_voice_assist(self):
        self._voice_assist_timer.stop()
        self._voice_assist_remainder = 0.0

    def _tick_voice_assist(self):
        if not self.voice_follow_enabled or self._paused or not self.state.lines:
            return

        now = time.monotonic()
        if self._last_voice_activity <= 0:
            return

        # 识别刚命中后不预测，避免和真实匹配来回拉扯。
        if now - self._last_voice_match < 0.35:
            return

        # 超过一段时间没有任何识别活动，认为用户停顿。
        if now - self._last_voice_activity > 1.2:
            return

        chars_per_second = 2.6 + self.scroll_speed * 0.28
        self._voice_assist_remainder += chars_per_second * (self._voice_assist_timer.interval() / 1000.0)
        step = int(self._voice_assist_remainder)
        if step <= 0:
            return
        self._voice_assist_remainder -= step

        line_idx, char_idx = self.follower.advance_by_chars(step)
        line_idx = max(0, min(line_idx, max(0, len(self.state.lines) - 1)))
        self.state.set_current_position(line_idx, char_idx)
        self._scroll_to_line(line_idx)
        self.update()

    def set_recognition_active(self, active: bool):
        if hasattr(self, 'controls'):
            self.controls.set_recognition_active(active)

    def set_recognition_text(self, text: str):
        self._last_recognized_text = text
        if hasattr(self, 'controls'):
            self.controls.set_recognition_text(text)

    # ================================================================
    # 事件
    # ================================================================

    def showEvent(self, event):
        self._calc_max_text_width()
        self._recalc_layout()
        self._position_controls()
        self.controls.set_width_capped(self.is_width_capped)
        self._reparse_and_render()
        super().showEvent(event)

    def resizeEvent(self, event):
        self._calc_max_text_width()
        self._recalc_layout()
        self._position_controls()
        if self._raw_text:
            self._reparse_and_render()
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        if event is None:
            return
        k = event.key()
        if k == Qt.Key.Key_Escape:
            self.close()
        elif k == Qt.Key.Key_Space:
            self._toggle_pause()
        elif k == Qt.Key.Key_Up:
            self._manual_scroll(-1)
        elif k == Qt.Key.Key_Down:
            self._manual_scroll(1)
        else:
            super().keyPressEvent(event)

    def _toggle_pause(self):
        self._paused = not self._paused
        if self._paused:
            self.scroller.pause()
            if hasattr(self, '_timecode_timer'):
                self._timecode_timer.stop()
        else:
            if not self.voice_follow_enabled:
                self.scroller.resume()
            if hasattr(self, '_timecode_timer'):
                self._timecode_timer.start(1000)
        self.update()

    def _manual_scroll(self, direction: int):
        self._scroll_by_pixels(direction * self._line_height * 0.5)

    def _maximum_scroll_offset(self) -> float:
        """最后一行位于提词位置时的最大可定位偏移。"""
        if not self.state.lines or self._line_height <= 0:
            return 0.0
        return float((len(self.state.lines) - 1) * self._line_height)

    def _scroll_by_pixels(self, delta: float):
        """用于键盘及触控板的即时定位滚动。"""
        target = min(
            self._maximum_scroll_offset(),
            max(0.0, self.scroller.offset_y + delta),
        )
        self._scroll_target = target
        self.scroller.offset_y = target
        self._sync_position_to_scroll()
        self.update()

    def _sync_position_to_scroll(self):
        """手动定位后同步高亮/语音跟随的当前位置。"""
        if not self.state.lines or self._line_height <= 0:
            return
        # 绘制公式为 base_y + line * line_height - offset，故 offset=0
        # 对应第一行，offset 每增加一行高即定位到下一行。
        line_idx = int(self.scroller.offset_y / self._line_height)
        line_idx = max(0, min(line_idx, len(self.state.lines) - 1))
        self.state.set_current_position(line_idx, 0)
        if self.voice_follow_enabled:
            self.follower.set_position(line_idx, 0)

    def wheelEvent(self, event: QWheelEvent):
        """支持 macOS 触控板双指上下滑动，快速定位台词。"""
        if event is None:
            return
        pixel_delta = event.pixelDelta().y()
        angle_delta = event.angleDelta().y()
        # macOS 触控板提供 pixelDelta；普通鼠标回退到 angleDelta。
        delta = -pixel_delta if pixel_delta else -(angle_delta / 120.0 * self._line_height * 0.7)
        if delta:
            self._scroll_by_pixels(delta)
            event.accept()
            return
        super().wheelEvent(event)
        self.update()

    def mouseMoveEvent(self, event):
        if event is None:
            return
        if self.height() - event.pos().y() < 120:
            self.controls.show_at_bottom()
        else:
            self.controls.start_hide_timer()
        super().mouseMoveEvent(event)

    # ================================================================
    # 控制条回调
    # ================================================================

    def _on_font_size_change(self, v): self.font_size = v; self._reparse_and_render()
    def _on_bold_toggle(self, v): self.font_bold = v; self._reparse_and_render()
    def _on_wpl_change(self, v):
        self.words_per_line = v; self._reparse_and_render()
        if self.is_width_capped:
            self.controls.set_width_capped(True)
            self.controls.show_max_width_toast()
        else:
            self.controls.set_width_capped(False)
    def _on_speed_change(self, v): self.scroll_speed = v; self.scroller.speed = v
    def _on_pos_change(self, v): self.pos_percentage = v; self._recalc_layout()

    def _on_voice_toggle(self, checked):
        self.voice_follow_enabled = checked
        if checked:
            self.scroller.pause()
            self._start_voice_assist()
        else:
            self._stop_voice_assist()
            self.scroller.resume()
        self.voice_follow_changed.emit(checked)

    # ================================================================
    # 绘制
    # ================================================================

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        self._draw_text(painter)
        self._draw_footer(painter)
        painter.end()

    def _draw_text(self, painter: QPainter):
        lines = self.state.lines
        if not lines:
            self._draw_placeholder(painter)
            return

        font = QFont("PingFang SC", self.font_size)
        if self.font_bold:
            font.setBold(True)
        painter.setFont(font)
        fm = QFontMetrics(font)

        w, h = self.width(), self.height()
        lh = self._line_height
        oy = self.scroller.offset_y
        mx = (w - self._max_text_width) // 2
        footer_h = 70
        voice_mode = self.voice_follow_enabled and self.follower

        # 当前行
        if voice_mode:
            cl, cc = self.follower.get_current_position()
            self.state.set_current_position(cl, cc)
        else:
            cl = int(oy / lh) if lh > 0 else 0
        cl = max(0, min(cl, len(lines) - 1))

        # 当前全局字符索引（带边界保护）
        cg = 0
        max_li = min(cl, len(lines))
        for li in range(max_li):
            cg += len(lines[li]) if li < len(lines) else 0
        cg += min(self.state.current_char_in_line,
                  len(lines[cl]) if cl < len(lines) else 0)

        for i, line in enumerate(lines):
            ly = self._base_y + i * lh - oy
            if ly + lh < -lh:
                continue
            if ly > h - footer_h:
                break

            try:
                tw = fm.horizontalAdvance(line)
            except Exception:
                tw = 100
            x = mx + (self._max_text_width - tw) // 2

            if not voice_mode:
                painter.setPen(QPen(QColor(255, 255, 255)))
                painter.setOpacity(1.0)
                painter.drawText(int(x), int(ly + lh - fm.descent()),
                                 line)
                continue

            # 语音跟随：当前行逐字，其余行整体
            if i == cl:
                self._draw_line_chars(painter, fm, line, i, x, ly, lh, cg)
            else:
                dist_lines = abs(i - cl)
                alpha = max(0.2, 1.0 - dist_lines * 0.3)
                if i < cl:
                    g = int(120 + 80 * (1 - min(dist_lines, 3) / 3))
                    color = QColor(g, g, g, int(255 * alpha))
                else:
                    v = int(200 + 55 * (1 - min(dist_lines, 3) / 3))
                    color = QColor(v, v, v, int(255 * alpha))

                painter.setPen(QPen(color))
                painter.setOpacity(1.0)
                painter.drawText(int(x), int(ly + lh - fm.descent()), line)

        painter.setOpacity(1.0)

    def _draw_line_chars(self, painter, fm, line, line_idx, x, ly, lh, cg):
        """逐字绘制当前行，带渐变。线程安全，边界保护。"""
        if not line:
            return

        # 该行起始全局偏移
        char_off = 0
        for j in range(min(line_idx, len(self.state.lines))):
            char_off += len(self.state.lines[j])

        cursor = float(x)
        for ci, ch in enumerate(line):
            gpos = char_off + ci
            dist = gpos - cg

            try:
                cw = fm.horizontalAdvance(ch)
                if cw <= 0:
                    cw = fm.averageCharWidth()
            except Exception:
                cw = 10

            if dist < 0:
                fade = min(abs(dist) / 25.0, 1.0)
                g = int(120 + 135 * (1 - fade))
                alpha = max(0.15, 1.0 - fade * 0.85)
                color = QColor(g, g, g, int(255 * alpha))
            elif dist == 0:
                color = QColor(255, 255, 255, 255)
            else:
                d = min(dist / 25.0, 1.0)
                v = int(200 + 55 * (1 - d))
                color = QColor(v, v, v, 255)

            painter.setPen(QPen(color))
            painter.setOpacity(1.0)
            try:
                painter.drawText(int(cursor), int(ly + lh - fm.descent()), ch)
            except Exception:
                pass
            cursor += cw

    def _draw_footer(self, painter: QPainter):
        w, h = self.width(), self.height()
        fy = h - 56

        # 进度条
        bx, bw, bh = int(w * 0.06), int(w * 0.25), 3
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(50, 50, 50))
        painter.drawRoundedRect(bx, fy, bw, bh, 1, 1)
        try:
            progress = self.state.get_read_progress()
        except Exception:
            progress = 0.0
        fw = int(bw * progress)
        if fw > 0:
            painter.setBrush(QColor(240, 200, 40))
            painter.drawRoundedRect(bx, fy, fw, bh, 1, 1)

        # 识别文字
        fs = QFont("PingFang SC", 11)
        painter.setFont(fs)
        painter.setPen(QPen(QColor(150, 150, 150)))
        rt = getattr(self, '_last_recognized_text', '') or ''
        painter.drawText(0, fy + 14, w, 16, Qt.AlignmentFlag.AlignHCenter, rt)

        # 时间码
        ft = QFont("PingFang SC", 12)
        painter.setFont(ft)
        painter.setPen(QPen(QColor(180, 180, 180)))
        el = getattr(self, '_elapsed_seconds', 0)
        ts = f"{el // 60:02d}:{el % 60:02d}"
        painter.drawText(w - 120, 24, 100, 20, Qt.AlignmentFlag.AlignRight, ts)

    def _draw_placeholder(self, painter: QPainter):
        painter.setFont(QFont("PingFang SC", 24))
        painter.setPen(QPen(QColor(120, 120, 120)))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                         "请先在主面板粘贴文本")

    # ================================================================
    # 关闭
    # ================================================================

    def closeEvent(self, event):
        self.scroller.stop()
        self._scroll_timer.stop()
        self._stop_voice_assist()
        if hasattr(self, '_render_timer'):
            self._render_timer.stop()
        if hasattr(self, '_timecode_timer'):
            self._timecode_timer.stop()
        super().closeEvent(event)
