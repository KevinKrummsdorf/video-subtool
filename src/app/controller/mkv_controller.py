from PySide6.QtWidgets import QFileDialog, QListWidgetItem, QMessageBox, QProgressDialog
from PySide6.QtCore import Qt
from pathlib import Path
from ..view.mkv_creation_dialog import MKVCreationDialog
from ..service.ffmpeg_service import FfmpegService
from ..i18n import t

class MKVController:
    def __init__(self, parent=None):
        self.view = MKVCreationDialog(parent)
        self._video_file = None
        self._audio_files = []
        self._subtitle_files = []
        self.ffmpeg_service = FfmpegService()

        self._connect_signals()

    def show(self):
        self.view.exec()
    
    def _connect_signals(self):
        self.view.browse_video_button.clicked.connect(self._browse_video)
        self.view.add_audio_button.clicked.connect(self._add_audio)
        self.view.remove_audio_button.clicked.connect(self._remove_audio)
        self.view.add_subtitle_button.clicked.connect(self._add_subtitle)
        self.view.remove_subtitle_button.clicked.connect(self._remove_subtitle)
        self.view.browse_output_button.clicked.connect(self._browse_output)
        self.view.create_button.clicked.connect(self._create_mkv)

    def _create_mkv(self):
        if not self._video_file:
            QMessageBox.warning(self.view, t("mkv.title"), t("mkv.no_video_file"))
            return

        output_path = self.view.output_file_edit.text()
        if not output_path:
            QMessageBox.warning(self.view, t("mkv.title"), t("mkv.no_output_file"))
            return
        output_file = Path(output_path)

        default_audio_index = self.view.default_audio_combo.currentData()
        default_subtitle_index = self.view.default_subtitle_combo.currentData()

        progress_dialog = QProgressDialog(t("mkv.create_mkv"), t("common.cancel"), 0, 100, self.view)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setAutoClose(True)
        progress_dialog.show()

        def on_progress(value):
            progress_dialog.setValue(value)

        try:
            self.ffmpeg_service.create_mkv(
                video_file=self._video_file,
                audio_files=self._audio_files,
                subtitle_files=self._subtitle_files,
                output_file=output_file,
                default_audio_index=default_audio_index if default_audio_index != -1 else None,
                default_subtitle_index=default_subtitle_index if default_subtitle_index != -1 else None,
                on_progress=on_progress,
            )
            progress_dialog.setValue(100)
            QMessageBox.information(self.view, t("mkv.title"), t("mkv.success", path=str(output_file)))
            self.view.accept()
        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(self.view, t("mkv.title"), t("mkv.fail", error=str(e)))

    def _browse_video(self):
        file, _ = QFileDialog.getOpenFileName(self.view, t("mkv.video_file"), "", "Video Files (*.mkv *.mp4 *.avi)")
        if file:
            self._video_file = Path(file)
            self.view.video_file_edit.setText(file)

    def _add_audio(self):
        files, _ = QFileDialog.getOpenFileNames(self.view, t("mkv.audio_files"), "", "Audio Files (*.m4a *.aac *.ac3 *.dts *.mp3)")
        for file in files:
            self._audio_files.append(Path(file))
            self.view.audio_list_widget.addItem(file)
        self._update_default_audio_combo()

    def _remove_audio(self):
        for item in self.view.audio_list_widget.selectedItems():
            self._audio_files.remove(Path(item.text()))
            self.view.audio_list_widget.takeItem(self.view.audio_list_widget.row(item))
        self._update_default_audio_combo()

    def _add_subtitle(self):
        files, _ = QFileDialog.getOpenFileNames(self.view, t("mkv.subtitle_files"), "", "Subtitle Files (*.srt *.ass *.sup)")
        for file in files:
            self._subtitle_files.append(Path(file))
            self.view.subtitle_list_widget.addItem(file)
        self._update_default_subtitle_combo()

    def _remove_subtitle(self):
        for item in self.view.subtitle_list_widget.selectedItems():
            self._subtitle_files.remove(Path(item.text()))
            self.view.subtitle_list_widget.takeItem(self.view.subtitle_list_widget.row(item))
        self._update_default_subtitle_combo()

    def _browse_output(self):
        file, _ = QFileDialog.getSaveFileName(self.view, t("mkv.output_file"), "", "MKV Files (*.mkv)")
        if file:
            self.view.output_file_edit.setText(file)

    def _update_default_audio_combo(self):
        self.view.default_audio_combo.clear()
        self.view.default_audio_combo.addItem("None", -1)
        for i, file in enumerate(self._audio_files):
            self.view.default_audio_combo.addItem(file.name, i)

    def _update_default_subtitle_combo(self):
        self.view.default_subtitle_combo.clear()
        self.view.default_subtitle_combo.addItem("None", -1)
        for i, file in enumerate(self._subtitle_files):
            self.view.default_subtitle_combo.addItem(file.name, i)
