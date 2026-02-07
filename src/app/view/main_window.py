# src/app/view/main_window.py
from __future__ import annotations
import os
import sys
import subprocess
import re
from pathlib import Path
from typing import Optional, List, TypedDict

from PySide6.QtCore import Qt, QTimer, Slot, Signal, QEvent, QByteArray
from PySide6.QtGui import QAction, QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow, QWidget, QFileDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableView, QListWidget, QListWidgetItem, QLabel, QComboBox, QSplitter, QStatusBar,
    QProgressDialog, QMenuBar, QHeaderView, QCheckBox, QLineEdit, QMenu, QSizePolicy,
    QMessageBox, QTabWidget, QGroupBox
)

from app.settings import get_settings, notify_style_default, settings_get_bytes, settings_set_bytes
from app.i18n import t
from app import i18n
from app.view.stream_table_model import StreamTableModel
from app.view.settings_dialog import SettingsDialog
from app.controller.subtitle_controller import SubtitleController
from app.controller.batch_controller import BatchController
from app.service.notification_center import notification_center
from app.view.notifiers import INotifier, StatusBarNotifier, DialogNotifier, ToastNotifier
from app.view.toast_overlay import ToastOverlay
from app.service.path_service import path_service
from app.service.ffmpeg_service import FfmpegService


class BatchStep(TypedDict, total=False):
    mode: str                 # "export" | "strip"
    keep: Optional[str]       # "forced" | "full" | None
    export_rel_idx: Optional[int]
    out_dir: Optional[Path]


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

    def dragEnterEvent(self, e):  # noqa: N802
        if self._collect(e):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):  # noqa: N802
        if self._collect(e):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):  # noqa: N802
        files = self._collect(e)
        if files:
            self.files_dropped.emit(files)
            e.acceptProposedAction()
        else:
            e.ignore()


class SubtitleLineEdit(QLineEdit):
    """QLineEdit that accepts subtitle file drops."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def _is_subtitle_file(self, path: Path) -> bool:
        return path.suffix.lower() in ['.srt', '.ass', '.ssa', '.sub', '.idx']

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            urls = e.mimeData().urls()
            if len(urls) == 1:
                path = Path(urls[0].toLocalFile())
                if path.is_file() and self._is_subtitle_file(path):
                    e.acceptProposedAction()
                    return
        e.ignore()

    def dragMoveEvent(self, e):
        self.dragEnterEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            urls = e.mimeData().urls()
            if len(urls) == 1:
                path = Path(urls[0].toLocalFile())
                if path.is_file() and self._is_subtitle_file(path):
                    self.setText(str(path))
                    e.acceptProposedAction()
                    return
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

        # Startprüfung (freundlich bei Custom; Hinweis bei System; blockend nur wenn gar nichts gefunden wird)
        QTimer.singleShot(0, self._startup_check_ffmpeg)

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
            pass

    def _build_ui(self) -> None:
        # --- Topbar (Ordneranzeige) ---
        self.folder_label = QLabel()
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
        topbar.setContentsMargins(0, 2, 0, 2)
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

        series_row = QHBoxLayout()
        self.lbl_series_name = QLabel()
        self.edit_series_name = QLineEdit()
        series_row.addWidget(self.lbl_series_name)
        series_row.addWidget(self.edit_series_name, 1)

        # Tab "Export"
        export_tab = QWidget()
        export_layout = QVBoxLayout(export_tab)
        export_layout.addWidget(self.lbl_streams)
        export_layout.addWidget(self.stream_table)
        export_layout.addWidget(self.chk_export_selected)
        export_layout.addWidget(self.chk_strip_keep_rule)
        export_layout.addWidget(self.keep_combo)
        export_layout.addWidget(self.chk_remove_all)
        export_layout.addLayout(export_row)
        export_layout.addLayout(series_row)
        export_layout.addSpacing(8)
        export_layout.addWidget(self.chk_apply_folder)
        export_layout.addWidget(self.btn_start)
        export_layout.addStretch(1)

        self.tabs = QTabWidget()
        self.tabs.addTab(export_tab, t("tab.export"))

        # Tab "Build"
        build_tab = QWidget()
        build_layout = QVBoxLayout(build_tab)
        
        # Video File Selection
        self.video_group = QGroupBox()
        video_layout = QHBoxLayout()
        self.video_file_edit = QLineEdit()
        self.browse_video_button = QPushButton()
        video_layout.addWidget(self.video_file_edit)
        video_layout.addWidget(self.browse_video_button)
        self.video_group.setLayout(video_layout)
        build_layout.addWidget(self.video_group)

        # Audio Files Selection
        self.audio_group = QGroupBox()
        audio_layout = QVBoxLayout()
        self.audio_list_widget = QListWidget()
        audio_buttons_layout = QHBoxLayout()
        self.add_audio_button = QPushButton()
        self.remove_audio_button = QPushButton()
        audio_buttons_layout.addWidget(self.add_audio_button)
        audio_buttons_layout.addWidget(self.remove_audio_button)
        audio_layout.addWidget(self.audio_list_widget)
        audio_layout.addLayout(audio_buttons_layout)
        self.audio_group.setLayout(audio_layout)
        build_layout.addWidget(self.audio_group)

        # Subtitle Files Selection
        self.subtitle_group = QGroupBox()
        subtitle_layout = QVBoxLayout()
        self.subtitle_list_widget = QListWidget()
        subtitle_buttons_layout = QHBoxLayout()
        self.add_subtitle_button = QPushButton()
        self.remove_subtitle_button = QPushButton()
        subtitle_buttons_layout.addWidget(self.add_subtitle_button)
        subtitle_buttons_layout.addWidget(self.remove_subtitle_button)
        subtitle_layout.addWidget(self.subtitle_list_widget)
        subtitle_layout.addLayout(subtitle_buttons_layout)
        self.subtitle_group.setLayout(subtitle_layout)
        build_layout.addWidget(self.subtitle_group)
        
        # Default Track Selection
        self.default_track_group = QGroupBox()
        default_track_layout = QHBoxLayout()
        self.default_audio_combo = QComboBox()
        self.default_subtitle_combo = QComboBox()
        self.default_audio_label = QLabel()
        self.default_subtitle_label = QLabel()
        default_track_layout.addWidget(self.default_audio_label)
        default_track_layout.addWidget(self.default_audio_combo)
        default_track_layout.addWidget(self.default_subtitle_label)
        default_track_layout.addWidget(self.default_subtitle_combo)
        self.default_track_group.setLayout(default_track_layout)
        build_layout.addWidget(self.default_track_group)

        # Output File Selection
        self.output_group = QGroupBox()
        output_layout = QHBoxLayout()
        self.output_file_edit = QLineEdit()
        self.browse_output_button = QPushButton()
        output_layout.addWidget(self.output_file_edit)
        output_layout.addWidget(self.browse_output_button)
        self.output_group.setLayout(output_layout)
        build_layout.addWidget(self.output_group)

        # Create Button
        self.btn_create_mkv = QPushButton()
        build_layout.addWidget(self.btn_create_mkv)
        build_layout.addStretch(1)
        
        self.tabs.addTab(build_tab, t("tab.build"))

        # Tab "Convert"
        convert_tab = QWidget()
        convert_layout = QVBoxLayout(convert_tab)

        self.convert_group = QGroupBox()
        convert_group_layout = QHBoxLayout()
        self.convert_file_edit = SubtitleLineEdit()
        self.browse_convert_file_button = QPushButton()
        convert_group_layout.addWidget(self.convert_file_edit)
        convert_group_layout.addWidget(self.browse_convert_file_button)
        self.convert_group.setLayout(convert_group_layout)
        convert_layout.addWidget(self.convert_group)

        self.convert_video_group = QGroupBox()
        convert_video_group_layout = QHBoxLayout()
        self.convert_video_file_edit = QLineEdit()
        self.browse_convert_video_file_button = QPushButton()
        convert_video_group_layout.addWidget(self.convert_video_file_edit)
        convert_video_group_layout.addWidget(self.browse_convert_video_file_button)
        self.convert_video_group.setLayout(convert_video_group_layout)
        convert_layout.addWidget(self.convert_video_group)
        self.convert_video_group.setVisible(False)

        self.format_group = QGroupBox()
        format_layout = QHBoxLayout()
        self.to_format_combo = QComboBox()
        self.to_label = QLabel()
        format_layout.addWidget(self.to_label)
        format_layout.addWidget(self.to_format_combo)
        self.format_group.setLayout(format_layout)
        convert_layout.addWidget(self.format_group)
        
        self.btn_convert = QPushButton()
        convert_layout.addWidget(self.btn_convert)
        convert_layout.addStretch(1)

        self.tabs.addTab(convert_tab, t("tab.convert"))

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.lbl_videos)
        left_layout.addWidget(self.video_list)

        right = self.tabs

        self.splitter = QSplitter()
        self.splitter.addWidget(left)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)

        central = QWidget()
        main = QVBoxLayout(central)
        main.setContentsMargins(8, 6, 8, 8)
        main.setSpacing(6)
        main.addWidget(topbar_w)
        main.addWidget(self.splitter)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        # Standardordner, i18n, erstes Laden
        self._folder_label_text: str = ""   # vollständiger Text für Eliding
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

        # Build tab signals
        self.browse_video_button.clicked.connect(self._browse_video)
        self.add_audio_button.clicked.connect(self._add_audio)
        self.remove_audio_button.clicked.connect(self._remove_audio)
        self.add_subtitle_button.clicked.connect(self._add_subtitle)
        self.remove_subtitle_button.clicked.connect(self._remove_subtitle)
        self.browse_output_button.clicked.connect(self._browse_output)
        self.btn_create_mkv.clicked.connect(self._create_mkv)

        # Convert tab
        self.to_format_combo.addItems(["SRT", "ASS/SSA", "SUB/IDX"])
        self.browse_convert_file_button.clicked.connect(self._browse_convert_file)
        self.browse_convert_video_file_button.clicked.connect(self._browse_convert_video_file)
        self.btn_convert.clicked.connect(self._convert_subtitle)
        self.convert_file_edit.textChanged.connect(self._update_to_format_combo)
        self.to_format_combo.currentTextChanged.connect(self._on_to_format_changed)

        # Laufzeit
        self._progress: QProgressDialog | None = None
        self._batch_queue: list[BatchStep] = []
        self._video_file = None
        self._audio_files = []
        self._subtitle_files = []
        self._existing_audio_streams = []
        self._existing_subtitle_streams = []

    # --- Hilfsfunktionen ---
    def _get_current_folder_path(self) -> Path:
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

    # --- Menü-Aktionen ---
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
        out_dir = path_service.get_output_folder()
        try:
            out = self.sub_ctrl.export_stream(file, rel_idx, out_dir)
        except Exception as e:
            QMessageBox.critical(self, t("mw.export.failed"), str(e))
            return

        notification_center.success(t("mw.exported", path=str(out)))

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
        notification_center.success(t("mw.replaced", name=out.name))

    def _batch_strip_folder(self):
        keep = self.keep_combo.currentData() or None
        if QMessageBox.question(self, t("mw.batch.confirm.strip.title"), t("mw.batch.confirm.strip.text")) != QMessageBox.Yes:
            return
        self._start_batch(mode="strip", keep=keep, export_rel_idx=None)

    def _batch_export_folder(self):
        rel_idx = self._selected_row_rel_idx()
        self._start_batch(mode="export", keep=None, export_rel_idx=rel_idx)

    def _start_batch(self, mode: str, keep: Optional[str], export_rel_idx: Optional[int]):
        self._batch_queue.clear()
        
        out_dir = self._get_export_output_dir() if mode == "export" else None

        self._batch_queue.append(BatchStep(
            mode=mode, 
            keep=keep, 
            export_rel_idx=export_rel_idx,
            out_dir=out_dir
        ))
        
        self._progress = QProgressDialog("Starte Batch…", t("common.cancel"), 0, 100, self)
        self._progress.setWindowTitle(t("common.batch"))
        self._progress.setAutoClose(False)
        self._progress.setAutoReset(False)
        self._progress.setMinimumDuration(0)
        self._progress.canceled.connect(self.batch_ctrl.stop)

        self._start_next_batch_step()

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

    def resizeEvent(self, e):
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
        from PySide6.QtGui import QKeySequence

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

        # ---- Batch (Ctrl+B) ----
        self.act_batch_strip = QAction(t("mw.batch.strip"), self)
        self.act_batch_strip.setShortcut("Ctrl+B")
        self.act_batch_strip.triggered.connect(self._batch_strip_folder)
        self.menu_file.addAction(self.act_batch_strip)

    def _retranslate(self, *_):
        # Titel & Pfadleiste
        self.setWindowTitle(t("app.title"))
        self._update_current_folder_label()

        # Labels
        self.lbl_streams.setText(t("mw.streams.in.video"))
        self.lbl_videos.setText(t("mw.video.files"))

        # Dropdown (nur forced/full)
        self.keep_combo.setItemText(0, t("mw.keep.forced"))
        self.keep_combo.setItemText(1, t("mw.keep.full"))

        # Optionen
        self.chk_export_selected.setText(t("mw.opt.export_selected"))
        self.chk_strip_keep_rule.setText(t("mw.opt.strip_with_rule"))
        self.chk_remove_all.setText(t("mw.opt.remove_all"))
        self.chk_custom_export_dir.setText(t("mw.opt.custom_export_dir"))
        self.lbl_series_name.setText(t("mw.opt.series_name"))
        self.edit_series_name.setPlaceholderText(t("mw.opt.series_name_placeholder"))
        self.btn_browse_export.setText(t("sd.pick.file"))
        self.chk_apply_folder.setText(t("mw.opt.apply_to_folder"))
        self.btn_start.setText(t("mw.start"))

        # Build Tab
        self.video_group.setTitle(t("mkv.video_file"))
        self.browse_video_button.setText(t("mkv.browse"))
        self.audio_group.setTitle(t("mkv.audio_files"))
        self.add_audio_button.setText(t("mkv.add_audio"))
        self.remove_audio_button.setText(t("mkv.remove_selected"))
        self.subtitle_group.setTitle(t("mkv.subtitle_files"))
        self.add_subtitle_button.setText(t("mkv.add_subtitle"))
        self.remove_subtitle_button.setText(t("mkv.remove_selected"))
        self.default_track_group.setTitle(t("mkv.default_tracks"))
        self.default_audio_label.setText(t("mkv.default_audio"))
        self.default_subtitle_label.setText(t("mkv.default_subtitle"))
        self.output_group.setTitle(t("mkv.output_file"))
        self.browse_output_button.setText(t("mkv.browse"))
        self.btn_create_mkv.setText(t("mkv.create_mkv"))

        # Tabs
        self.tabs.setTabText(0, t("tab.export"))
        self.tabs.setTabText(1, t("tab.build"))
        self.tabs.setTabText(2, t("tab.convert"))

        # Convert Tab
        self.convert_group.setTitle(t("convert.input_file"))
        self.browse_convert_file_button.setText(t("mkv.browse"))
        self.convert_video_group.setTitle(t("convert.video_file"))
        self.browse_convert_video_file_button.setText(t("mkv.browse"))
        self.format_group.setTitle(t("convert.formats"))
        self.to_label.setText(t("convert.to"))
        self.btn_convert.setText(t("convert.convert"))

        # Menüs
        self.menu_file.setTitle(t("menu.file"))
        self.menu_edit.setTitle(t("menu.settings"))
        self.menu_help.setTitle(t("menu.help"))

        # Datei-Menü Actions
        self.act_pick.setText(t("common.folder.open"))
        self.act_export_selected.setText(t("mw.export.selected"))
        self.act_batch_export.setText(t("mw.batch.export"))
        self.act_strip_replace.setText(t("mw.strip.replace"))
        self.act_batch_strip.setText(t("mw.batch.strip"))

        # Listen-Actions
        if hasattr(self, "act_remove_selected"):
            self.act_remove_selected.setText(t("mw.remove.selected"))
        if hasattr(self, "act_clear_list"):
            self.act_clear_list.setText(t("mw.clear.list"))

        # Einstellungen/Hilfe
        self.act_settings.setText(t("common.settings"))
        self.act_about.setText(t("common.about"))

    # ---------- Settings / About ----------
    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.notify_style_changed.connect(self._on_notify_style_changed)
        if dlg.exec():
            self.statusBar().showMessage(t("sd.saved"), 4000)

    def _about(self):
        # Lazy import, damit Build nicht am __version__-Import scheitert
        try:
            from app.view.about_dialog import AboutDialog  # noqa: WPS433 (local import intentional)
            AboutDialog(self).exec()
        except Exception as e:
            QMessageBox.critical(self, t("app.title"), f"About-Dialog konnte nicht geladen werden:\n{e}")

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

    def _get_export_output_dir(self) -> Optional[Path]:
        """Berechnet den Zielordner für den Export basierend auf den UI-Einstellungen."""
        if self.chk_custom_export_dir.isChecked():
            path_str = self.edit_export_dir.text().strip()
            return Path(path_str) if path_str else None

        series_name = self.edit_series_name.text().strip() or "unknown"
        # Sanitize: ungültige Zeichen entfernen und Directory Traversal verhindern
        series_name = re.sub(r'[<>:"/\\|?*]', '_', series_name)
        while '..' in series_name:
            series_name = series_name.replace('..', '_')

        out_dir = self.default_dir / "subs" / series_name
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

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
                
                out_dir = self._get_export_output_dir()
                self._batch_queue.append(BatchStep(mode="export", keep=None, export_rel_idx=rel_idx, out_dir=out_dir))

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
            
            out_dir = self._get_export_output_dir()

            try:
                out = self.sub_ctrl.export_stream(src, rel_idx, out_dir=out_dir)
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

    # ---------- Build Tab methods ----------
    def _create_mkv(self):
        if not self._video_file:
            QMessageBox.warning(self, t("mkv.title"), t("mkv.no_video_file"))
            return

        output_path = self.output_file_edit.text()
        if not output_path:
            QMessageBox.warning(self, t("mkv.title"), t("mkv.no_output_file"))
            return
        output_file = Path(output_path)

        default_audio_index = self.default_audio_combo.currentData()
        default_subtitle_index = self.default_subtitle_combo.currentData()

        progress_dialog = QProgressDialog(t("mkv.create_mkv"), t("common.cancel"), 0, 100, self)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setAutoClose(True)
        progress_dialog.show()

        def on_progress(value):
            progress_dialog.setValue(value)

        try:
            ffmpeg_service = FfmpegService()
            ffmpeg_service.create_mkv(
                video_file=self._video_file,
                audio_files=self._audio_files,
                subtitle_files=self._subtitle_files,
                output_file=output_file,
                default_audio_index=default_audio_index if default_audio_index != -1 else None,
                default_subtitle_index=default_subtitle_index if default_subtitle_index != -1 else None,
                on_progress=on_progress,
            )
            progress_dialog.setValue(100)
            QMessageBox.information(self, t("mkv.title"), t("mkv.success", path=str(output_file)))
        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(self, t("mkv.title"), t("mkv.fail", error=str(e)))

    def _browse_video(self):
        file, _ = QFileDialog.getOpenFileName(self, t("mkv.video_file"), "", "Video Files (*.mkv *.mp4 *.avi)")
        if file:
            self._video_file = Path(file)
            self.video_file_edit.setText(file)
            
            ffmpeg_service = FfmpegService()
            probe_result = ffmpeg_service.probe_file(self._video_file)
            self._existing_audio_streams = [s for s in probe_result.streams if s.codec_type == "audio"]
            self._existing_subtitle_streams = [s for s in probe_result.streams if s.codec_type == "subtitle"]
            
            self._update_default_audio_combo()
            self._update_default_subtitle_combo()

    def _add_audio(self):
        files, _ = QFileDialog.getOpenFileNames(self, t("mkv.audio_files"), "", "Audio Files (*.m4a *.aac *.ac3 *.dts *.mp3)")
        for file in files:
            self._audio_files.append(Path(file))
            self.audio_list_widget.addItem(file)
        self._update_default_audio_combo()

    def _remove_audio(self):
        for item in self.audio_list_widget.selectedItems():
            self._audio_files.remove(Path(item.text()))
            self.audio_list_widget.takeItem(self.audio_list_widget.row(item))
        self._update_default_audio_combo()

    def _add_subtitle(self):
        files, _ = QFileDialog.getOpenFileNames(self, t("mkv.subtitle_files"), "", "Subtitle Files (*.srt *.ass *.sup)")
        for file in files:
            self._subtitle_files.append(Path(file))
            self.subtitle_list_widget.addItem(file)
        self._update_default_subtitle_combo()

    def _remove_subtitle(self):
        for item in self.subtitle_list_widget.selectedItems():
            self._subtitle_files.remove(Path(item.text()))
            self.subtitle_list_widget.takeItem(self.subtitle_list_widget.row(item))
        self._update_default_subtitle_combo()

    def _browse_output(self):
        file, _ = QFileDialog.getSaveFileName(self, t("mkv.output_file"), "", "MKV Files (*.mkv)")
        if file:
            self.output_file_edit.setText(file)

    def _update_default_audio_combo(self):
        self.default_audio_combo.clear()
        self.default_audio_combo.addItem("None", -1)
        for i, stream in enumerate(self._existing_audio_streams):
            self.default_audio_combo.addItem(f"Stream {stream.index}: {stream.language} ({stream.codec_name})", i)
        for i, file in enumerate(self._audio_files):
            self.default_audio_combo.addItem(file.name, len(self._existing_audio_streams) + i)

    def _update_default_subtitle_combo(self):
        self.default_subtitle_combo.clear()
        self.default_subtitle_combo.addItem("None", -1)
        for i, stream in enumerate(self._existing_subtitle_streams):
            self.default_subtitle_combo.addItem(f"Stream {stream.index}: {stream.language} ({stream.codec_name})", i)
        for i, file in enumerate(self._subtitle_files):
            self.default_subtitle_combo.addItem(file.name, len(self._existing_subtitle_streams) + i)

    def _browse_convert_video_file(self):
        file, _ = QFileDialog.getOpenFileName(self, t("mkv.video_file"), "", "Video Files (*.mkv *.mp4 *.avi)")
        if file:
            self.convert_video_file_edit.setText(file)

    def _on_to_format_changed(self, text: str):
        is_sub_idx = "sub/idx" in text.lower()
        self.convert_video_group.setVisible(is_sub_idx)

    def _browse_convert_file(self):
        file, _ = QFileDialog.getOpenFileName(self, t("convert.select_file"), "", "Subtitle Files (*.srt *.ass *.ssa *.sub *.idx)")
        if file:
            self.convert_file_edit.setText(file)

    def _update_to_format_combo(self, text: str):
        path = Path(text)
        if path.is_file():
            suffix = path.suffix.lower()
            for i in range(self.to_format_combo.count()):
                item_text = self.to_format_combo.itemText(i)
                is_disabled = False
                if 'srt' in item_text.lower() and suffix == '.srt':
                    is_disabled = True
                elif 'ass' in item_text.lower() and suffix in ['.ass', '.ssa']:
                    is_disabled = True
                elif 'ssa' in item_text.lower() and suffix in ['.ass', '.ssa']:
                    is_disabled = True
                elif 'sub' in item_text.lower() and suffix in ['.sub', '.idx']:
                    is_disabled = True
                elif 'idx' in item_text.lower() and suffix in ['.sub', '.idx']:
                    is_disabled = True
                
                item = self.to_format_combo.model().item(i)
                if item:
                    item.setEnabled(not is_disabled)
    
    def _convert_subtitle(self):
        input_file = self.convert_file_edit.text()
        if not input_file:
            QMessageBox.warning(self, t("app.title"), t("convert.no_input_file"))
            return

        to_format = self.to_format_combo.currentText()
        video_file = self.convert_video_file_edit.text() if self.convert_video_group.isVisible() else None

        if self.convert_video_group.isVisible() and not video_file:
            QMessageBox.warning(self, t("app.title"), t("mkv.no_video_file"))
            return

        input_path = Path(input_file)
        default_output_name = input_path.stem + "." + to_format.lower().split('/')[0]
        output_file, _ = QFileDialog.getSaveFileName(self, t("convert.output_file"), default_output_name, f"{to_format} Files (*.{to_format.lower().split('/')[0]})")
        if not output_file:
            return

        try:
            self.sub_ctrl.convert_subtitle(Path(input_file), Path(output_file), video_file=Path(video_file) if video_file else None)
            notification_center.success(t("convert.success", path=output_file))
        except Exception as e:
            QMessageBox.critical(self, t("app.title"), t("convert.fail", error=str(e)))

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
                              keep=step.get("keep"), export_rel_idx=step.get("export_rel_idx"),
                              out_dir=step.get("out_dir"))

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

    # ---------- Persistenz ----------
    def closeEvent(self, event):
        try:
            settings_set_bytes("ui/main/geometry", bytes(self.saveGeometry()))
            settings_set_bytes("ui/main/state",    bytes(self.saveState()))
            if hasattr(self, "splitter"):
                settings_set_bytes("ui/main/splitter", bytes(self.splitter.saveState()))
        except Exception:
            pass
        super().closeEvent(event)

    # ---------- FFmpeg/ffprobe-Startprüfung ----------
    def _is_bundled_path(self, p: Path) -> bool:
        """
        Erkenne typische Pfade für gebündelte Binaries:
          - Pfade unter sys._MEIPASS (PyInstaller onefile)
          - unser Ressourcen-Ordner …/_internal/resources/ffmpeg/… (onedir)
        """
        try:
            p = p.resolve()
        except Exception:
            return False

        # PyInstaller onefile Temp-Verzeichnis
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and str(p).startswith(str(Path(meipass).resolve())):
            return True

        # onedir: Ressourcen-Ordner
        app_dir = Path(getattr(sys, "frozen", False) and sys.executable or sys.argv[0]).resolve().parent
        candidate = app_dir / "_internal" / "resources" / "ffmpeg"
        try:
            return str(p).startswith(str(candidate.resolve()))
        except Exception:
            return False

    def _is_valid_binary(self, path: Path) -> bool:
        """Sanity-Check für Custom-Pfade: existiert und liefert `-version` erfolgreich?"""
        try:
            if not path.exists():
                return False
            proc = subprocess.run([str(path), "-version"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL,
                                  timeout=5,
                                  check=False)
            return proc.returncode == 0
        except Exception:
            return False

    def _startup_check_ffmpeg(self) -> None:
        """
        Start-Check:
          - Wenn Custom-Pfade gesetzt sind: freundlich warnen, falls ungültig.
          - Wenn gar nichts gefunden wird: blockierend Settings öffnen.
          - KEIN System-Hinweis, wenn bundled benutzt wird oder der Nutzer "bundled bevorzugen" gewählt hat.
        """
        s = get_settings()
        custom_ffmpeg  = (s.value("path_ffmpeg",  "",  type=str) or "").strip()
        custom_ffprobe = (s.value("path_ffprobe", "",  type=str) or "").strip()
        prefer_bundled = bool(s.value("prefer_bundled", False, bool))
        has_custom     = bool(custom_ffmpeg or custom_ffprobe)

        # 1) Custom prüfen → bei Fehler direkt Einstellungen öffnen
        if has_custom:
            bad = []
            for name, p in (("ffmpeg", custom_ffmpeg), ("ffprobe", custom_ffprobe)):
                if p and not self._is_valid_binary(Path(p)):
                    bad.append(name)
            if bad:
                QMessageBox.warning(
                    self,
                    t("app.title"),
                    "Die gesetzten FFmpeg-Pfade scheinen ungültig zu sein: "
                    + ", ".join(bad) + ". Bitte in den Einstellungen prüfen."
                )
                self._open_settings()
                return

        ff = FfmpegService()

        # 2) Prüfen, ob FFmpeg/ffprobe überhaupt gefunden werden
        try:
            ff_path = Path(ff.find_ffbin("ffmpeg"))
            fp_path = Path(ff.find_ffbin("ffprobe"))
            if not ff_path.exists() or not fp_path.exists():
                raise FileNotFoundError
        except Exception:
            QMessageBox.critical(
                self,
                t("mw.ffmpeg.missing"),
                "FFmpeg/ffprobe konnte nicht gefunden werden.\n\n"
                "Bitte in den Einstellungen Pfade setzen oder die gebündelten Binaries verwenden."
            )
            self._open_settings()
            return

        # 3) Herkunft ermitteln (bundled/system/custom) und ggf. Hinweis unterdrücken
        origin = None
        if hasattr(ff, "detect_origin"):
            try:
                origin = ff.detect_origin()  # 'bundled' | 'system' | 'custom' | 'missing'
            except Exception:
                origin = None

        # Fallback: am Pfad erkennen
        if origin is None:
            origin = "bundled" if (self._is_bundled_path(ff_path) and self._is_bundled_path(fp_path)) else \
                     ("custom" if has_custom else "system")

        # Kein Hinweis, wenn bundled genutzt wird oder Nutzer bundled bevorzugt
        if origin == "bundled" or prefer_bundled:
            return

        # Kein Hinweis bei Custom
        if origin == "custom":
            return

        # Freundlicher Hinweis nur bei System
        msg = t("mw.ffmpeg.using.system")
        if msg == "mw.ffmpeg.using.system":
            msg = ("System-FFmpeg (PATH) wird verwendet. Für reproduzierbares Verhalten "
                   "kannst du gebündelte Binaries bevorzugen oder Custom-Pfade setzen.")
        notification_center.info(msg)
