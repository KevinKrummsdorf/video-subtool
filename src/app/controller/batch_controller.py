from __future__ import annotations
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, Signal, QThread

from app.view.workers.batch_worker import BatchWorker

class BatchController(QObject):
    """Startet/überwacht Batch-Operationen in einem QThread."""
    progress = Signal(int, str)     # percent, current file name
    finished = Signal(int, int)     # processed, errors
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: BatchWorker | None = None

    def start(self, files: List[Path], mode: str, keep: Optional[str], export_rel_idx: Optional[int]):
        self.stop()  # Sicherheit, falls noch läuft
        self._thread = QThread(self)
        self._worker = BatchWorker(files=files, mode=mode, keep=keep, export_rel_idx=export_rel_idx)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress)
        self._worker.error.connect(self.error)
        self._worker.finished.connect(self._on_worker_finished)

        self._thread.start()

    def stop(self):
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None

    def _on_worker_finished(self, processed: int, errors: int):
        self.finished.emit(processed, errors)
        self.stop()
