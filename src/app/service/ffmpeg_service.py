# src/app/service/ffmpeg_service.py
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
    """Kapselt Aufrufe von ffprobe/ffmpeg, inkl. Progress-Parsing und Binärauflösung."""

    # -------------------- Pfad-Helfer --------------------

    def _platform_tag(self) -> str:
        return "windows" if platform.system().lower().startswith("win") else "linux"

    def _bundle_base_dir(self) -> Path:
        """
        Basisordner, unter dem unsere mitgelieferten Binaries liegen.
        - Dev/Poetry: <repo>/resources/ffmpeg/<plat>/
        - PyInstaller onedir: <dist>/<App>/_internal/resources/ffmpeg/<plat>/
        - PyInstaller onefile: <_MEIPASS>/resources/ffmpeg/<plat>/
        """
        if getattr(sys, "frozen", False):
            # onefile: _MEIPASS, onedir: <App>/.../_internal/...
            root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
            # In onedir liegt „_internal“ neben der exe – realtiv dazu die resources
            if "_internal" not in str(root):
                # exe liegt z.B. in <dist>/<App>/ ; resources in <dist>/<App>/_internal/resources
                maybe = Path(sys.executable).parent / "_internal"
                if maybe.exists():
                    root = maybe
        else:
            # im Dev: src/app/service/... -> zurück zur Repo-Wurzel
            root = Path(__file__).resolve().parents[3]

        return root / "resources" / "ffmpeg"

    def _vendor_dir(self) -> Path:
        return self._bundle_base_dir() / self._platform_tag()

    def _vendor_ffbin(self, name: str) -> Optional[Path]:
        exe = name + (".exe" if self._platform_tag() == "windows" else "")
        p = self._vendor_dir() / exe
        return p if p.exists() else None

    def _chmod_exec(self, p: Path) -> None:
        try:
            os.chmod(p, 0o755)
        except Exception:
            pass

    # -------------------- Auswahl der Binärdatei --------------------

    def find_ffbin(self, name: str) -> str:
        """
        Liefert den Pfad zu ffmpeg/ffprobe unter Beachtung der gewünschten Priorität:
        - prefer_bundled=True  -> bundled > custom > system
        - prefer_bundled=False -> custom > system > bundled
        """
        prefer_bundled = use_bundled_preferred()
        custom = custom_bin_path(name)
        vendor = self._vendor_ffbin(name)
        system = shutil.which(name)

        # Normalisiere: Wenn String -> Path, und Existenz prüfen
        custom_ok = bool(custom and Path(custom).exists())
        vendor_ok = bool(vendor and vendor.exists())
        system_ok = bool(system)

        if prefer_bundled:
            if vendor_ok:
                self._chmod_exec(vendor)  # macht unter Linux ausführbar
                return str(vendor)
            if custom_ok:
                return str(custom)
            if system_ok:
                return str(system)
        else:
            if custom_ok:
                return str(custom)
            if system_ok:
                return str(system)
            if vendor_ok:
                self._chmod_exec(vendor)
                return str(vendor)

        raise FileNotFoundError(
            f"{name} nicht gefunden. Setze einen Pfad in den Einstellungen, "
            f"installiere es systemweit oder lege es unter resources/ffmpeg/<platform>/ ab."
        )

    # Eine reine Herkunfts-Erkennung ohne find_ffbin-Aufruf (spiegelt die Settings-Logik)
    def detect_origin(self) -> str:
        prefer_bundled = use_bundled_preferred()
        ff_custom = custom_bin_path("ffmpeg")
        fp_custom = custom_bin_path("ffprobe")
        has_custom = bool(ff_custom and Path(ff_custom).exists()) and bool(fp_custom and Path(fp_custom).exists())
        vendor_ff = self._vendor_ffbin("ffmpeg")
        vendor_fp = self._vendor_ffbin("ffprobe")
        has_vendor = bool(vendor_ff) and bool(vendor_fp)
        has_system = bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe"))

        if prefer_bundled and has_vendor:
            return "bundled"
        if not prefer_bundled and has_custom:
            return "custom"
        if has_system:
            return "system"
        if has_vendor:
            return "bundled"
        return "missing"

    # -------------------- ffprobe --------------------

    def run_ffprobe(self, file: Path) -> Dict[str, Any]:
        ffprobe = self.find_ffbin("ffprobe")
        cmd = [ffprobe, "-v", "error", "-show_streams", "-print_format", "json", str(file)]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return json.loads(out)

    def probe_duration_seconds(self, file: Path) -> Optional[float]:
        ffprobe = self.find_ffbin("ffprobe")
        cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(file)]
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
            result.append(
                ProbeStream(
                    index=int(s.get("index", -1)),
                    codec_type=ctype,
                    codec_name=s.get("codec_name"),
                    language=tags.get("language") or tags.get("LANGUAGE"),
                    title=tags.get("title") or tags.get("TITLE"),
                    forced=str(s.get("disposition", {}).get("forced", 0)) == "1",
                    default=str(s.get("disposition", {}).get("default", 0)) == "1",
                )
            )
        return result

    def probe_file(self, file: Path) -> ProbeResult:
        data = self.run_ffprobe(file)
        return ProbeResult(path=file, streams=self.parse_streams(data))

    # -------------------- Utilities --------------------

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

    # -------------------- Gemeinsamer ffmpeg-Runner (Progress) --------------------

    def _run_ffmpeg_with_progress(
        self,
        cmd: List[str],
        input_file: Optional[Path],
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> None:
        total = None
        if input_file is not None:
            total = self.probe_duration_seconds(input_file)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )

        last_reported = -1
        try:
            if on_progress and total:
                on_progress(0)

            if proc.stderr:
                for line in proc.stderr:
                    m = _TIME_RE.search(line)
                    if m and total and total > 0:
                        cur = _time_to_seconds(m.group(1), m.group(2), m.group(3))
                        pct = max(0, min(100, int(cur / total * 100)))
                        if pct != last_reported:
                            last_reported = pct
                            if on_progress:
                                on_progress(pct)
        finally:
            ret = proc.wait()

        if on_progress:
            on_progress(100)

        if ret != 0:
            raise subprocess.CalledProcessError(ret, cmd)

    # -------------------- Export / Strip --------------------

    def export_subtitle(
        self,
        file: Path,
        rel_sub_index: int,
        out_dir: Path,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> Path:
        ffmpeg = self.find_ffbin("ffmpeg")
        out_dir.mkdir(parents=True, exist_ok=True)
        base = file.stem
        out = out_dir / f"{base}.sub{rel_sub_index}.srt"

        cmd = [ffmpeg, "-y", "-i", str(file), "-map", f"0:s:{rel_sub_index}", "-c:s", "srt", str(out)]
        try:
            self._run_ffmpeg_with_progress(cmd, input_file=file, on_progress=on_progress)
        except subprocess.CalledProcessError:
            out = out.with_suffix(".sup")
            cmd = [ffmpeg, "-y", "-i", str(file), "-map", f"0:s:{rel_sub_index}", "-c", "copy", str(out)]
            self._run_ffmpeg_with_progress(cmd, input_file=file, on_progress=on_progress)
        return out

    def remove_subtitles_and_replace(
        self,
        file: Path,
        keep_kinds: Optional[List[str]] = None,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> Path:
        pr = self.probe_file(file)

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

    def create_mkv(
        self,
        video_file: Path,
        audio_files: List[Path],
        subtitle_files: List[Path],
        output_file: Path,
        default_audio_index: Optional[int] = None,
        default_subtitle_index: Optional[int] = None,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> Path:
        """
        Creates a new MKV file by muxing a video file with additional audio and subtitle files.
        All streams from the original video file are kept.
        Default flags can be set on one audio and one subtitle stream.
        """
        ffmpeg = self.find_ffbin("ffmpeg")

        pr = self.probe_file(video_file)
        num_audio_in_video = sum(1 for s in pr.streams if s.codec_type == "audio")
        num_subs_in_video = sum(1 for s in pr.streams if s.codec_type == "subtitle")

        all_inputs = [video_file] + audio_files + subtitle_files

        cmd = [ffmpeg, "-y"]
        for f in all_inputs:
            cmd += ["-i", str(f)]

        for i in range(len(all_inputs)):
            cmd += ["-map", f"{i}"]

        cmd += ["-c", "copy"]

        total_audio_streams = num_audio_in_video + len(audio_files)
        total_subtitle_streams = num_subs_in_video + len(subtitle_files)

        for i in range(total_audio_streams):
            is_default = (i == default_audio_index)
            cmd += [f"-disposition:a:{i}", "default" if is_default else "0"]
        
        for i in range(total_subtitle_streams):
            is_default = (i == default_subtitle_index)
            cmd += [f"-disposition:s:{i}", "default" if is_default else "0"]

        cmd += [str(output_file)]

        self._run_ffmpeg_with_progress(cmd, input_file=video_file, on_progress=on_progress)
        return output_file
