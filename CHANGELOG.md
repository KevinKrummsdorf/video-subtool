# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Released]

## [0.4.0] - 2026-xx-xx
### Added
- New "Build" tab to create and edit MKV files.
    - Ability to add external audio and subtitle files to an MKV container.
    - Functionality to set the default audio and subtitle track.
- New "Convert" tab for subtitle format conversion (SRT <-> ASS/SSA, SRT <-> SUB/IDX).
    - Drag and drop support for the subtitle conversion input file.
    - The output format dropdown now disables the source format.
    - The save dialog for subtitle conversion now suggests a default filename.
- Default export directory logic:
    - If no custom target folder is specified, subtitles are exported to a `subs` directory in the executable's folder.
    - Added a "Series name" field to organize exports into subfolders (defaults to `unknown`).

### Changed
- UI refactored into "Export" and "Build" tabs for better organization.

### Fixed
n/a

---

## [0.3.0] - 2025-08-17
- Splash screen with controlled timing
- Responsive main window scaling
- Drag & drop support for files
- Centralized alert system (status bar / modal / toast) with user preference
- Bundled-FFmpeg preference control and About/credits updates
- Jellyfin language code mapping (ISO 639-2 → Jellyfin-friendly codes)
- Output folder behavior: write exports and processed videos to current working folder
- Settings/UX refinements (checkbox enable/disable, translations)
