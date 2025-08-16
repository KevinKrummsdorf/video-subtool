from __future__ import annotations
from pathlib import Path
from typing import Optional, List, TypedDict

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow, QWidget, QFileDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableView, QListWidget, QListWidgetItem, QLabel, QComboBox, QMessageBox, QSplitter, QStatusBar,
    QProgressDialog, QMenuBar, QHeaderView, QCheckBox, QLineEdit
)

from app.settings import get_settings
from app.i18n import t
from app import i18n
from app.view.stream_table_model import StreamTableModel
from app.view.settings_dialog import SettingsDialog
from app.view.about_dialog import AboutDialog
from app.controller.subtitle_controller import SubtitleController
from app.controller.batch_controller import BatchController


class BatchStep(TypedDict, total=False):
    mode: str                 # "export" | "strip"
    keep: Optional[str]       # "forced" | "full" | None
    export_rel_idx: Optional[int]


class MainWindow(QMainWindow):
    """Hauptfenster (nur View + Wiring zu Controllern)."""

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.sub_ctrl = SubtitleController()
        self.batch_ctrl = BatchController(self)
        self.batch_ctrl.progress.connect(self._on_batch_progress)
        self.batch_ctrl.error.connect(self._on_batch_error)
        self.batch_ctrl.finished.connect(self._on_batch_finished_chained)

        self._build_menu()

        # --- Topbar (Ordnerwahl) ---
        self.folder_label = QLabel()
        self.btn_pick = QPushButton()
        self.btn_pick.clicked.connect(self._pick_folder)

        # --- Videoliste ---
        self.video_list = QListWidget()
        self.video_list.currentItemChanged.connect(self._on_video_selected)

        # --- Stream-Tabelle ---
        self.stream_model = StreamTableModel()
        self.stream_table = QTableView()
        self.stream_table.setModel(self.stream_model)
        self.stream_table.setSelectionBehavior(QTableView.SelectRows)
        self.stream_table.setSelectionMode(QTableView.SingleSelection)

        # Tabelle: Look & Feel
        self.stream_table.verticalHeader().setVisible(False)
        self.stream_table.setAlternatingRowColors(True)
        self.stream_table.setWordWrap(False)
        self.stream_table.setSortingEnabled(False)
        h = self.stream_table.horizontalHeader()
        h.setStretchLastSection(True)
        h.setHighlightSections(False)
        h.setSectionsMovable(True)
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # --- Optionen-Bereich (Häkchen + Dropdown) ---
        self.chk_export_selected = QCheckBox("Ausgewählten Sub exportieren")
        self.chk_export_selected.setChecked(True)

        self.chk_strip_keep_rule = QCheckBox("Subs entfernen / Original ersetzen (Regel unten)")
        self.keep_combo = QComboBox()
        # nur forced/full – Default = forced
        self.keep_combo.addItem("nur Forced behalten", "forced")
        self.keep_combo.addItem("nur Full behalten", "full")
        self.keep_combo.setEnabled(False)

        self.chk_remove_all = QCheckBox("Alle Untertitel entfernen")

        # Export-Ziel (optional eigener Ordner)
        self.chk_custom_export_dir = QCheckBox("Eigenen Zielordner verwenden")
        self.edit_export_dir = QLineEdit()
        self.edit_export_dir.setReadOnly(True)
        self.btn_browse_export = QPushButton("Ziel wählen …")
        self.btn_browse_export.clicked.connect(self._browse_export_dir)
        for w in (self.edit_export_dir, self.btn_browse_export):
            w.setEnabled(False)
        self.chk_custom_export_dir.toggled.connect(
            lambda on: [self.edit_export_dir.setEnabled(on), self.btn_browse_export.setEnabled(on)]
        )

        # Batch + Start
        self.chk_apply_folder = QCheckBox("Auf gesamten Ordner anwenden (Batch)")
        self.btn_start = QPushButton("Start")
        self.btn_start.clicked.connect(self._on_start_clicked)

        # --- Layouts ---
        topbar = QHBoxLayout()
        topbar.addWidget(self.folder_label)
        topbar.addStretch(1)
        topbar.addWidget(self.btn_pick)

        self.lbl_streams = QLabel()
        self.lbl_videos = QLabel()

        export_row = QHBoxLayout()
        export_row.addWidget(self.chk_custom_export_dir)
        export_row.addWidget(self.edit_export_dir, 1)
        export_row.addWidget(self.btn_browse_export)

        rightbar = QVBoxLayout()
        rightbar.addWidget(self.lbl_streams)
        rightbar.addWidget(self.stream_table)

        # Optionen in gewünschter Reihenfolge
        rightbar.addWidget(self.chk_export_selected)
        rightbar.addWidget(self.chk_strip_keep_rule)
        rightbar.addWidget(self.keep_combo)         # Dropdown direkt darunter
        rightbar.addWidget(self.chk_remove_all)
        rightbar.addLayout(export_row)

        rightbar.addSpacing(8)
        rightbar.addWidget(self.chk_apply_folder)
        rightbar.addWidget(self.btn_start)
        rightbar.addStretch(1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.lbl_videos)
        left_layout.addWidget(self.video_list)

        right = QWidget()
        right.setLayout(rightbar)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        central = QWidget()
        main = QVBoxLayout(central)
        main.addLayout(topbar)
        main.addWidget(splitter)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        # i18n
        i18n.bus.language_changed.connect(self._retranslate)
        self._retranslate()

        # Letzten Ordner laden
        last = self.settings.value("last_folder", "")
        if last and Path(last).exists():
            self._load_folder(Path(last))

        # Startgröße (60%) & Tabellenbreiten
        self._adjust_initial_size(splitter)
        QTimer.singleShot(0, self._apply_table_layout)
        self.stream_model.modelReset.connect(self._apply_table_layout)
        self.stream_model.layoutChanged.connect(self._apply_table_layout)

        # Toggle-Logik Dropdown
        self.chk_strip_keep_rule.toggled.connect(self._update_keep_combo_enabled)
        self.chk_remove_all.toggled.connect(self._update_keep_combo_enabled)

        # Laufzeit
        self._progress: QProgressDialog | None = None
        self._batch_queue: List[BatchStep] = []

    # ---------- Größe & Layout ----------
    def _adjust_initial_size(self, splitter: QSplitter) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        w = int(area.width() * 0.60)
        h = int(area.height() * 0.60)
        self.resize(w, h)
        splitter.setSizes([int(w * 0.35), int(w * 0.65)])
        frame = self.frameGeometry()
        frame.moveCenter(area.center())
        self.move(frame.topLeft())
        self.setMinimumSize(int(area.width() * 0.4), int(area.height() * 0.4))

    def _apply_table_layout(self) -> None:
        header: QHeaderView = self.stream_table.horizontalHeader()
        cols = self.stream_model.columnCount()
        if cols == 0:
            return
        header.setSectionResizeMode(QHeaderView.Interactive)
        widths = {0: 70, 1: 70, 2: 120, 3: 80, 5: 110, 6: 80}
        for i in range(cols):
            if i in widths:
                header.resizeSection(i, widths[i])
        title_idx = 4 if cols > 4 else cols - 1
        if title_idx >= 0:
            header.setStretchLastSection(False)
            if title_idx != cols - 1:
                header.moveSection(title_idx, cols - 1)
            header.setStretchLastSection(True)

    def _update_keep_combo_enabled(self):
        enable = self.chk_strip_keep_rule.isChecked() and not self.chk_remove_all.isChecked()
        self.keep_combo.setEnabled(enable)

    # ---------- Menü ----------

    def _build_menu(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        self.menu_file = menubar.addMenu("")
        self.act_pick = QAction("", self)
        self.act_pick.triggered.connect(self._pick_folder)
        self.menu_file.addAction(self.act_pick)

        self.menu_edit = menubar.addMenu("")
        self.act_settings = QAction("", self)
        self.act_settings.triggered.connect(self._open_settings)
        self.menu_edit.addAction(self.act_settings)

        self.menu_help = menubar.addMenu("")
        self.act_about = QAction("", self)
        self.act_about.triggered.connect(self._about)
        self.menu_help.addAction(self.act_about)

    def _retranslate(self, *_):
        # Titel & Top-Leiste
        self.setWindowTitle(t("app.title"))
        self.folder_label.setText(t("mw.no.folder"))
        self.btn_pick.setText(t("common.folder.choose"))

        # Labels
        self.lbl_streams.setText(t("mw.streams.in.video"))
        self.lbl_videos.setText(t("mw.video.files"))

        # Dropdown (nur forced/full)
        self.keep_combo.setItemText(0, t("mw.keep.forced"))
        self.keep_combo.setItemText(1, t("mw.keep.full"))

        # Optionen (Checkboxen + Buttons)
        self.chk_export_selected.setText(t("mw.opt.export_selected"))
        self.chk_strip_keep_rule.setText(t("mw.opt.strip_with_rule"))
        self.chk_remove_all.setText(t("mw.opt.remove_all"))
        self.chk_custom_export_dir.setText(t("mw.opt.custom_export_dir"))
        self.btn_browse_export.setText(t("sd.pick.file"))  # "Ziel wählen …" / "Choose file"
        self.chk_apply_folder.setText(t("mw.opt.apply_to_folder"))
        self.btn_start.setText(t("mw.start"))

        # Menüs
        self.menu_file.setTitle(t("menu.file"))
        self.act_pick.setText(t("common.folder.open"))
        self.menu_edit.setTitle(t("menu.settings"))
        self.act_settings.setText(t("common.settings"))
        self.menu_help.setTitle(t("menu.help"))
        self.act_about.setText(t("common.about"))


    # ---------- Settings / About ----------

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.statusBar().showMessage(t("sd.saved"), 4000)

    def _about(self):
        AboutDialog(self).exec()

    # ---------- Ordner & Streams ----------

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(self, t("common.folder.choose"))
        if not path:
            return
        self._load_folder(Path(path))
        self.settings.setValue("last_folder", path)

    def _load_folder(self, folder: Path):
        self.folder_label.setText(str(folder))
        self.video_list.clear()
        items = self.sub_ctrl.scan_folder(folder)
        for it in items:
            li = QListWidgetItem(it.path.name)
            li.setData(Qt.UserRole, str(it.path))
            self.video_list.addItem(li)
        if self.video_list.count() > 0:
            self.video_list.setCurrentRow(0)
        QTimer.singleShot(0, self._apply_table_layout)

    def _on_video_selected(self, curr: Optional[QListWidgetItem], prev: Optional[QListWidgetItem]):
        if not curr:
            self.stream_model.set_rows([])
            QTimer.singleShot(0, self._apply_table_layout)
            return
        file = Path(curr.data(Qt.UserRole))
        try:
            rows = self.sub_ctrl.get_stream_table(file)
        except FileNotFoundError as e:
            QMessageBox.warning(self, t("mw.ffmpeg.missing"), str(e))
            rows = []
        except Exception as e:
            QMessageBox.critical(self, t("mw.analyze.error"), str(e))
            rows = []
        self.stream_model.set_rows(rows)
        QTimer.singleShot(0, self._apply_table_layout)

    def _selected_row_rel_idx(self) -> Optional[int]:
        sel = self.stream_table.selectionModel()
        if not sel or not sel.hasSelection():
            return None
        row = sel.selectedRows()[0].row()
        rel_idx = self.stream_model.rows[row][1]
        return int(rel_idx)

    # ---------- Export-Ziel ----------

    def _browse_export_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Zielordner wählen")
        if path:
            self.edit_export_dir.setText(path)

    def _resolve_export_dir(self, src_file: Path) -> Path:
        if self.chk_custom_export_dir.isChecked():
            p = self.edit_export_dir.text().strip()
            if p:
                return Path(p)
        return src_file.parent / "subs_export"

    # ---------- Start-Button ----------

    @Slot()
    def _on_start_clicked(self):
        if not any([self.chk_export_selected.isChecked(),
                    self.chk_strip_keep_rule.isChecked(),
                    self.chk_remove_all.isChecked()]):
            QMessageBox.information(self, t("app.title"), "Bitte mindestens eine Aktion auswählen.")
            return

        if self.chk_apply_folder.isChecked():
            # Batch-Schrittkette bauen (Export -> Strip)
            self._batch_queue.clear()
            rel_idx = self._selected_row_rel_idx()

            if self.chk_export_selected.isChecked():
                if rel_idx is None:
                    QMessageBox.information(self, t("app.title"), t("mw.pick.subtitle.first"))
                    return
                self._batch_queue.append(BatchStep(mode="export", keep=None, export_rel_idx=rel_idx))

            if self.chk_remove_all.isChecked():
                self._batch_queue.append(BatchStep(mode="strip", keep=None, export_rel_idx=None))
            elif self.chk_strip_keep_rule.isChecked():
                keep = self.keep_combo.currentData()
                if not keep:
                    keep = "forced"
                self._batch_queue.append(BatchStep(mode="strip", keep=keep, export_rel_idx=None))

            if not self._batch_queue:
                return

            self._progress = QProgressDialog("Starte Batch…", t("common.cancel"), 0, 100, self)
            self._progress.setWindowTitle(t("common.batch"))
            self._progress.setAutoClose(False)
            self._progress.setAutoReset(False)
            self._progress.setMinimumDuration(0)
            self._progress.canceled.connect(self.batch_ctrl.stop)

            # Custom-Exportziel für Batch optional merken (Quick-Flag)
            if self.chk_custom_export_dir.isChecked():
                self.settings.setValue("batch_custom_export_dir", self.edit_export_dir.text().strip())
            else:
                self.settings.remove("batch_custom_export_dir")

            self._start_next_batch_step()
            return

        # Einzeldatei
        item = self.video_list.currentItem()
        if not item:
            QMessageBox.information(self, t("app.title"), t("mw.pick.video.first"))
            return
        src = Path(item.data(Qt.UserRole))

        # Export
        if self.chk_export_selected.isChecked():
            rel_idx = self._selected_row_rel_idx()
            if rel_idx is None:
                QMessageBox.information(self, t("app.title"), t("mw.pick.subtitle.first"))
                return
            out_dir = self._resolve_export_dir(src)
            try:
                out = self.sub_ctrl.export_stream(src, rel_idx, out_dir)
                self.statusBar().showMessage(t("mw.exported", path=str(out)), 5000)
            except Exception as e:
                QMessageBox.critical(self, t("mw.export.failed"), str(e))
                return

        # Strip: alle oder nach Regel
        if self.chk_remove_all.isChecked() or self.chk_strip_keep_rule.isChecked():
            keep: Optional[str] = None
            if not self.chk_remove_all.isChecked():
                keep = self.keep_combo.currentData() or "forced"
            confirm = QMessageBox.question(self, t("app.title"), t("dlg.strip.confirm"))
            if confirm != QMessageBox.Yes:
                return
            try:
                out = self.sub_ctrl.strip_subs(src, keep=keep)
                self._on_video_selected(self.video_list.currentItem(), None)
                self.statusBar().showMessage(t("mw.replaced", name=out.name), 5000)
            except Exception as e:
                QMessageBox.critical(self, t("mw.analyze.error"), str(e))
                return

    # ---------- Batch-Kette ----------

    def _collect_current_folder_files(self) -> List[Path]:
        files: List[Path] = []
        for i in range(self.video_list.count()):
            it = self.video_list.item(i)
            files.append(Path(it.data(Qt.UserRole)))
        return files

    def _start_next_batch_step(self):
        if not self._batch_queue:
            if self._progress:
                self._progress.setValue(100)
                self._progress.close()
                self._progress = None
            self._on_video_selected(self.video_list.currentItem(), None)
            QMessageBox.information(self, t("common.done"), "Batch abgeschlossen.")
            return

        step = self._batch_queue.pop(0)
        files = self._collect_current_folder_files()
        if not files:
            QMessageBox.information(self, t("app.title"), t("mw.no.videos"))
            if self._progress:
                self._progress.close()
                self._progress = None
            return

        self.batch_ctrl.start(files=files, mode=step["mode"],
                              keep=step.get("keep"), export_rel_idx=step.get("export_rel_idx"))

    def _on_batch_progress(self, percent: int, name: str):
        if self._progress:
            self._progress.setLabelText(t("common.processing", name=name))
            self._progress.setValue(percent)

    def _on_batch_error(self, msg: str):
        self.statusBar().showMessage(f"Error: {msg}", 7000)

    def _on_batch_finished_chained(self, processed: int, errors: int):
        if self._progress:
            self._progress.setLabelText(f"{t('common.done.processed')}: {processed} | {t('common.done.errors')}: {errors}")
        self._start_next_batch_step()
