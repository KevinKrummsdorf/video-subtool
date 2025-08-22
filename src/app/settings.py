# src/app/settings.py
from __future__ import annotations
from pathlib import Path
import json
import os
import platform
from typing import Optional
import base64

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

_TRUE = {"1", "true", "yes", "on", "y", "t"}
_FALSE = {"0", "false", "no", "off", "n", "f"}


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
            # ACHTUNG: bool("false") wäre True -> daher unten settings_get_bool nutzen.
            if isinstance(val, bool):
                return val
            if isinstance(val, int):
                return val != 0
            if isinstance(val, str):
                low = val.strip().lower()
                if low in _TRUE:
                    return True
                if low in _FALSE:
                    return False
                # Fallback: unverändert lassen, damit Aufrufer entscheiden kann
                return default if isinstance(default, bool) else False
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

    def remove(self, key: str) -> None:
        if key in self._data:
            del self._data[key]
            try:
                self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass


_OBSOLETE_KEYS = ("last_folder",)


def _cleanup_obsolete(settings) -> None:
    for key in _OBSOLETE_KEYS:
        if hasattr(settings, "remove"):
            try:
                settings.remove(key)
            except Exception:
                pass


def get_settings():
    """
    Liefert ein Objekt mit .value(key, default, type=...) und .setValue(key, val)
    – entweder QSettings oder der Dateifallback.
    """
    if _QSETTINGS_AVAILABLE:
        # QSettings schreibt unter Windows in die Registry, unter Linux nach ~/.config
        s = QSettings(ORG, APP)  # type: ignore
    else:
        s = _DictSettings(_CFG_FILE)
    _cleanup_obsolete(s)
    return s


def app_data_dir() -> Path:
    return _CFG_DIR


# ---------------------- Bool-Helper ----------------------

def _parse_bool_like(v, default: bool = False) -> bool:
    """Robuste Interpretation von bools aus QSettings (bool, int, str)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v != 0
    if isinstance(v, str):
        val = v.strip().lower()
        if val in _TRUE:
            return True
        if val in _FALSE:
            return False
    return default


def settings_get_bool(key: str, default: bool = False) -> bool:
    s = get_settings()
    raw = s.value(key, None)  # bewusst ohne type=bool, damit Strings sichtbar bleiben
    return _parse_bool_like(raw, default)


def settings_set_bool(key: str, value: bool) -> None:
    get_settings().setValue(key, bool(value))


# ---------------------- Notify-Style ----------------------

def notify_style_default() -> str:
    """Return current notification style or default to "toast"."""
    s = get_settings()
    return s.value("notify_style", "toast", type=str) or "toast"


def set_notify_style(style: str) -> None:
    """Persist chosen notification style."""
    s = get_settings()
    if style not in ("statusbar", "dialog", "toast"):
        style = "toast"
    s.setValue("notify_style", style)


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
      - Setting 'prefer_bundled' (neuer Schlüssel) True ist, ODER
      - Setting 'use_bundled' (Alt) True ist, ODER
      - gar nichts gesetzt ist, aber (Windows) und Bundled-Binaries vorhanden sind.
    Sonst False.

    Wichtig: Strings wie "false"/"0" werden korrekt interpretiert.
    """
    s = get_settings()

    # Neuer Schlüssel hat Vorrang
    if (val := s.value("prefer_bundled", None)) is not None:
        return _parse_bool_like(val, False)

    # Abwärtskompatibel: alter Schlüssel
    if (val := s.value("use_bundled", None)) is not None:
        return _parse_bool_like(val, False)

    # Intelligenter Default (wenn nichts konfiguriert ist)
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


# --- Universelle Bytes-Helper (funktionieren mit QSettings und JSON-Fallback) ---

def settings_set_bytes(key: str, data: bytes) -> None:
    s = get_settings()
    try:
        # QSettings (PySide6) kann QByteArray/bytes direkt speichern
        s.setValue(key, data)
    except Exception:
        # Fallback-Datei: als Base64-String speichern
        s.setValue(key, base64.b64encode(data).decode("ascii"))


def settings_get_bytes(key: str) -> bytes | None:
    s = get_settings()
    val = s.value(key, None)
    if val is None:
        return None
    # QSettings gibt oft direkt QByteArray/bytes zurück
    if isinstance(val, (bytes, bytearray)):
        return bytes(val)
    if isinstance(val, str):
        # Fallback-Datei: Base64-String dekodieren
        try:
            return base64.b64decode(val)
        except Exception:
            return None
    return None
