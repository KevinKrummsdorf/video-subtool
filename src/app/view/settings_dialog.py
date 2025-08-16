from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QCheckBox, QDialogButtonBox, QWidget, QComboBox
)

from app.settings import get_settings
from app import i18n
from app.i18n import t

class SettingsDialog(QDialog):
    """Einstellungsdialog (Sprache, Bundled/Paths)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = get_settings()

        self.setModal(True)
        self._build_ui()
        self._retranslate()
        i18n.bus.language_changed.connect(self._retranslate)

    def _build_ui(self):
        self.chk_use_bundled = QCheckBox()
        self.chk_use_bundled.setChecked(bool(self.settings.value("use_bundled", False, type=bool)))

        self.ed_ffmpeg = QLineEdit(self.settings.value("path_ffmpeg", "", type=str) or "")
        self.btn_ffmpeg = QPushButton("…")
        self.btn_ffmpeg.clicked.connect(lambda: self._pick_file(self.ed_ffmpeg))

        self.ed_ffprobe = QLineEdit(self.settings.value("path_ffprobe", "", type=str) or "")
        self.btn_ffprobe = QPushButton("…")
        self.btn_ffprobe.clicked.connect(lambda: self._pick_file(self.ed_ffprobe))

        self.cbo_lang = QComboBox()
        self.cbo_lang.addItem("Deutsch", "de")
        self.cbo_lang.addItem("English", "en")
        curr = i18n.current_language()
        idx = self.cbo_lang.findData(curr)
        if idx >= 0:
            self.cbo_lang.setCurrentIndex(idx)

        def row(label: QLabel, editor: QWidget, btn: QPushButton | None = None) -> QWidget:
            w = QWidget()
            h = QHBoxLayout(w); h.setContentsMargins(0,0,0,0)
            h.addWidget(label); h.addWidget(editor, 1)
            if btn: h.addWidget(btn)
            return w

        self.lbl_bundled = QLabel()
        self.lbl_ffmpeg = QLabel()
        self.lbl_ffprobe = QLabel()
        self.lbl_lang = QLabel()

        v = QVBoxLayout(self)
        v.addWidget(self.lbl_bundled)
        v.addSpacing(8)
        v.addWidget(row(self.lbl_ffmpeg, self.ed_ffmpeg, self.btn_ffmpeg))
        v.addWidget(row(self.lbl_ffprobe, self.ed_ffprobe, self.btn_ffprobe))
        v.addSpacing(12)
        v.addWidget(row(self.lbl_lang, self.cbo_lang, None))
        v.addStretch(1)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)
        self._btns = btns

    def _retranslate(self, *_):
        self.setWindowTitle(t("sd.title"))
        self.lbl_bundled.setText(t("sd.use.bundled"))
        self.lbl_ffmpeg.setText(t("sd.ffmpeg.path"))
        self.lbl_ffprobe.setText(t("sd.ffprobe.path"))
        self.lbl_lang.setText(t("sd.lang"))

    def _pick_file(self, line: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, t("sd.pick.file"))
        if path:
            line.setText(path)

    def _save(self):
        def valid_path(s: str) -> str:
            p = Path(s) if s else None
            return str(p) if p and p.exists() else ""

        self.settings.setValue("use_bundled", bool(self.chk_use_bundled.isChecked()))
        self.settings.setValue("path_ffmpeg", valid_path(self.ed_ffmpeg.text().strip()))
        self.settings.setValue("path_ffprobe", valid_path(self.ed_ffprobe.text().strip()))

        lang = self.cbo_lang.currentData()
        from app.i18n import set_language
        set_language(lang)

        self.accept()
