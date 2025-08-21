from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Optional, List, TypedDict

from PySide6.QtCore import Qt, QTimer, Slot, Signal, QEvent
from PySide6.QtGui import QAction, QFontMetrics
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow, QWidget, QFileDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableView, QListWidget, QListWidgetItem, QLabel, QComboBox, QSplitter, QStatusBar,
    QProgressDialog, QMenuBar, QHeaderView, QCheckBox, QLineEdit, QMenu, QSizePolicy
)

from app.settings import get_settings, notify_style_default
from app.i18n import t
from app import i18n
from app.view.stream_table_model import StreamTableModel
from app.view.settings_dialog import SettingsDialog
from app.view.about_dialog import AboutDialog
from app.controller.subtitle_controller import SubtitleController
from app.controller.batch_controller import BatchController
from app.service.notification_center import notification_center
from app.view.notifiers import INotifier, StatusBarNotifier, DialogNotifier, ToastNotifier
from app.view.toast_overlay import ToastOverlay
from app.service.path_service import path_service
from PySide6.QtCore import QByteArray
from app.settings import settings_get_bytes
from app.settings import settings_set_bytes


class BatchStep(TypedDict, total=False):
    mode: str                 # "export" | "strip"
    keep: Optional[str]       # "forced" | "full" | None
    export_rel_idx: Optional[int]


class VideoListWidget(QListWidget):
    """List widget that accepts external video file drops."""

    files_dropped = Signal(list)

    def __init__(self, collector, parent=None):
        super().__init__(parent)
        self._collector = collector
        self.setAcceptDrops(True)
        self.setDragEnabled(False)

    def _collect(self, e):
        if not e.mimeData().hasUrls():
            return []
        paths = [Path(u.toLocalFile()) for u in e.mimeData().urls()]
        return self._collector(paths)

    def dragEnterEvent(self, e):  # noqa: N802 (Qt override)
        if self._collect(e):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):  # noqa: N802 (Qt override)
        if self._collect(e):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):  # noqa: N802 (Qt override)
        files = self._collect(e)
        if files:
            self.files_dropped.emit(files)
            e.acceptProposedAction()
        else:
            e.ignore()


class MainWindow(QMainWindow):
    """Hauptfenster (nur View + Wiring zu Controllern)."""

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.sub_ctrl = SubtitleController()
        self.batch_ctrl = BatchController(self)
        self.batch_ctrl.progress.connect(self._on_batch_progress)
        self.batch_ctrl.error.connect(self._on_batch_error)
        self.batch_ctrl.finished.connect(self._on_batch_finished)

        self._toast_overlay = ToastOverlay(self)
        self._notifier: INotifier = self._make_notifier()
        notification_center.notification_requested.connect(self._on_notification_requested)

        self._build_menu()
        self._build_ui()

        # --- UI-State wiederherstellen (Fenster + Splitter) ---
        try:
            g = settings_get_bytes("ui/main/geometry")
            if g:
                self.restoreGeometry(QByteArray(g))
            s = settings_get_bytes("ui/main/state")
            if s:
                self.restoreState(QByteArray(s))
            sp = settings_get_bytes("ui/main/splitter")
            if sp:
                self.splitter.restoreState(QByteArray(sp))
        except Exception:
            # silently ignore restore issues
            pass


    def _build_ui(self) -> None:
        # --- Topbar (Ordneranzeige) ---
        self.folder_label = QLabel()
        # Pfad-Label: einkanalig, kompakt, elidiert
        self.folder_label.setWordWrap(False)
        self.folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.folder_label.setContentsMargins(0, 0, 0, 0)
        self.folder_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        fm = QFontMetrics(self.folder_label.font())
        line_h = fm.height()
        self.folder_label.setMinimumHeight(line_h + 2)
        self.folder_label.setMaximumHeight(line_h + 2)
        self.folder_label.installEventFilter(self)

        # --- Videoliste ---
        self.video_list = VideoListWidget(self.sub_ctrl.collect_videos_from_paths)
        self.video_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.video_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_list.customContextMenuRequested.connect(self._on_vlist_context_menu)
        self.video_list.installEventFilter(self)
        self.video_list.files_dropped.connect(self._on_files_dropped)
        self.video_list.currentItemChanged.connect(self._on_video_selected)
        self.video_list.itemSelectionChanged.connect(self._update_video_actions_enabled)

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

        # --- Optionen-Bereich ---
        self.chk_export_selected = QCheckBox("Ausgewählten Sub exportieren")
        self.chk_export_selected.setChecked(True)

        self.chk_strip_keep_rule = QCheckBox("Subs entfernen / Original ersetzen (Regel unten)")
        self.keep_combo = QComboBox()
        self.keep_combo.addItem("nur Forced behalten", "forced")
        self.keep_combo.addItem("nur Full behalten", "full")
        self.keep_combo.setEnabled(False)

        self.chk_remove_all = QCheckBox("Alle Untertitel entfernen")

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

        self.chk_apply_folder = QCheckBox("Auf gesamten Ordner anwenden (Batch)")
        self.btn_start = QPushButton("Start")
        self.btn_start.clicked.connect(self._on_start_clicked)

        # --- kompakter Header-Container ---
        topbar_w = QWidget()
        topbar = QHBoxLayout(topbar_w)
        topbar.setContentsMargins(0, 2, 0, 2)   # enger
        topbar.setSpacing(8)
        topbar.addWidget(self.folder_label, 1)
        topbar_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        topbar_w.setFixedHeight(line_h + 6)

        self.lbl_streams = QLabel()
        self.lbl_videos = QLabel()

        export_row = QHBoxLayout()
        export_row.addWidget(self.chk_custom_export_dir)
        export_row.addWidget(self.edit_export_dir, 1)
        export_row.addWidget(self.btn_browse_export)

        rightbar = QVBoxLayout()
        rightbar.addWidget(self.lbl_streams)
        rightbar.addWidget(self.stream_table)
        rightbar.addWidget(self.chk_export_selected)
        rightbar.addWidget(self.chk_strip_keep_rule)
        rightbar.addWidget(self.keep_combo)
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

        self.splitter = QSplitter()
        self.splitter.addWidget(left)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)

        central = QWidget()
        main = QVBoxLayout(central)
        main.setContentsMargins(8, 6, 8, 8)  # insgesamt kompakter
        main.setSpacing(6)
        main.addWidget(topbar_w)
        main.addWidget(self.splitter)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        # Standardordner, i18n, erstes Laden
        self._folder_label_text: str = ""   # unverkurzte Anzeige (für Eliding)
        self.default_dir = Path(sys.argv[0]).resolve().parent

        i18n.bus.language_changed.connect(self._retranslate)
        self._retranslate()

        path_service.set_current_folder(self.default_dir)
        self._update_current_folder_label()
        self._load_folder(self.default_dir)

        # Größe & Tabellenbreiten
        self._adjust_initial_size(self.splitter)
        QTimer.singleShot(0, self._apply_table_layout)
        self.stream_model.modelReset.connect(self._apply_table_layout)
        self.stream_model.layoutChanged.connect(self._apply_table_layout)

        # Toggle-Logik Dropdown
        self.chk_strip_keep_rule.toggled.connect(self._update_keep_combo_enabled)
        self.chk_remove_all.toggled.connect(self._update_keep_combo_enabled)

        # Laufzeit
        self._progress: QProgressDialog | None = None
        self._batch_queue: list[BatchStep] = []

    # --- Hilfsfunktionen ---
    def _get_current_folder_path(self) -> Path:
        """
        Liefert den im UI dargestellten Arbeitsordner (robust).
        Primär nutzen wir path_service, diese Funktion ist Fallback/Komfort.
        """
        try:
            return path_service.get_output_folder()
        except Exception:
            txt = (self.folder_label.text() or "").strip()
            for prefix in ("Aktueller Ordner:", "Current folder:", "Ordner:", "Folder:"):
                if txt.startswith(prefix):
                    txt = txt[len(prefix):].strip()
                    break
            p = Path(txt)
            return p if p.exists() else Path.cwd()

    def _selected_row_rel_idx(self) -> Optional[int]:
        sel = self.stream_table.selectionModel()
        if not sel or not sel.hasSelection():
            return None
        row = sel.selectedRows()[0].row()
        rel_idx = self.stream_model.rows[row][1]
        return int(rel_idx)

    # --- Menü-Aktionen (werden in _build_menu() verbunden) ---
    def _export_selected(self):
        item = self.video_list.currentItem()
        if not item:
            QMessageBox.information(self, t("app.title"), t("mw.pick.video.first"))
            return
        rel_idx = self._selected_row_rel_idx()
        if rel_idx is None:
            QMessageBox.information(self, t("app.title"), t("mw.pick.subtitle.first"))
            return

        file = Path(item.data(Qt.UserRole))
        out_dir = path_service.get_output_folder()  # Export in aktuellen Arbeitsordner

        try:
            out = self.sub_ctrl.export_stream(file, rel_idx, out_dir)
        except Exception as e:
            QMessageBox.critical(self, t("mw.export.failed"), str(e))
            return

        msg = t("mw.exported", path=str(out))
        (self.notify.success(msg) if hasattr(self, "notify") else self.statusBar().showMessage(msg, 5000))

    def _strip_and_replace(self):
        item = self.video_list.currentItem()
        if not item:
            QMessageBox.information(self, t("app.title"), t("mw.pick.video.first"))
            return
        file = Path(item.data(Qt.UserRole))
        keep = self.keep_combo.currentData() or None

        if QMessageBox.question(self, t("app.title"), t("dlg.strip.confirm")) != QMessageBox.Yes:
            return

        try:
            out = self.sub_ctrl.strip_subs(file, keep=keep)
        except Exception as e:
            QMessageBox.critical(self, t("mw.analyze.error"), str(e))
            return

        self._on_video_selected(self.video_list.currentItem(), None)
        msg = t("mw.replaced", name=out.name)
        (self.notify.success(msg) if hasattr(self, "notify") else self.statusBar().showMessage(msg, 5000))

    def _batch_strip_folder(self):
        keep = self.keep_combo.currentData() or None
        if QMessageBox.question(self, t("mw.batch.confirm.strip.title"), t("mw.batch.confirm.strip.text")) != QMessageBox.Yes:
            return
        self._start_batch(mode="strip", keep=keep, export_rel_idx=None)

    def _batch_export_folder(self):
        rel_idx = self._selected_row_rel_idx()
        self._start_batch(mode="export", keep=None, export_rel_idx=rel_idx)

    def _make_notifier(self):
        style = notify_style_default()
        if style == "statusbar":
            return StatusBarNotifier(self)
        if style == "dialog":
            return DialogNotifier(self)
        return ToastNotifier(self, self._toast_overlay)

    def _on_notification_requested(self, level: str, text: str, ms: int) -> None:
        if self._notifier:
            self._notifier.notify(level, text, ms)

    def _on_notify_style_changed(self, style: str) -> None:
        self._notifier = self._make_notifier()

    def _update_current_folder_label(self) -> None:
        """Update header label to show the current output folder (elided, single-line)."""
        p = path_service.get_output_folder()
        norm = os.path.normpath(str(p)).strip()
        self._folder_label_text = f"{t('mw.current.folder')}: {norm}"

        fm = QFontMetrics(self.folder_label.font())
        # kleine Reserve, damit Padding/Margins einkalkuliert sind
        elided = fm.elidedText(self._folder_label_text, Qt.ElideRight, max(50, self.folder_label.width() - 12))
        self.folder_label.setText(elided)

    def eventFilter(self, obj, event):
        if obj is self.folder_label and event.type() == QEvent.Resize:
            fm = QFontMetrics(self.folder_label.font())
            elided = fm.elidedText(self._folder_label_text, Qt.ElideRight, max(50, self.folder_label.width() - 12))
            self.folder_label.setText(elided)
        elif obj is self.video_list and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Delete,):
                self._remove_selected_files()
                return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, e):  # sorgt ebenfalls für korrektes Eliding
        try:
            fm = QFontMetrics(self.folder_label.font())
            elided = fm.elidedText(self._folder_label_text, Qt.ElideRight, max(50, self.folder_label.width() - 12))
            self.folder_label.setText(elided)
        except Exception:
            pass
        super().resizeEvent(e)

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
        from PySide6.QtGui import QKeySequence  # optional; Strings gehen auch

        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        # ---- Datei ----
        self.menu_file = menubar.addMenu("")

        # Open (Ctrl+O)
        self.act_pick = QAction("", self)
        self.act_pick.setShortcut(QKeySequence("Ctrl+O"))
        self.act_pick.triggered.connect(self._pick_folder)
        self.menu_file.addAction(self.act_pick)

        self.menu_file.addSeparator()

        # Export selected (Ctrl+E)
        self.act_export_selected = QAction(t("mw.export.selected"), self)
        self.act_export_selected.setShortcut("Ctrl+E")
        self.act_export_selected.triggered.connect(self._export_selected)
        self.menu_file.addAction(self.act_export_selected)

        # Export all (Ctrl+Shift+E)
        self.act_batch_export = QAction(t("mw.batch.export"), self)
        self.act_batch_export.setShortcut("Ctrl+Shift+E")
        self.act_batch_export.triggered.connect(self._batch_export_folder)
        self.menu_file.addAction(self.act_batch_export)

        # Remove/Replace (Ctrl+R)
        self.act_strip_replace = QAction(t("mw.strip.replace"), self)
        self.act_strip_replace.setShortcut("Ctrl+R")
        self.act_strip_replace.triggered.connect(self._strip_and_replace)
        self.menu_file.addAction(self.act_strip_replace)

        self.menu_file.addSeparator()

        # Remove selected from list (Del)
        self.act_remove_selected = QAction("", self)
        self.act_remove_selected.setShortcut(Qt.Key_Delete)
        self.act_remove_selected.triggered.connect(self._remove_selected_files)
        self.menu_file.addAction(self.act_remove_selected)

        # Clear list (Ctrl+Shift+Del)
        self.act_clear_list = QAction("", self)
        self.act_clear_list.setShortcut(QKeySequence("Ctrl+Shift+Del"))
        self.act_clear_list.triggered.connect(self._clear_video_list)
        self.menu_file.addAction(self.act_clear_list)

        # ---- Edit ----
        self.menu_edit = menubar.addMenu("")

        # Settings (F2)
        self.act_settings = QAction("", self)
        self.act_settings.setShortcut(Qt.Key_F2)
        self.act_settings.triggered.connect(self._open_settings)
        self.menu_edit.addAction(self.act_settings)

        # ---- Help (F1) ----
        self.menu_help = menubar.addMenu("")
        self.act_about = QAction("", self)
        self.act_about.setShortcut(Qt.Key_F1)
        self.act_about.triggered.connect(self._about)
        self.menu_help.addAction(self.act_about)

        # ---- Batch (Strg+B) ----
        self.act_batch_strip = QAction(t("mw.batch.strip"), self)
        self.act_batch_strip.setShortcut("Ctrl+B")
        self.act_batch_strip.triggered.connect(self._batch_strip_folder)
        self.menu_file.addAction(self.act_batch_strip)

    def _retranslate(self, *_):
        # Titel & Top-Leiste
        self.setWindowTitle(t("app.title"))
        # Label-Text neu setzen (unverkürzt) und eliden
        current = os.path.normpath(str(path_service.get_output_folder()))
        self._folder_label_text = f"{t('mw.current.folder')}: {current}"
        fm = QFontMetrics(self.folder_label.font())
        elided = fm.elidedText(self._folder_label_text, Qt.ElideRight, max(50, self.folder_label.width() - 12))
        self.folder_label.setText(elided)

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
        self.btn_browse_export.setText(t("sd.pick.file"))
        self.chk_apply_folder.setText(t("mw.opt.apply_to_folder"))
        self.btn_start.setText(t("mw.start"))

        # Menüs
        self.menu_file.setTitle(t("menu.file"))
        self.act_pick.setText(t("common.folder.open"))
        if hasattr(self, "act_remove_selected"):
            self.act_remove_selected.setText(t("mw.remove.selected"))
        if hasattr(self, "act_clear_list"):
            self.act_clear_list.setText(t("mw.clear.list"))
        self.menu_edit.setTitle(t("menu.settings"))
        self.act_settings.setText(t("common.settings"))
        self.menu_help.setTitle(t("menu.help"))
        self.act_about.setText(t("common.about"))

    # ---------- Settings / About ----------

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.notify_style_changed.connect(self._on_notify_style_changed)
        if dlg.exec():
            self.statusBar().showMessage(t("sd.saved"), 4000)

    def _about(self):
        AboutDialog(self).exec()

    # ---------- Ordner & Streams ----------

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("common.folder.choose"), str(self.default_dir)
        )
        if not path:
            return
        self._load_folder(Path(path))

    def _load_folder(self, folder: Path):
        path_service.set_current_folder(folder)
        self._update_current_folder_label()
        self.video_list.clear()
        items = self.sub_ctrl.scan_folder(folder)
        for it in items:
            li = QListWidgetItem(it.path.name)
            li.setData(Qt.UserRole, str(it.path))
            self.video_list.addItem(li)
        if self.video_list.count() > 0:
            self.video_list.setCurrentRow(0)
        QTimer.singleShot(0, self._apply_table_layout)
        self._update_video_actions_enabled()

    def _on_files_dropped(self, files: List[Path]) -> None:
        existing = {Path(self.video_list.item(i).data(Qt.UserRole)) for i in range(self.video_list.count())}
        added: List[QListWidgetItem] = []
        for p in files:
            if p not in existing:
                item = QListWidgetItem(p.name)
                item.setData(Qt.UserRole, str(p))
                self.video_list.addItem(item)
                added.append(item)
                existing.add(p)
        if not added:
            self.statusBar().showMessage(t("mw.no.videos"), 4000)
            return
        if not self.video_list.currentItem():
            self.video_list.setCurrentItem(added[0])
        self._update_video_actions_enabled()

    def _on_vlist_context_menu(self, pos):
        if self.video_list.count() == 0:
            return
        menu = QMenu(self)
        act_remove = menu.addAction(t("mw.remove.selected"))
        act_clear = menu.addAction(t("mw.clear.list"))
        act_remove.setEnabled(self.video_list.selectedItems())
        act_clear.setEnabled(self.video_list.count() > 0)
        chosen = menu.exec_(self.video_list.mapToGlobal(pos))
        if chosen == act_remove:
            self._remove_selected_files()
        elif chosen == act_clear:
            self._clear_video_list()

    def _on_video_selected(self, curr: Optional[QListWidgetItem], prev: Optional[QListWidgetItem]):
        if not curr:
            self.stream_model.set_rows([])
            QTimer.singleShot(0, self._apply_table_layout)
            self._update_video_actions_enabled()
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
        self._update_video_actions_enabled()

    def _remove_selected_files(self):
        items = self.video_list.selectedItems()
        if not items:
            return
        rows = sorted((self.video_list.row(it) for it in items), reverse=True)
        current_removed = False
        curr = self.video_list.currentItem()
        for r in rows:
            if self.video_list.item(r) is curr:
                current_removed = True
            self.video_list.takeItem(r)
        if current_removed:
            self.stream_model.set_rows([])
        self._update_video_actions_enabled()

    def _clear_video_list(self):
        self.video_list.clear()
        self.stream_model.set_rows([])
        self._update_video_actions_enabled()

    def _update_video_actions_enabled(self):
        has_items = self.video_list.count() > 0
        has_sel = len(self.video_list.selectedItems()) > 0
        if hasattr(self, "act_remove_selected"):
            self.act_remove_selected.setEnabled(has_sel)
        if hasattr(self, "act_clear_list"):
            self.act_clear_list.setEnabled(has_items)

    def _browse_export_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Zielordner wählen")
        if path:
            self.edit_export_dir.setText(path)

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
            try:
                out = self.sub_ctrl.export_stream(src, rel_idx)
                notification_center.success(t("toast.exported", path=str(out)))
            except Exception as e:
                QMessageBox.critical(self, t("mw.export.fail.title"), f"{t('mw.export.fail.msg')}\n\n{e}")
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
                notification_center.success(t("toast.replaced", name=out.name))
            except Exception as e:
                QMessageBox.critical(self, t("mw.remove.fail.title"), f"{t('mw.remove.fail.msg')}\n\n{e}")
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
        notification_center.error(msg)

    def _on_batch_finished(self, processed: int, errors: int):
        if self._progress:
            self._progress.setLabelText(f"{t('common.done.processed')}: {processed} | {t('common.done.errors')}: {errors}")
        if errors == 0:
            notification_center.success(t("mw.batch.done.msg", processed=str(processed)))
        else:
            notification_center.warn(t("mw.batch.done.partial", processed=str(processed), errors=str(errors)))
        self._start_next_batch_step()

    def closeEvent(self, event):
        # Fenster- & Splitter-Layout persistieren
        try:
            settings_set_bytes("ui/main/geometry", bytes(self.saveGeometry()))
            settings_set_bytes("ui/main/state",    bytes(self.saveState()))
            if hasattr(self, "splitter"):
                settings_set_bytes("ui/main/splitter", bytes(self.splitter.saveState()))
        except Exception:
            pass
        super().closeEvent(event)

