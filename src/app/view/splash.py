from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QLinearGradient, QBrush, QColor, QPainter, QFont
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect


class SplashScreen(QWidget):
    """
    Minimaler Splash:
    - Frameless, abgerundet, dunkler Hintergrund
    - Großes Logo (PNG/SVG/ICO), smooth skaliert
    - Dezenter Titel in Grau
    """
    def __init__(self, image_path: Path, title: str = "VideoSubTool", parent=None) -> None:
        # WICHTIG: flags als 2. Parameter, nicht als Keyword!
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # ----- Schatten / Card -----
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(12)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

        # ----- Logo -----
        self.logo_lbl = QLabel(alignment=Qt.AlignCenter)
        self.logo_lbl.setAttribute(Qt.WA_TranslucentBackground)
        pm = QPixmap(str(image_path)) if image_path.exists() else QPixmap()
        if not pm.isNull():
            pm = pm.scaledToWidth(220, Qt.SmoothTransformation)
        self.logo_lbl.setPixmap(pm)

        # ----- Titel -----
        self.title_lbl = QLabel(title, alignment=Qt.AlignCenter)
        f = QFont()
        f.setPointSize(12); f.setBold(True)
        self.title_lbl.setFont(f)
        self.title_lbl.setStyleSheet("color: #C9D1D9;")

        # ----- Layout -----
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 22, 22, 22)
        lay.setSpacing(10)
        lay.addWidget(self.logo_lbl)
        lay.addWidget(self.title_lbl)

        self.resize(380, 300)

    def center_on_screen(self) -> None:
        geo = self.frameGeometry()
        scr = self.screen().availableGeometry() if self.screen() else None
        if scr:
            geo.moveCenter(scr.center())
            self.move(geo.topLeft())

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0.0, QColor("#0f1722"))
        g.setColorAt(1.0, QColor("#0b111a"))
        p.setBrush(QBrush(g))
        p.setPen(QColor(47, 47, 51))
        rect = self.rect().adjusted(1, 1, -1, -1)
        p.drawRoundedRect(rect, 16, 16)
        p.end()
