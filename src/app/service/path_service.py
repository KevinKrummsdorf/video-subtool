from __future__ import annotations
from pathlib import Path
from typing import Optional


class PathService:
    """Resolve and store the application's current output folder."""

    def __init__(self) -> None:
        self._current: Optional[Path] = None

    def set_current_folder(self, folder: Path) -> None:
        """Set the current working folder (resolved)."""
        self._current = Path(folder).resolve()

    def get_output_folder(self) -> Path:
        """Return the configured output folder or fall back to app directory."""
        if self._current:
            return self._current
        return Path(__file__).resolve().parent


# global singleton
path_service = PathService()
