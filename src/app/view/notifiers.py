from __future__ import annotations
from typing import Protocol

from PySide6.QtWidgets import QMainWindow, QMessageBox


class INotifier(Protocol):
    def notify(self, level: str, text: str, ms: int) -> None:
        ...


class StatusBarNotifier:
    def __init__(self, window: QMainWindow):
        self.window = window

    def notify(self, level: str, text: str, ms: int) -> None:  # noqa: D401
        sb = self.window.statusBar()
        if sb:
            sb.showMessage(text, ms)


class DialogNotifier:
    def __init__(self, window: QMainWindow):
        self.window = window

    def notify(self, level: str, text: str, ms: int) -> None:  # noqa: D401
        if level == "error":
            QMessageBox.critical(self.window, self.window.windowTitle(), text, QMessageBox.Ok)
        elif level == "warn":
            QMessageBox.warning(self.window, self.window.windowTitle(), text, QMessageBox.Ok)
        else:
            QMessageBox.information(self.window, self.window.windowTitle(), text, QMessageBox.Ok)


class ToastNotifier:
    def __init__(self, window: QMainWindow, toast_overlay):
        self.window = window
        self.toast_overlay = toast_overlay

    def notify(self, level: str, text: str, ms: int) -> None:  # noqa: D401
        self.toast_overlay.show_toast(level, text, ms)
