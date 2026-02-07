# src/app/controller/batch_controller.py
from __future__ import annotations
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, Signal, QThread, Qt

from app.view.workers.batch_worker import BatchWorker


class BatchController(QObject):
    """
    Startet/überwacht Batch-Operationen in einem QThread und
    leitet Fortschritt/Fehler/Fertig-Signale an die GUI weiter.

    Signals
    -------
    progress : (int percent, str current_file_name)
        Fortschritt in Prozent (0..100) und der aktuell verarbeitete Dateiname.
    finished : (int processed, int errors)
        Anzahl erfolgreich verarbeiteter Dateien und Fehleranzahl.
    error : (str message)
        Fehlermeldungen, die während der Verarbeitung auftreten.
    """

    progress = Signal(int, str)
    finished = Signal(int, int)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: BatchWorker | None = None

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #
    def start(
        self,
        files: List[Path],
        mode: str,
        keep: Optional[str],
        export_rel_idx: Optional[int],
        out_dir: Optional[Path] = None,
    ) -> None:
        """
        Startet eine neue Batch-Verarbeitung in einem Hintergrund-Thread.
        Beendet vorher ggf. einen laufenden Job.
        """
        self.stop()  # Sicherheitsstopp, falls noch etwas läuft

        # Thread + Worker anlegen
        thread = QThread(self)
        worker = BatchWorker(files=files, mode=mode, keep=keep, export_rel_idx=export_rel_idx, out_dir=out_dir)
        worker.moveToThread(thread)

        # Verbindungen
        thread.started.connect(worker.run, type=Qt.QueuedConnection)

        # 1) Fortschritt
        #    Unterstützt optional ein erweitertes Signal 'file_progress(int, str, int, int)' im Worker.
        #    Falls nicht vorhanden, fallback auf 'progress(int, str)'.
        if hasattr(type(worker), "file_progress"):
            # type: ignore[attr-defined] weil optional
            worker.file_progress.connect(self._on_worker_file_progress)  # type: ignore[attr-defined]
        if hasattr(type(worker), "progress"):
            worker.progress.connect(self.progress)

        # 2) Fehler & Fertig
        worker.error.connect(self.error)
        worker.finished.connect(self._on_worker_finished)

        # 3) Thread-Cleanup
        thread.finished.connect(thread.deleteLater)

        # Member merken (erst NACH erfolgreicher Initialisierung)
        self._thread = thread
        self._worker = worker

        # Start
        thread.start()

    def stop(self) -> None:
        """
        Stoppt einen laufenden Batch sauber (best effort).
        """
        if self._worker is not None:
            try:
                self._worker.stop()
            except Exception:
                pass

        if self._thread is not None:
            try:
                self._thread.quit()
                self._thread.wait()
            except Exception:
                pass

        self._thread = None
        self._worker = None

    # --------------------------------------------------------------------- #
    # Slots (Worker -> Controller)
    # --------------------------------------------------------------------- #
    def _on_worker_finished(self, processed: int, errors: int) -> None:
        """
        Vom Worker nach Abschluss aufgerufen.
        """
        self.finished.emit(processed, errors)
        self.stop()

    def _on_worker_file_progress(self, percent: int, name: str, index: int, total: int) -> None:
        """
        Optionaler Handler für ein erweitertes Worker-Signal:
        (per-file-percent, filename, currentIndex, totalFiles).
        Standardisiert auf das öffentliche progress-Signal (percent, name).
        """
        # Wenn du hier später globalen Fortschritt berechnen willst, kannst du
        # index/total nutzen. Aktuell leiten wir den Percent-Wert 1:1 weiter.
        self.progress.emit(percent, name)
