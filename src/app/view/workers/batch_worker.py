from __future__ import annotations
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

from app.controller.subtitle_controller import SubtitleController

class BatchWorker(QObject):
    """Hintergrund-Worker (nur Ausführung, keine UI)."""
    progress = Signal(int, str)     # percent, current file name
    finished = Signal(int, int)     # processed, errors
    error = Signal(str)

    def __init__(self, files: List[Path], mode: str, keep: Optional[str], export_rel_idx: Optional[int], out_dir: Optional[Path] = None):
        super().__init__()
        self.files = files
        self.mode = mode
        self.keep = keep
        self.export_rel_idx = export_rel_idx
        self.out_dir = out_dir
        self._stop = False
        self._ctrl = SubtitleController()

    def stop(self):
        self._stop = True

    def run(self):
        processed = 0
        errors = 0
        total = len(self.files)
        for i, f in enumerate(self.files, start=1):
            if self._stop:
                break
            try:
                self.progress.emit(int((i-1) / total * 100), f.name)
                if self.mode == "strip":
                    self._ctrl.strip_subs(f, keep=self.keep)
                else:
                    if self.export_rel_idx is not None:
                        self._ctrl.export_stream(f, self.export_rel_idx, out_dir=self.out_dir)
                    else:
                        # naive All-Subs-Export (0..9 versuchen)
                        for rel in range(0, 10):
                            try:
                                self._ctrl.export_stream(f, rel, out_dir=self.out_dir)
                            except Exception:
                                if rel == 0:
                                    break
                processed += 1
            except Exception as e:
                errors += 1
                self.error.emit(f"{f.name}: {e}")
            finally:
                self.progress.emit(int(i / total * 100), f.name)
        self.finished.emit(processed, errors)
