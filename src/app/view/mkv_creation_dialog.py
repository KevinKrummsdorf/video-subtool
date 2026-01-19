from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QFileDialog,
    QListWidget, QListWidgetItem, QLabel, QComboBox, QGroupBox
)
from PySide6.QtCore import Qt
from pathlib import Path
from .. import i18n
from ..i18n import t

class MKVCreationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)

        # Video File Selection
        self.video_group = QGroupBox()
        video_layout = QHBoxLayout()
        self.video_file_edit = QLineEdit()
        self.browse_video_button = QPushButton()
        video_layout.addWidget(self.video_file_edit)
        video_layout.addWidget(self.browse_video_button)
        self.video_group.setLayout(video_layout)
        layout.addWidget(self.video_group)

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
        layout.addWidget(self.audio_group)

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
        layout.addWidget(self.subtitle_group)
        
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
        layout.addWidget(self.default_track_group)

        # Output File Selection
        self.output_group = QGroupBox()
        output_layout = QHBoxLayout()
        self.output_file_edit = QLineEdit()
        self.browse_output_button = QPushButton()
        output_layout.addWidget(self.output_file_edit)
        output_layout.addWidget(self.browse_output_button)
        self.output_group.setLayout(output_layout)
        layout.addWidget(self.output_group)

        # Create Button
        self.create_button = QPushButton()
        layout.addWidget(self.create_button)

        self.setLayout(layout)
        
        i18n.bus.language_changed.connect(self._retranslate)
        self._retranslate()

    def _retranslate(self):
        self.setWindowTitle(t("mkv.title"))
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
        self.create_button.setText(t("mkv.create_mkv"))
