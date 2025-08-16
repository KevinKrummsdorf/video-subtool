from __future__ import annotations
from dataclasses import dataclass

@dataclass
class ProbeStream:
    index: int
    codec_type: str
    codec_name: str | None
    language: str | None
    title: str | None
    forced: bool
    default: bool
