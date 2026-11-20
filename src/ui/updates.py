"""Run update work in the background and present results on the Qt thread."""

from queue import Empty, SimpleQueue
from threading import Thread

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox

from utils.updater import check_latest_release, launch_installer, stage_update
from version import APP_VERSION


class UpdateController(QObject):
    status_changed = pyqtSignal(str, bool)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.status = f"当前版本：v{APP_VERSION}"
        self.busy = False
        self.dialog = None
        self.results = SimpleQueue()
        self.timer = QTimer(self, interval=100)
        self.timer.timeout.connect(self._poll)

    def _status(self, text, busy=False):
        self.status, self.busy = text, busy
        self.status_changed.emit(text, busy)

    def check(self, dialog=None):
        if self.busy:
            return
        self.dialog = dialog
        self._start("正在检查 GitHub 更新…", check_latest_release, self._checked)

    def _start(self, status, operation, callback):
        self._status(status, True)
        self.callback = callback
        results = self.results

        def work():
            try:
                results.put((operation(), None))
            except Exception as error:
                results.put((None, str(error)))

        Thread(target=work, daemon=True).start()
        self.timer.start()

    def _poll(self):
        try:
            result, error = self.results.get_nowait()
        except Empty:
            return
        self.timer.stop()
        self.callback(result, error)

    def _parent(self):
        return self.dialog if self.dialog is not None and self.dialog.isVisible() else self.window

    def _checked(self, release, error):
        if error:
            self._status(f"检查更新失败：{error}")
            return
        if release is None:
            self._status(f"当前已是最新版本 v{APP_VERSION}")
            return
        version, notes, asset = release
        self._status(f"发现新版本 v{version}", True)
        prompt = QMessageBox(self._parent())
        prompt.setWindowTitle("软件更新")
        prompt.setTextFormat(Qt.TextFormat.PlainText)
        prompt.setText(f"发现 v{version}，是否下载并重启更新？")
        prompt.setInformativeText(notes[:1800])
        install = prompt.addButton("下载并更新", QMessageBox.ButtonRole.AcceptRole)
        later = prompt.addButton("稍后", QMessageBox.ButtonRole.RejectRole)
        prompt.setDefaultButton(later)
        prompt.exec()
        if prompt.clickedButton() == install:
            self._start("正在下载并校验更新…", lambda: stage_update(asset), self._staged)
        else:
            self._status(f"发现新版本 v{version}")

    def _staged(self, staged, error):
        if error is None:
            try:
                launch_installer(staged)
            except (OSError, KeyError) as failure:
                staged[0].cleanup()
                error = str(failure)
        if error:
            self._status("更新失败")
            QMessageBox.warning(self._parent(), "更新失败", error)
            return
        if self.dialog is not None:
            self.dialog.reject()
        self.window.close()
        QApplication.quit()
