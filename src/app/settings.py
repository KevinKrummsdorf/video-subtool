# src/app/settings.py
from __future__ import annotations
from pathlib import Path
import json
import os
import platform
from typing import Optional

ORG = "KevNetwork"
APP = "VideoSubTool"

# --- Optional: QSettings verwenden, wenn PySide6 verfügbar ist ---
_QSETTINGS_AVAILABLE = False
try:
    from PySide6.QtCore import QSettings  # type: ignore
    _QSETTINGS_AVAILABLE = True
except Exception:
    QSettings = None  # type: ignore

# --- Fallback-Datei (wenn kein QSettings) ---
_CFG_DIR = Path.home() / f".{APP.lower()}"
_CFG_DIR.mkdir(parents=True, exist_ok=True)
_CFG_FILE = _CFG_DIR / "config.json"


class _DictSettings:
    """
    Kleiner Adapter, der ein QSettings-ähnliches Interface bietet.
    Wird genutzt, wenn PySide6/QSettings im Frozen-Binary nicht verfügbar ist.
    """
    def __init__(self, path: Path):
        self.path = path
        self._data: dict = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text("utf-8"))
            except Exception:
                self._data = {}

    def value(self, key: str, default=None, type=None):  # noqa: A003
        val = self._data.get(key, default)
        # einfache Typkonvertierung wie QSettings
        if type is bool:
            return bool(val)
        if type is int:
            try:
                return int(val)
            except Exception:
                return default
        if type is str:
            return "" if val is None else str(val)
        return val

    def setValue(self, key: str, val):
        self._data[key] = val
        try:
            self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


def get_settings():
    """
    Liefert ein Objekt mit .value(key, default, type=...) und .setValue(key, val)
    – entweder QSettings oder der Dateifallback.
    """
    if _QSETTINGS_AVAILABLE:
        # QSettings schreibt unter Windows in die Registry, unter Linux nach ~/.config
        return QSettings(ORG, APP)  # type: ignore
    return _DictSettings(_CFG_FILE)


def app_data_dir() -> Path:
    return _CFG_DIR


# ---------------------- Helpers für Bundled-FFmpeg ----------------------

def _project_root() -> Path:
    """
    Projektwurzel:
      - im PyInstaller-Build: sys._MEIPASS
      - im Dev: zwei Ordner über dieser Datei (…/src/app -> Projektroot)
    """
    import sys as _sys
    return Path(getattr(_sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def _bundled_ffmpeg_dir() -> Path:
    plat = "windows" if platform.system() == "Windows" else "linux"
    return _project_root() / "resources" / "ffmpeg" / plat


def _bundled_ffmpeg_paths() -> tuple[Path, Path]:
    d = _bundled_ffmpeg_dir()
    if platform.system() == "Windows":
        return d / "ffmpeg.exe", d / "ffprobe.exe"
    else:
        return d / "ffmpeg", d / "ffprobe"


def bundled_ffmpeg_available() -> bool:
    ffmpeg, ffprobe = _bundled_ffmpeg_paths()
    return ffmpeg.exists() and ffprobe.exists()


def use_bundled_preferred() -> bool:
    """
    True, wenn:
      - Setting 'use_bundled' explizit True ist, ODER
      - Setting noch NICHT gesetzt ist UND (Windows) UND Bundled-Binaries vorhanden sind.
    Sonst False.
    """
    s = get_settings()
    val = s.value("use_bundled", None)  # bewusst ohne type=bool -> None möglich
    if isinstance(val, bool):
        return val
    # intelligenter Default, falls Nutzer nichts gesetzt hat:
    if platform.system() == "Windows" and bundled_ffmpeg_available():
        return True
    return False


def custom_bin_path(name: str) -> Optional[str]:
    """
    Benutzerdefinierter Pfad (Einstellungen) – nur zurückgeben, wenn vorhanden.
    """
    s = get_settings()
    v = s.value(f"path_{name}", "", type=str) or ""
    v = v.strip()
    return v if v and Path(v).exists() else None
