from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ActionType = Literal["export", "remove"]

@dataclass
class Task:
    file: Path
    action: ActionType
    keep_kind: str | None = None
