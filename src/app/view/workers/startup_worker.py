from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from app.service.ffmpeg_service import FfmpegService
from app.settings import use_bundled_preferred

class StartupWorker(QObject):
    progress = Signal(str)   # status text
    finished = Signal(object)  # result object or None
    failed = Signal(str)     # error message

    def __init__(self) -> None:
        super().__init__()
        self.result: Optional[dict] = None

    def run(self) -> None:
        try:
            self.progress.emit("Initialisiere Dienste…")
            ff = FfmpegService()

            self.progress.emit("Prüfe FFprobe…")
            ffprobe_path = ff.find_ffbin("ffprobe")

            self.progress.emit("Prüfe FFmpeg…")
            ffmpeg_path = ff.find_ffbin("ffmpeg")

            self.result = {
                "use_bundled": use_bundled_preferred(),
                "ffprobe": ffprobe_path,
                "ffmpeg": ffmpeg_path,
            }
            self.finished.emit(self.result)
        except Exception as e:
            self.failed.emit(str(e))
