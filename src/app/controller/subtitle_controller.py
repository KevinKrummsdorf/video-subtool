# src/app/controller/subtitle_controller.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Optional

from app.model.video_item import VideoItem, is_video
from app.service.ffmpeg_service import FfmpegService
from app.service.detection_service import DetectionService
from app.model.probe_result import ProbeResult

class SubtitleController:
    """Controller für Einzelfunktionen (Scannen, Tabellen-Daten, Export/Strip)."""

    def __init__(self, ffmpeg: FfmpegService | None = None, detect: DetectionService | None = None):
        self.ffmpeg = ffmpeg or FfmpegService()
        self.detect = detect or DetectionService()

    def scan_folder(self, folder: Path) -> List[VideoItem]:
        items: List[VideoItem] = []
        for p in sorted(folder.iterdir()):
            if p.is_file() and is_video(p):
                items.append(VideoItem(path=p))
        return items

    def probe_file(self, file: Path) -> ProbeResult:
        return self.ffmpeg.probe_file(file)

    def get_stream_table(self, file: Path) -> List[Tuple]:
        pr = self.ffmpeg.probe_file(file)
        rows = []
        sub_idx = -1
        for s in pr.streams:
            if s.codec_type == "subtitle":
                sub_idx += 1
                cls = self.detect.classify_subtitle(s.title, s.language, s.forced)
                rows.append((
                    s.index,
                    sub_idx,                       # relativer Subindex
                    s.codec_name or "",
                    s.language or "",
                    s.title or "",
                    cls,
                    "yes" if s.default else "no"
                ))
        return rows

    def export_stream(self, file: Path, rel_sub_index: int, out_dir: Path) -> Path:
        return self.ffmpeg.export_subtitle(file, rel_sub_index, out_dir)

    def strip_subs(self, file: Path, keep: Optional[str]) -> Path:
        keep_kinds = [keep] if keep else None
        return self.ffmpeg.remove_subtitles_and_replace(file, keep_kinds=keep_kinds)
