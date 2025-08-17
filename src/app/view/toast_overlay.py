from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ToastOverlay(QWidget):
    """Very small toast overlay widget."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.label = QLabel(self)
        lay = QVBoxLayout(self)
        lay.addWidget(self.label)

    def show_toast(self, level: str, text: str, ms: int) -> None:
        self.label.setText(text)
        self.adjustSize()
        self.show()
        QTimer.singleShot(ms, self.hide)
