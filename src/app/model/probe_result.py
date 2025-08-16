from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List
from app.model.probe_stream import ProbeStream

@dataclass
class ProbeResult:
    path: Path
    streams: List[ProbeStream]
