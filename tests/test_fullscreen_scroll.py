import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.fullscreen import FullscreenWindow


class FullscreenScrollTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_manual_pixel_scroll_clamps_and_syncs_current_line(self):
        window = FullscreenWindow()
        window.resize(1200, 800)
        window.load_settings({"font_size": 32, "pos_percentage": 50})
        window.load_text("\n".join(f"第 {i} 行" for i in range(80)))

        window._scroll_by_pixels(100000)
        self.assertEqual(window.scroller.offset_y, window._maximum_scroll_offset())
        self.assertGreater(window.state.current_line, 0)

        window._scroll_by_pixels(-100000)
        self.assertEqual(window.scroller.offset_y, 0.0)
        self.assertEqual(window.state.current_line, 0)
        window.close()
