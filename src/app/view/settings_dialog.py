# src/app/view/settings_dialog.py
from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QCheckBox, QComboBox, QDialogButtonBox, QWidget, QSizePolicy,
    QGroupBox, QRadioButton
)

from app.settings import get_settings, notify_style_default, set_notify_style
from app import i18n
from app.i18n import t, available_languages, current_language, set_language


class SettingsDialog(QDialog):
    notify_style_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setModal(True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self.s = get_settings()

        # --- Widgets --------------------------------------------------------
        self.chk_use_bundled = QCheckBox(self)

        self.le_ffmpeg = QLineEdit(self)
        self.btn_ffmpeg = QPushButton("…", self)
        self.btn_ffmpeg.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_ffmpeg.clicked.connect(self._pick_ffmpeg)

        self.le_ffprobe = QLineEdit(self)
        self.btn_ffprobe = QPushButton("…", self)
        self.btn_ffprobe.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_ffprobe.clicked.connect(self._pick_ffprobe)

        self.cmb_lang = QComboBox(self)
        for code, label in available_languages().items():
            self.cmb_lang.addItem(label, code)
        # aktuelle Sprache setzen
        idx = self.cmb_lang.findData(current_language())
        if idx >= 0:
            self.cmb_lang.setCurrentIndex(idx)

        # Notification style
        self.grp_notify = QGroupBox(self)
        self.rb_status = QRadioButton(self.grp_notify)
        self.rb_dialog = QRadioButton(self.grp_notify)
        self.rb_toast = QRadioButton(self.grp_notify)
        v_notify = QVBoxLayout(self.grp_notify)
        v_notify.addWidget(self.rb_status)
        v_notify.addWidget(self.rb_dialog)
        v_notify.addWidget(self.rb_toast)

        # Buttons (wir setzen die Beschriftung selbst, damit es übersetzt ist)
        self.btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        self.btns.accepted.connect(self._save)
        self.btns.rejected.connect(self.reject)

        # --- Layout ---------------------------------------------------------
        lay = QVBoxLayout(self)

        lay.addWidget(self.chk_use_bundled)

        # ffmpeg row
        row_ffmpeg = QHBoxLayout()
        self.lbl_ffmpeg = QLabel(self)
        row_ffmpeg.addWidget(self.lbl_ffmpeg)
        row_ffmpeg.addWidget(self.le_ffmpeg, 1)
        row_ffmpeg.addWidget(self.btn_ffmpeg)
        lay.addLayout(row_ffmpeg)

        # ffprobe row
        row_ffprobe = QHBoxLayout()
        self.lbl_ffprobe = QLabel(self)
        row_ffprobe.addWidget(self.lbl_ffprobe)
        row_ffprobe.addWidget(self.le_ffprobe, 1)
        row_ffprobe.addWidget(self.btn_ffprobe)
        lay.addLayout(row_ffprobe)

        # language row
        row_lang = QHBoxLayout()
        self.lbl_lang = QLabel(self)
        row_lang.addWidget(self.lbl_lang)
        row_lang.addWidget(self.cmb_lang, 1)
        lay.addLayout(row_lang)

        lay.addWidget(self.grp_notify)
        lay.addWidget(self.btns)

        # --- Werte laden ----------------------------------------------------
        self._load_from_settings()

        # --- Signals --------------------------------------------------------
        self.chk_use_bundled.stateChanged.connect(self._update_enabled)
        self.cmb_lang.currentIndexChanged.connect(self._on_lang_changed)
        i18n.bus.language_changed.connect(self._retranslate)

        # Initiale Texte + Enable-State
        self._retranslate()
        self._update_enabled()

    # ---------------------- UI Helfer ---------------------------------------
    def _retranslate(self, *_):
        self.setWindowTitle(t("sd.title"))
        self.chk_use_bundled.setText(t("sd.use.bundled"))
        self.lbl_ffmpeg.setText(t("sd.ffmpeg.path"))
        self.lbl_ffprobe.setText(t("sd.ffprobe.path"))
        self.lbl_lang.setText(t("sd.lang"))

        self.grp_notify.setTitle(t("sd.notify.title"))
        self.rb_status.setText(t("sd.notify.statusbar"))
        self.rb_dialog.setText(t("sd.notify.dialog"))
        self.rb_toast.setText(t("sd.notify.toast"))

        # Button-Beschriftungen explizit setzen, damit sie zu DE/EN passen
        b_save = self.btns.button(QDialogButtonBox.Save)
        b_cancel = self.btns.button(QDialogButtonBox.Cancel)
        if b_save:
            b_save.setText(t("common.save"))
        if b_cancel:
            b_cancel.setText(t("common.cancel"))

    def _update_enabled(self):
        # Custom-Pfade nur bearbeitbar, wenn NICHT „bundled bevorzugen“
        enabled = not self.chk_use_bundled.isChecked()
        for w in (self.le_ffmpeg, self.btn_ffmpeg, self.le_ffprobe, self.btn_ffprobe):
            w.setEnabled(enabled)

    def _load_from_settings(self):
        use_bundled = bool(self.s.value("use_bundled", False, type=bool))
        self.chk_use_bundled.setChecked(use_bundled)

        self.le_ffmpeg.setText(self.s.value("path_ffmpeg", "", type=str) or "")
        self.le_ffprobe.setText(self.s.value("path_ffprobe", "", type=str) or "")

        cur = notify_style_default()
        if cur == "statusbar":
            self.rb_status.setChecked(True)
        elif cur == "dialog":
            self.rb_dialog.setChecked(True)
        else:
            self.rb_toast.setChecked(True)

    # ---------------------- Aktionen ----------------------------------------
    def _pick_ffmpeg(self):
        fn, _ = QFileDialog.getOpenFileName(self, t("sd.pick.file"))
        if fn:
            self.le_ffmpeg.setText(fn)

    def _pick_ffprobe(self):
        fn, _ = QFileDialog.getOpenFileName(self, t("sd.pick.file"))
        if fn:
            self.le_ffprobe.setText(fn)

    def _on_lang_changed(self):
        code = self.cmb_lang.currentData()
        if code and code != current_language():
            set_language(code)  # triggert _retranslate über den Bus

    def _save(self):
        self.s.setValue("use_bundled", self.chk_use_bundled.isChecked())
        # Pfade speichern (auch wenn ggf. deaktiviert – bestehende Werte bleiben erhalten)
        self.s.setValue("path_ffmpeg", self.le_ffmpeg.text().strip())
        self.s.setValue("path_ffprobe", self.le_ffprobe.text().strip())

        style = "toast"
        if self.rb_status.isChecked():
            style = "statusbar"
        elif self.rb_dialog.isChecked():
            style = "dialog"
        set_notify_style(style)
        self.notify_style_changed.emit(style)
        self.accept()
