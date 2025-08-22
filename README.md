# VideoSubTool

VideoSubTool is a **PySide6** GUI on top of FFmpeg/ffprobe for managing subtitles in video files.

## Features

- Load a folder and list video files
- Show subtitle streams
- Export the selected subtitle (SRT when possible, otherwise SUP)
- Remove subtitles and replace the original file
- Batch mode with progress dialog
- Settings dialog with language switch (DE/EN) and FFmpeg path selection
- FFmpeg finder order: custom → system PATH → bundled `resources/ffmpeg/<platform>/`

## Development Setup

### Prerequisites
- Python 3.12
- [Poetry](https://python-poetry.org/) installed and on PATH
- Windows: PowerShell 5+ or PowerShell 7+

### Install (development)
```bash
git clone https://github.com/KevinKrummsdorf/video-subtool.git
cd video-subtool
poetry install
poetry run video-subtool
```

## Build Instructions

The build is managed by **build.ps1** (PowerShell).  
You can choose between `release`, `debug`, `run`, and `clean`.

### Bundled FFmpeg (Windows)

If you want to ship FFmpeg with the app, place binaries here:
```
resources/ffmpeg/windows/ffmpeg.exe
resources/ffmpeg/windows/ffprobe.exe
```

### Release build (optimized GUI)
Default: fast onedir build
```powershell
.\build.ps1 -Task release
```
Optional: single-file build (slower startup, self-extracting EXE)
```powershell
.\build.ps1 -Task release -OneFile:$true
```
Artifacts appear in the `dist/` directory.

The build script auto-detects `resources/branding/icon.ico` (with fallbacks). Use `-Icon <path>` to override the icon.

### Debug build (console + verbose PyInstaller logs)

```powershell
.\build.ps1 -Task debug
```

### Run (development shortcut)

```powershell
.\build.ps1 -Task run
```

### Clean build artifacts

```powershell
.\build.ps1 -Task clean
```

## FFmpeg on Windows

This project uses [FFmpeg](https://ffmpeg.org/).

On Windows, an FFmpeg build from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) is bundled with the application.  
These builds are licensed under the [GPLv3](resources/LICENSES/FFmpeg/FFmpeg-GPLv3.txt).  

See additional information in [NOTICE.txt](resources/LICENSES/FFmpeg/NOTICE.txt).

## License

This project is released under the **MIT License**.  
See [LICENSE](LICENSE) for details.
