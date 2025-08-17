from __future__ import annotations
from PySide6.QtCore import QObject, Signal


class NotificationCenter(QObject):
    notification_requested = Signal(str, str, int)  # level, text, ms

    def info(self, text: str, ms: int = 3000) -> None:
        self.notification_requested.emit("info", text, ms)

    def success(self, text: str, ms: int = 3000) -> None:
        self.notification_requested.emit("success", text, ms)

    def warn(self, text: str, ms: int = 3500) -> None:
        self.notification_requested.emit("warn", text, ms)

    def error(self, text: str, ms: int = 5000) -> None:
        self.notification_requested.emit("error", text, ms)


notification_center = NotificationCenter()
