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

## Development / Run

```bash
poetry install
poetry run video-subtool
```

## FFmpeg on Windows

The Windows distribution bundles FFmpeg. The included binaries are licensed separately; see `resources/LICENSES/FFmpeg` for details.

## License

Released under the MIT License.
