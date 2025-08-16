# src/app/settings.py
from __future__ import annotations
from pathlib import Path
import json
import os

ORG = "KevNetwork"
APP = "VideoSubTool"

DEFAULT_URLS = {
    "windows": {"ffmpeg": "", "ffprobe": ""},
    "linux": {"ffmpeg": "", "ffprobe": ""},
}

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

    def value(self, key: str, default=None, type=None):  # noqa: A003 (shadow builtins)
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

def use_bundled_preferred() -> bool:
    s = get_settings()
    return bool(s.value("use_bundled", False, type=bool))

def custom_bin_path(name: str) -> str | None:
    s = get_settings()
    v = s.value(f"path_{name}", "", type=str)
    return v or None
