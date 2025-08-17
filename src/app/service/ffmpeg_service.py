#src/app/service/ffmpeg_service.py
from __future__ import annotations
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.settings import custom_bin_path, use_bundled_preferred
from app.model.probe_result import ProbeResult
from app.model.probe_stream import ProbeStream


class FfmpegService:
    """Kapselt Aufrufe von ffprobe/ffmpeg und Muxing-Logik."""

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
        # 1) Benutzerdefinierter Pfad?
        custom = custom_bin_path(name)
        if custom and Path(custom).exists():
            # print(f"[ffmpeg] using custom: {custom}", file=sys.stderr)
            return custom

        # 2) Bevorzugt gebündelt?
        prefer_bundled = use_bundled_preferred()
        if prefer_bundled:
            vend = self._vendor_ffbin(name)
            if vend:
                self._chmod_exec(vend)
                # print(f"[ffmpeg] using bundled: {vend}", file=sys.stderr)
                return str(vend)
            sysbin = shutil.which(name)
            if sysbin:
                # print(f"[ffmpeg] fallback system: {sysbin}", file=sys.stderr)
                return sysbin
        else:
            sysbin = shutil.which(name)
            if sysbin:
                # print(f"[ffmpeg] using system: {sysbin}", file=sys.stderr)
                return sysbin
            vend = self._vendor_ffbin(name)
            if vend:
                self._chmod_exec(vend)
                # print(f"[ffmpeg] fallback bundled: {vend}", file=sys.stderr)
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

    # --------- Export / Strip ---------
    def export_subtitle(self, file: Path, rel_sub_index: int, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)

        pr = self.probe_file(file)

        sub_rel = -1
        picked = None
        for s in pr.streams:
            if s.codec_type == "subtitle":
                sub_rel += 1
                if sub_rel == rel_sub_index:
                    picked = s
                    break
        if picked is None:
            raise RuntimeError(f"Kein Untertitel-Stream mit rel-idx {rel_sub_index} gefunden.")

        codec = (picked.codec_name or "").lower()
        text_codecs = {"subrip", "ass", "ssa", "text"}
        is_text = codec in text_codecs

        lang = (picked.language or "und").lower()
        kind = "forced" if picked.forced else "full"
        ext = "srt" if is_text else "sup"

        out_path = out_dir / f"{file.stem}.{lang}.{kind}.{ext}"

        ffmpeg = self.find_ffbin("ffmpeg")
        cmd = [ffmpeg, "-y", "-v", "error", "-i", str(file), "-map", f"0:s:{rel_sub_index}"]
        if is_text:
            cmd += ["-c:s", "srt", str(out_path)]
        else:
            cmd += ["-c", "copy", str(out_path)]

        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
        except subprocess.CalledProcessError as e:
            output = (e.stdout or b"").decode("utf-8", errors="replace")

            try:
                (out_path.with_suffix(out_path.suffix + ".log.txt")).write_text(
                    "Command:\n" + " ".join(cmd) + "\n\nOutput:\n" + output, encoding="utf-8"
                )
            except Exception:
                pass
            raise RuntimeError(f"FFmpeg-Export fehlgeschlagen.\n\nBefehl:\n{' '.join(cmd)}\n\nAusgabe:\n{output}")

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg meldete Erfolg, aber die Ausgabedatei wurde nicht erstellt.")

        return out_path


    def remove_subtitles_and_replace(self, file: Path, keep_kinds: Optional[List[str]] = None) -> Path:
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
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)

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
