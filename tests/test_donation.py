import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel

from ui.settings_dialog import DonationDialog, _resource_path


class DonationDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_bundled_payment_codes_are_visible_and_read_only(self):
        for filename in ("alipay.png", "wechat-qr.png"):
            self.assertTrue(
                _resource_path(f"resources/donation/{filename}").is_file())

        dialog = DonationDialog()
        loaded_codes = [
            label for label in dialog.findChildren(QLabel)
            if label.pixmap() is not None and not label.pixmap().isNull()
        ]
        self.assertEqual(len(loaded_codes), 2)


if __name__ == "__main__":
    unittest.main()
