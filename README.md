# VideoSubTool (strict MVC)

PySide6-GUI zum:
- Ordner laden und Videodateien auflisten
- Untertitel-Streams anzeigen
- Ausgewählten Sub exportieren (SRT wenn möglich, sonst .sup)
- Untertitel entfernen und **Originaldatei ersetzen**
- **Batch**-Modus mit Fortschrittsdialog
- **Einstellungsdialog** inkl. **Sprachumschaltung (DE/EN)** und FFmpeg-Pfade
- **FFmpeg-Finder**: Custom → System `PATH` → Bundled `resources/ffmpeg/<platform>/`

## Dev-Setup

```bash
poetry install
poetry run video-subtool
