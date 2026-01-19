from __future__ import annotations
from typing import Dict, Optional
import locale

from PySide6.QtCore import QObject, Signal
from app.settings import get_settings


# ---------- Events ----------
class _I18nBus(QObject):
    language_changed = Signal(str)  # "de" | "en"
bus = _I18nBus()


# ---------- Strings ----------
_STRINGS: Dict[str, Dict[str, str]] = {
    "de": {
        # App / Common
        "app.title": "VideoSubTool",
        "common.ok": "OK",
        "common.cancel": "Abbrechen",
        "common.save": "Speichern",
        "common.settings": "Einstellungen",
        "common.folder.choose": "Ordner wählen",
        "common.folder.open": "Ordner öffnen…",
        "common.about": "Über…",
        "common.batch": "Batch-Verarbeitung",
        "common.processing.files": "Verarbeite Dateien…",
        "common.processing": "Verarbeite: {name}",
        "common.done": "Batch abgeschlossen",
        "common.done.processed": "Verarbeitet",
        "common.done.errors": "Fehler",

        # Datei-Menü Actions
        "mw.export.selected": "Ausgewählten Sub exportieren",
        "mw.batch.export": "Batch: Subs exportieren (ganzer Ordner)",
        "mw.strip.replace": "Subs entfernen & Original ersetzen",
        "mw.batch.strip": "Batch: Subs entfernen (ganzer Ordner)",

        #Listen-Operationen
        "mw.remove.selected": "Ausgewählte entfernen",
        "mw.clear.list": "Liste leeren",

        # Menüs
        "menu.file": "&Datei",
        "menu.settings": "&Einstellungen",
        "menu.help": "&Hilfe",

        # Main Window – Labels
        "mw.no.folder": "Kein Ordner gewählt",
        "mw.current.folder": "Aktueller Ordner",
        "mw.video.files": "Videodateien:",
        "mw.streams.in.video": "Streams im ausgewählten Video:",
        "mw.remove.selected": "Ausgewählte entfernen",
        "mw.clear.list": "Liste leeren",

        # Keep-Options (Dropdown)
        "mw.keep.forced": "nur Forced behalten",
        "mw.keep.full": "nur Full behalten",

        # Neue Options-Variante (Checkboxen)
        "mw.opt.export_selected": "Ausgewählten Sub exportieren",
        "mw.opt.strip_with_rule": "Subs entfernen / Original ersetzen (Regel unten)",
        "mw.opt.remove_all": "Alle Untertitel entfernen",
        "mw.opt.custom_export_dir": "Eigenen Zielordner verwenden",
        "mw.opt.apply_to_folder": "Auf gesamten Ordner anwenden (Batch)",
        "mw.start": "Start",
        "mw.create_mkv": "MKV erstellen",

        # Meldungen / Fehler
        "mw.ffmpeg.missing": "FFmpeg/ffprobe fehlt",
        "mw.analyze.error": "Fehler beim Analysieren",
        "mw.pick.video.first": "Bitte zuerst ein Video wählen.",
        "mw.pick.subtitle.first": "Bitte einen Untertitel-Stream auswählen.",
        "mw.export.failed": "Export fehlgeschlagen",
        "mw.replaced": "Ersetzt: {name}",
        "mw.exported": "Exportiert: {path}",
        "mw.export.done.title": "Export abgeschlossen",
        "mw.export.done.msg": "Die Untertitel wurden erfolgreich exportiert.",
        "mw.export.fail.title": "Export fehlgeschlagen",
        "mw.export.fail.msg": "Beim Export der Untertitel ist ein Fehler aufgetreten.",
        "mw.remove.done.title": "Entfernen abgeschlossen",
        "mw.remove.done.msg": "Die Untertitel wurden erfolgreich entfernt.",
        "mw.remove.fail.title": "Entfernen fehlgeschlagen",
        "mw.remove.fail.msg": "Beim Entfernen der Untertitel ist ein Fehler aufgetreten.",
        "mw.batch.done.title": "Batch abgeschlossen",
        "mw.batch.done.msg": "Alle Dateien wurden erfolgreich verarbeitet ({processed}).",
        "mw.batch.done.partial": "Batch abgeschlossen: {processed} Dateien verarbeitet, {errors} Fehler.",
        "mw.batch.fail.title": "Batch-Fehler",
        "mw.batch.confirm.strip.title": "Batch bestätigen",
        "mw.batch.confirm.strip.text": "Für **alle** Videos im Ordner Untertitel entfernen und Originale ersetzen?\nDie Aktion ist nicht ohne weiteres rückgängig zu machen.",
        "mw.no.videos": "Kein Video im Ordner gefunden.",
        "mw.about.text": "VideoSubTool – ffmpeg/ffprobe GUI\n• Untertitel anzeigen/exportieren\n• Subs entfernen & Original ersetzen\nLizenzhinweise in resources/LICENSES/",

        # Tabelle
        "tbl.abs": "Abs-Idx",
        "tbl.rel": "Rel-Idx (s)",
        "tbl.codec": "Codec",
        "tbl.lang": "Lang",
        "tbl.title": "Title",
        "tbl.class": "Class",
        "tbl.default": "Default",

        # Dialoge
        "dlg.strip.confirm": "Untertitel werden entfernt und die Originaldatei ersetzt. Fortfahren?",

        # Settings
        "sd.title": "Einstellungen",
        "sd.use.bundled": "Bevorzugt mitgelieferte FFmpeg-Binaries verwenden (falls vorhanden)",
        "sd.ffmpeg.path": "Pfad zu ffmpeg:",
        "sd.ffprobe.path": "Pfad zu ffprobe:",
        "sd.pick.file": "Datei wählen",
        "sd.saved": "Einstellungen gespeichert.",
        "sd.lang": "Sprache:",
        "sd.lang.de": "Deutsch",
        "sd.lang.en": "Englisch",
        "sd.notify.title": "Benachrichtigungen",
        "sd.notify.statusbar": "StatusBar-Nachrichten",
        "sd.notify.dialog": "Dialogfenster (Alerts)",
        "sd.notify.toast": "Toast/Overlay",
        "toast.exported": "Exportiert: {path}",
        "toast.replaced": "Ersetzt: {name}",

        # About-Dialog
        "about.title": "Über …",
        "about.head": "VideoSubTool <span style='opacity:.7'>by</span> <b>Kevin Krummsdorf</b>",
        "about.features": (
        "<ul style='margin-top:8px'>"
        "<li>Untertitel <b>analysieren</b> (ffprobe)</li>"
        "<li>Subs <b>exportieren</b> (SRT/SUP)</li>"
        "<li>Subs <b>entfernen</b> &amp; Datei <b>verlustfrei remuxen</b></li>"
        "<li>Batch-Verarbeitung ganzer Ordner</li>"
        "</ul>"
        ),
        "about.ffmpeg.win": (
        "<p style='margin-top:4px'>Dieses Programm nutzt "
        "<a href='https://ffmpeg.org/'>FFmpeg</a>. "
        "Unter Windows wird FFmpeg <b>mitgeliefert</b> "
        "auf Basis der Builds von "
        "<a href='https://github.com/BtbN/FFmpeg-Builds'>BtbN/FFmpeg-Builds</a>. "
        "Alternativ kann in den Einstellungen ein System-FFmpeg gewählt werden.</p>"
        ),
        "about.ffmpeg.linux": (
        "<p style='margin-top:4px'>Dieses Programm nutzt "
        "<a href='https://ffmpeg.org/'>FFmpeg</a>. "
        "Unter Linux wird standardmäßig das <b>systemweite</b> FFmpeg genutzt "
        "(oder ein in den Einstellungen gesetzter Pfad).</p>"
        ),
        "about.licenses": "Lizenzhinweise",
        "about.website": "Website",
        "about.source": "Source &amp; Issues",
        "about.appdata": "App-Daten:",

        # MKV Creator Dialog
        "mkv.title": "MKV Creator",
        "mkv.video_file": "Videodatei",
        "mkv.audio_files": "Audiodateien",
        "mkv.subtitle_files": "Untertiteldateien",
        "mkv.add_audio": "Audio hinzufügen...",
        "mkv.add_subtitle": "Untertitel hinzufügen...",
        "mkv.remove_selected": "Ausgewählte entfernen",
        "mkv.default_tracks": "Standardspuren",
        "mkv.default_audio": "Standard-Audio:",
        "mkv.default_subtitle": "Standard-Untertitel:",
        "mkv.output_file": "Zieldatei",
        "mkv.browse": "Durchsuchen...",
        "mkv.create_mkv": "MKV erstellen",
        "mkv.success": "MKV-Datei erfolgreich erstellt unter {path}",
        "mkv.fail": "MKV-Datei konnte nicht erstellt werden: {error}",
        "mkv.no_video_file": "Bitte wählen Sie eine Videodatei aus.",
        "mkv.no_output_file": "Bitte geben Sie eine Zieldatei an.",
    },
    "en": {
        # App / Common
        "app.title": "VideoSubTool",
        "common.ok": "OK",
        "common.cancel": "Cancel",
        "common.save": "Save",
        "common.settings": "Settings",
        "common.folder.choose": "Choose Folder",
        "common.folder.open": "Open Folder…",
        "common.about": "About…",
        "common.batch": "Batch Processing",
        "common.processing.files": "Processing files…",
        "common.processing": "Processing: {name}",
        "common.done": "Batch finished",
        "common.done.processed": "Processed",
        "common.done.errors": "Errors",

        #File menu actions
        "mw.export.selected": "Export selected subtitle",
        "mw.batch.export": "Batch: export subs (entire folder)",
        "mw.strip.replace": "Remove subs & replace original",
        "mw.batch.strip": "Batch: remove subs (entire folder)",

        # List operations
        "mw.remove.selected": "Remove selected",
        "mw.clear.list": "Clear list",

        # Menus
        "menu.file": "&File",
        "menu.settings": "&Settings",
        "menu.help": "&Help",

        # Main Window – Labels
        "mw.no.folder": "No folder selected",
        "mw.current.folder": "Current folder",
        "mw.video.files": "Video files:",
        "mw.streams.in.video": "Streams in selected video:",
        "mw.remove.selected": "Remove selected",
        "mw.clear.list": "Clear list",

        # Keep-Options (Dropdown)
        "mw.keep.forced": "keep forced only",
        "mw.keep.full": "keep full only",

        # New options (checkbox style)
        "mw.opt.export_selected": "Export selected subtitle",
        "mw.opt.strip_with_rule": "Remove subs & replace original (rule below)",
        "mw.opt.remove_all": "Remove all subtitles",
        "mw.opt.custom_export_dir": "Use custom target folder",
        "mw.opt.apply_to_folder": "Apply to entire folder (batch)",
        "mw.start": "Start",
        "mw.create_mkv": "Create MKV",

        # Messages / Errors
        "mw.ffmpeg.missing": "FFmpeg/ffprobe missing",
        "mw.analyze.error": "Error while analyzing",
        "mw.pick.video.first": "Please select a video first.",
        "mw.pick.subtitle.first": "Please select a subtitle stream.",
        "mw.export.failed": "Export failed",
        "mw.replaced": "Replaced: {name}",
        "mw.exported": "Exported: {path}",
        "mw.export.done.title": "Export complete",
        "mw.export.done.msg": "Subtitles were exported successfully.",
        "mw.export.fail.title": "Export failed",
        "mw.export.fail.msg": "An error occurred while exporting subtitles.",
        "mw.remove.done.title": "Removal complete",
        "mw.remove.done.msg": "Subtitles were removed successfully.",
        "mw.remove.fail.title": "Removal failed",
        "mw.remove.fail.msg": "An error occurred while removing subtitles.",
        "mw.batch.done.title": "Batch complete",
        "mw.batch.done.msg": "All files processed successfully ({processed}).",
        "mw.batch.done.partial": "Batch finished: {processed} files processed, {errors} errors.",
        "mw.batch.fail.title": "Batch error",
        "mw.batch.confirm.strip.title": "Confirm batch",
        "mw.batch.confirm.strip.text": "Remove subtitles and replace originals for **all** videos in the folder?\nThis action cannot be undone easily.",
        "mw.no.videos": "No videos found in the folder.",
        "mw.about.text": "VideoSubTool – ffmpeg/ffprobe GUI\n• Show/export subtitles\n• Remove subs & replace original\nLicense notes in resources/LICENSES/",

        # Table
        "tbl.abs": "Abs-Idx",
        "tbl.rel": "Rel-Idx (s)",
        "tbl.codec": "Codec",
        "tbl.lang": "Lang",
        "tbl.title": "Title",
        "tbl.class": "Class",
        "tbl.default": "Default",

        # Dialogs
        "dlg.strip.confirm": "Subtitles will be removed and the original file will be replaced. Continue?",

        # Settings
        "sd.title": "Settings",
        "sd.use.bundled": "Prefer bundled FFmpeg binaries (if available)",
        "sd.ffmpeg.path": "Path to ffmpeg:",
          "sd.ffprobe.path": "Path to ffprobe:",
          "sd.pick.file": "Choose file",
          "sd.saved": "Settings saved.",
          "sd.lang": "Language:",
          "sd.lang.de": "German",
          "sd.lang.en": "English",
          "sd.notify.title": "Notifications",
          "sd.notify.statusbar": "StatusBar messages",
          "sd.notify.dialog": "Dialog windows (alerts)",
          "sd.notify.toast": "Toast/Overlay",

          "toast.exported": "Exported: {path}",
          "toast.replaced": "Replaced: {name}",

        # About-Dialog
        "about.title": "About …",
        "about.head": "VideoSubTool <span style='opacity:.7'>by</span> <b>Kevin Krummsdorf</b>",
        "about.features": (
        "<ul style='margin-top:8px'>"
        "<li><b>Analyze</b> subtitles (ffprobe)</li>"
        "<li><b>Export</b> subs (SRT/SUP)</li>"
        "<li><b>Remove</b> subs &amp; <b>losslessly remux</b> file</li>"
        "<li>Batch processing of whole folders</li>"
        "</ul>"
        ),
        "about.ffmpeg.win": (
        "<p style='margin-top:4px'>This program uses "
        "<a href='https://ffmpeg.org/'>FFmpeg</a>. "
        "On Windows, FFmpeg is <b>bundled</b> "
        "based on builds from "
        "<a href='https://github.com/BtbN/FFmpeg-Builds'>BtbN/FFmpeg-Builds</a>. "
        "Alternatively, you can configure a system-wide FFmpeg in Settings.</p>"
        ),
        "about.ffmpeg.linux": (
        "<p style='margin-top:4px'>This program uses "
        "<a href='https://ffmpeg.org/'>FFmpeg</a>. "
        "On Linux, the <b>system-wide</b> FFmpeg is used by default "
        "(or a path set in Settings).</p>"
        ),
    "about.licenses": "License notes",
    "about.website": "Website",
    "about.source": "Source &amp; Issues",
    "about.appdata": "App data:",

    # MKV Creator Dialog
    "mkv.title": "MKV Creator",
    "mkv.video_file": "Video File",
    "mkv.audio_files": "Audio Files",
    "mkv.subtitle_files": "Subtitle Files",
    "mkv.add_audio": "Add Audio...",
    "mkv.add_subtitle": "Add Subtitles...",
    "mkv.remove_selected": "Remove Selected",
    "mkv.default_tracks": "Default Tracks",
    "mkv.default_audio": "Default Audio:",
    "mkv.default_subtitle": "Default Subtitle:",
    "mkv.output_file": "Output File",
    "mkv.browse": "Browse...",
    "mkv.create_mkv": "Create MKV",
    "mkv.success": "MKV file created successfully at {path}",
    "mkv.fail": "Failed to create MKV file: {error}",
    "mkv.no_video_file": "Please select a video file.",
    "mkv.no_output_file": "Please specify an output file.",
    }
}

# ---------- Sprache wählen & Fallback ----------
def _lang_from_system() -> str:
    """
    Versuch, die Systemsprache zu ermitteln. Rückgabe 'de' oder 'en'.
    Fällt auf 'de' zurück, wenn nichts Sinnvolles ermittelt werden kann.
    """
    try:
        # Python 3.12: getlocale() ist ok; Value wie ('de_DE', 'UTF-8')
        loc = locale.getlocale()[0] or ""
    except Exception:
        try:
            loc = locale.getdefaultlocale()[0] or ""  # falls verfügbar
        except Exception:
            loc = ""

    loc = loc.lower()
    if loc.startswith("de"):
        return "de"
    # alles andere → en
    return "en"


def _lang_default() -> str:
    """Settings → sonst Systemlocale → 'de'."""
    s = get_settings()
    val = s.value("language", "", type=str)
    if val:
        return "de" if val == "de" else "en"
    return _lang_from_system()


_current_lang = _lang_default()


# ---------- API ----------
def t(key: str, **kwargs) -> str:
    """
    Hole Übersetzung für 'key' in aktueller Sprache, fällt auf Englisch zurück,
    dann auf den Schlüssel selbst. Optionales .format(**kwargs).
    """
    bundle = _STRINGS.get(_current_lang, {})
    txt: Optional[str] = bundle.get(key)
    if txt is None:
        txt = _STRINGS["en"].get(key, key)
    if kwargs:
        try:
            return txt.format(**kwargs)
        except Exception:
            return txt
    return txt


def set_language(lang: str):
    """Setzt Sprache ('de'|'en'), speichert in Settings und feuert Event."""
    global _current_lang
    lang = "de" if lang == "de" else "en"
    if lang == _current_lang:
        return
    _current_lang = lang
    s = get_settings()
    s.setValue("language", lang)
    bus.language_changed.emit(lang)


def current_language() -> str:
    return _current_lang


def available_languages() -> Dict[str, str]:
    """z. B. für Comboboxen: {'de': 'Deutsch', 'en': 'English'}"""
    return {"de": _STRINGS["de"]["sd.lang.de"], "en": _STRINGS["en"]["sd.lang.en"]}


