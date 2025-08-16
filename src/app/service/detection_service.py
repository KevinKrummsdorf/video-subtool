from __future__ import annotations

class DetectionService:
    """Heuristik zur Klassifikation von Untertiteln."""

    def classify_subtitle(self, title: str | None, language: str | None, forced: bool) -> str:
        if forced:
            return "forced"
        t = (title or "").lower()
        if any(k in t for k in ["forced", "zwang", "signs", "songs"]):
            return "forced"
        return "full"
