from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass
class VideoItem:
    path: Path

SUPPORTED_EXT = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".webm"}

def is_video(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXT
