# src/app/model/lang_codes.py
from __future__ import annotations
from typing import Optional, Dict


class LangNormalizer:
    """
    Normalisiert Sprachcodes für Medien-Dateien (Jellyfin-kompatibel).
    - Bevorzugt ISO-639-1 (2-Buchstaben), z. B. 'de', 'en', 'ja'
    - Lässt BCP-47-Tags (mit Region) wie 'pt-BR' bestehen
    - Fällt auf vorhandene 3-Buchstaben-Codes zurück, wenn kein 2er-Mapping existiert
    - 'und' (undetermined), falls nichts erkannt werden kann
    """

    # 3-letter -> 2-letter (inkl. Alias-Varianten wie 'ger'->'de')
    _MAP_3_TO_2: Dict[str, str] = {
        "eng": "en", "deu": "de", "ger": "de", "fra": "fr", "fre": "fr", "spa": "es",
        "ita": "it", "nld": "nl", "dut": "nl", "por": "pt", "rus": "ru", "jpn": "ja",
        "zho": "zh", "chi": "zh", "kor": "ko", "ara": "ar", "pol": "pl", "tur": "tr",
        "ces": "cs", "cze": "cs", "hun": "hu", "ukr": "uk", "ron": "ro", "rum": "ro",
        "ell": "el", "gre": "el", "heb": "he", "hin": "hi", "ben": "bn", "tam": "ta",
        "tha": "th", "vie": "vi", "swe": "sv", "nor": "no", "dan": "da", "fin": "fi",
        "srp": "sr", "hrv": "hr", "bos": "bs", "cat": "ca", "isl": "is", "ind": "id",
        "msa": "ms", "aze": "az", "kat": "ka", "geo": "ka", "kaz": "kk", "lit": "lt",
        "lav": "lv", "est": "et", "eus": "eu", "glg": "gl", "slv": "sl", "slk": "sk",
    }

    # Heuristiken auf Titel/Handler-Name, wenn language-Tag fehlt
    _TITLE_HINTS: Dict[str, str] = {
        "german": "de", "deutsch": "de", "ger": "de", "deu": "de",
        "english": "en", "eng": "en",
        "japanese": "ja", "jpn": "ja", "jap": "ja",
        "french": "fr", "fra": "fr", "fre": "fr",
        "spanish": "es", "spa": "es", "español": "es",
        "italian": "it", "ita": "it",
        "russian": "ru", "rus": "ru",
        "chinese": "zh", "zho": "zh", "chi": "zh",
        "korean": "ko", "kor": "ko",
    }

    @staticmethod
    def _clean(s: str) -> str:
        return s.strip().replace("_", "-").lower()

    @classmethod
    def guess_from_title(cls, title: Optional[str]) -> Optional[str]:
        if not title:
            return None
        t = cls._clean(title)
        for key, val in cls._TITLE_HINTS.items():
            if key in t:
                return val
        return None

    @classmethod
    def normalize(cls, lang: Optional[str], title: Optional[str]) -> str:
        """
        Gibt einen Jellyfin-freundlichen Code zurück:
        - 2-Buchstaben, wenn möglich (oder Region wie 'pt-br')
        - sonst vorhandenen 3-Buchstaben-Code
        - sonst 'und'
        """
        if lang:
            l = cls._clean(lang)
            # Bereits 2er-Code oder BCP-47 mit Region?
            if len(l) == 2 or "-" in l:
                return l
            # 3er-Code -> Mapping versuchen
            if len(l) == 3 and l in cls._MAP_3_TO_2:
                return cls._MAP_3_TO_2[l]
            return l  # unbekanntes 3er-Label, aber wenigstens besser als 'und'

        # Fallback: aus dem Titel erraten
        guess = cls.guess_from_title(title)
        return guess if guess else "und"
