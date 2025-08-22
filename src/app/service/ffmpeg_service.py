from __future__ import annotations
import json
import os
import platform
import shutil
import subprocess
import sys
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from app.settings import custom_bin_path, use_bundled_preferred
from app.model.probe_result import ProbeResult
from app.model.probe_stream import ProbeStream


_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")  # HH:MM:SS(.ms)


def _time_to_seconds(h: str, m: str, s: str) -> float:
    return int(h) * 3600 + int(m) * 60 + float(s)


class FfmpegService:
    """Kapselt Aufrufe von ffprobe/ffmpeg, inkl. Progress-Parsing."""

    # --------- Binärsuche ---------

    def _bundle_dir(self) -> Path:
        return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))

    def _vendor_ffbin(self, name: str) -> Optional[Path]:
        plat = "windows" if platform.system() == "Windows" else "linux"
        exe = name + (".exe" if plat == "windows" else "")
        candidate = self._bundle_dir() / "resources" / "ffmpeg" / plat / exe
        return candidate if candidate.exists() else None

    def _chmod_exec(self, p: Path):
        try:
            os.chmod(p, 0o755)
        except Exception:
            pass

    def find_ffbin(self, name: str) -> str:
        custom = custom_bin_path(name)
        if custom and Path(custom).exists():
            return custom

        prefer_bundled = use_bundled_preferred()
        if prefer_bundled:
            vend = self._vendor_ffbin(name)
            if vend:
                self._chmod_exec(vend)
                return str(vend)
            sysbin = shutil.which(name)
            if sysbin:
                return sysbin
        else:
            sysbin = shutil.which(name)
            if sysbin:
                return sysbin
            vend = self._vendor_ffbin(name)
            if vend:
                self._chmod_exec(vend)
                return str(vend)

        raise FileNotFoundError(
            f"{name} nicht gefunden. Setze Pfad in den Einstellungen, "
            f"installiere es systemweit oder lege es unter resources/ffmpeg/<platform>/ ab."
        )

    # --------- ffprobe ---------

    def run_ffprobe(self, file: Path) -> Dict[str, Any]:
        ffprobe = self.find_ffbin("ffprobe")
        cmd = [ffprobe, "-v", "error", "-show_streams", "-print_format", "json", str(file)]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return json.loads(out)

    def probe_duration_seconds(self, file: Path) -> Optional[float]:
        """
        Holt die Container-Dauer in Sekunden (float). Kann None sein (z.B. bei kaputten Dateien).
        """
        ffprobe = self.find_ffbin("ffprobe")
        cmd = [
            ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nk=1:nw=1",
            str(file)
        ]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            txt = out.decode("utf-8", "ignore").strip()
            if txt:
                return float(txt)
        except Exception:
            pass
        return None

    def parse_streams(self, ffprobe_json: Dict[str, Any]) -> List[ProbeStream]:
        result: List[ProbeStream] = []
        for s in ffprobe_json.get("streams", []):
            ctype = s.get("codec_type")
            if not ctype:
                continue
            tags = s.get("tags", {}) or {}
            result.append(ProbeStream(
                index=int(s.get("index", -1)),
                codec_type=ctype,
                codec_name=s.get("codec_name"),
                language=tags.get("language") or tags.get("LANGUAGE"),
                title=tags.get("title") or tags.get("TITLE"),
                forced=str(s.get("disposition", {}).get("forced", 0)) == "1",
                default=str(s.get("disposition", {}).get("default", 0)) == "1",
            ))
        return result

    def probe_file(self, file: Path) -> ProbeResult:
        data = self.run_ffprobe(file)
        return ProbeResult(path=file, streams=self.parse_streams(data))

    # --------- Utilities ---------

    def _ffmpeg_type_letter(self, codec_type: str) -> str:
        return {"video": "v", "audio": "a", "subtitle": "s", "data": "d", "attachment": "t"}.get(codec_type, "d")

    def _relative_index_for_type(self, pr: ProbeResult, abs_index: int, codec_type: str) -> int:
        i = -1
        for s in pr.streams:
            if s.codec_type == codec_type:
                i += 1
            if s.index == abs_index:
                return i
        return 0

    def _build_non_sub_maps(self, pr: ProbeResult) -> List[str]:
        maps: List[str] = []
        for s in pr.streams:
            if s.codec_type != "subtitle":
                rel = self._relative_index_for_type(pr, s.index, s.codec_type)
                maps.append(f"0:{self._ffmpeg_type_letter(s.codec_type)}:{rel}")
        return maps

    # --------- Gemeinsame ffmpeg-Runner mit Progress ---------

    def _run_ffmpeg_with_progress(
        self,
        cmd: List[str],
        input_file: Optional[Path],
        on_progress: Optional[Callable[[int], None]] = None
    ) -> None:
        """
        Führt ffmpeg aus und parst Fortschritt aus stderr. Berechnet % anhand der Container-Dauer.
        Ruft on_progress(%) wiederholt auf (0..100).
        """
        total = None
        if input_file is not None:
            total = self.probe_duration_seconds(input_file)
            # Falls ffprobe keine Dauer liefert, arbeiten wir ohne echte % und melden nur 0/100.

        # ffmpeg loggt Fortschritt nach stderr
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace"
        )

        last_reported = -1
        try:
            if on_progress and total:
                on_progress(0)

            if proc.stderr:
                for line in proc.stderr:
                    # Beispiel: "... time=00:00:05.12 ..."
                    m = _TIME_RE.search(line)
                    if m and total and total > 0:
                        cur = _time_to_seconds(m.group(1), m.group(2), m.group(3))
                        pct = max(0, min(100, int(cur / total * 100)))
                        # ffmpeg kann „über das Ende hinaus“ loggen; clamp + vermeide Spam
                        if pct != last_reported:
                            last_reported = pct
                            if on_progress:
                                on_progress(pct)
        finally:
            ret = proc.wait()

        # Stelle sicher, dass 100% signalisiert wird
        if on_progress:
            on_progress(100)

        if ret != 0:
            raise subprocess.CalledProcessError(ret, cmd)

    # --------- Export / Strip ---------

    def export_subtitle(
        self,
        file: Path,
        rel_sub_index: int,
        out_dir: Path,
        on_progress: Optional[Callable[[int], None]] = None
    ) -> Path:
        ffmpeg = self.find_ffbin("ffmpeg")
        out_dir.mkdir(parents=True, exist_ok=True)
        base = file.stem
        out = out_dir / f"{base}.sub{rel_sub_index}.srt"

        cmd = [ffmpeg, "-y", "-i", str(file), "-map", f"0:s:{rel_sub_index}", "-c:s", "srt", str(out)]
        try:
            self._run_ffmpeg_with_progress(cmd, input_file=file, on_progress=on_progress)
        except subprocess.CalledProcessError:
            # Fallback: Bildbasierte Subs roh kopieren
            out = out.with_suffix(".sup")
            cmd = [ffmpeg, "-y", "-i", str(file), "-map", f"0:s:{rel_sub_index}", "-c", "copy", str(out)]
            self._run_ffmpeg_with_progress(cmd, input_file=file, on_progress=on_progress)
        return out

    def remove_subtitles_and_replace(
        self,
        file: Path,
        keep_kinds: Optional[List[str]] = None,
        on_progress: Optional[Callable[[int], None]] = None
    ) -> Path:
        pr = self.probe_file(file)

        # Ermitteln, welche Sub-Maps wir behalten
        keep_maps: List[str] = []
        if keep_kinds:
            from app.service.detection_service import DetectionService
            detect = DetectionService()
            sub_rel = -1
            for s in pr.streams:
                if s.codec_type == "subtitle":
                    sub_rel += 1
                    cls = detect.classify_subtitle(s.title, s.language, s.forced)
                    if cls in keep_kinds:
                        keep_maps.append(f"0:s:{sub_rel}")

        ffmpeg = self.find_ffbin("ffmpeg")
        tmp = file.with_suffix(file.suffix + ".tmp_mux.mkv")
        maps = self._build_non_sub_maps(pr)

        cmd = [ffmpeg, "-y", "-i", str(file)]
        for m in maps:
            cmd += ["-map", m]
        for km in keep_maps:
            cmd += ["-map", km]
        cmd += ["-c", "copy", str(tmp)]

        self._run_ffmpeg_with_progress(cmd, input_file=file, on_progress=on_progress)

        backup = file.with_suffix(file.suffix + ".bak")
        if backup.exists():
            backup.unlink()
        file.replace(backup)
        try:
            tmp.replace(file)
            backup.unlink(missing_ok=True)
        except Exception:
            if file.exists():
                file.unlink(missing_ok=True)
            backup.replace(file)
            raise
        return file
