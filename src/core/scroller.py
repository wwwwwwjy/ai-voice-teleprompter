"""
平滑滚动引擎
基于 QTimer 定时刷新，驱动全屏文字连续向上滚动。
"""

from PyQt6.QtCore import QTimer, QObject


class Scroller(QObject):
    """
    平滑滚动引擎。

    控制文字的垂直滚动偏移量，根据速度设置每秒移动一定像素。
    """

    # 速度等级 → 每秒像素移动量（使用公式，支持 1-30）
    @staticmethod
    def _pixels_per_second(speed: int) -> float:
        """速度 1=10px/s, 30=900px/s，曲线递增"""
        return 8.0 * (speed ** 1.35)  # 1→8, 5→52, 10→142, 20→373, 30→663

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._offset_y = 0.0          # 当前滚动偏移（像素）
        self._speed = 5               # 速度等级 1-30
        self._running = False
        self._fps = 60                # 刷新率

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self):
        """开始滚动"""
        if not self._running:
            self._running = True
            self._timer.start(1000 // self._fps)

    def stop(self):
        """停止滚动"""
        self._running = False
        self._timer.stop()

    def pause(self):
        """暂停滚动（保留偏移量）"""
        self._running = False
        self._timer.stop()

    def resume(self):
        """恢复滚动"""
        self.start()

    def reset(self):
        """重置滚动位置到起始"""
        self._offset_y = 0.0

    @property
    def offset_y(self) -> float:
        """当前垂直偏移量（像素）"""
        return self._offset_y

    @offset_y.setter
    def offset_y(self, value: float):
        self._offset_y = max(0.0, value)

    @property
    def speed(self) -> int:
        """速度等级 (1-30)"""
        return self._speed

    @speed.setter
    def speed(self, value: int):
        self._speed = max(1, min(30, value))

    @property
    def is_running(self) -> bool:
        return self._running

    def _tick(self):
        """每帧调用，更新偏移量"""
        if self._running:
            pixel_per_frame = self._pixels_per_second(self._speed) / self._fps
            self._offset_y += pixel_per_frame
