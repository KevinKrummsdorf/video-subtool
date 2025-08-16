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

This project uses [FFmpeg](https://ffmpeg.org/).

On Windows, an FFmpeg build from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) is bundled with the application.  
These builds are licensed under the [GPLv3](resources/LICENSES/FFmpeg/FFmpeg-GPLv3.txt).  

See additional information in [NOTICE.txt](resources/LICENSES/FFmpeg/NOTICE.txt).


## License

Released under the MIT License.
