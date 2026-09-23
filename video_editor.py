# video_editor.py - deterministic FFmpeg video editing with Evidence Gate
from __future__ import annotations
import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
FONT_CANDIDATES = (
    os.getenv("VIDEO_FONT", ""),
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
)

@dataclass
class EditResult:
    state: str
    operation: str
    input_path: str
    output_path: Optional[str] = None
    artifact_bytes: int = 0
    artifact_sha256: Optional[str] = None
    error_code: Optional[str] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return (
            self.state == "EDITED"
            and bool(self.output_path)
            and self.artifact_bytes > 0
            and bool(self.artifact_sha256)
        )

def ffmpeg_available() -> bool:
    return shutil.which(FFMPEG_BIN) is not None

def editor_status() -> Dict[str, Any]:
    font = next((p for p in FONT_CANDIDATES if p and os.path.exists(p)), None)
    return {
        "ready": ffmpeg_available(),
        "ffmpeg": shutil.which(FFMPEG_BIN),
        "font": font,
    }

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _fail(operation: str, source: Path, code: str, error: str) -> EditResult:
    return EditResult("FAILED", operation, str(source), error_code=code, error=error)

def _run(args):
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=300,
    )

def edit_video(
    input_path: str,
    operation: Dict[str, Any],
    output_path: Optional[str] = None,
) -> EditResult:
    source = Path(input_path)
    op = str(operation.get("type", "")).lower()

    if not source.is_file() or source.stat().st_size <= 0:
        return _fail(op, source, "EDIT_INPUT_INVALID", "input video missing or empty")

    if not ffmpeg_available():
        return EditResult(
            "BLOCKED_NO_EDIT_ENGINE",
            op,
            str(source),
            error_code="BLOCKED_NO_EDIT_ENGINE",
            error="ffmpeg executable is not available",
        )

    if output_path:
        output = Path(output_path)
    else:
        fd, temp_name = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        output = Path(temp_name)

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.resolve() == source.resolve():
        return _fail(op, source, "EDIT_OUTPUT_SAME_AS_INPUT", "output must differ from input")

    filters = []
    audio_filters = []
    args = [FFMPEG_BIN, "-y", "-i", str(source)]

    if op == "lighting":
        value = str(operation.get("value", "adjust"))
        brightness, contrast = {
            "darker": (-0.15, 1.12),
            "brighter": (0.12, 1.05),
        }.get(value, (0.0, 1.0))
        filters.append(f"eq=brightness={brightness}:contrast={contrast}")

    elif op == "trim":
        seconds = max(0.1, float(operation.get("seconds", 3)))
        position = str(operation.get("position", "start"))
        if position == "start":
            args += ["-ss", str(seconds)]
        else:
            args += ["-t", str(seconds)]

    elif op == "speed":
        raw = str(operation.get("value", "1.0x")).lower().replace("x", "")
        speed = min(4.0, max(0.25, float(raw)))
        filters.append(f"setpts={1 / speed:.8f}*PTS")
        remaining = speed
        while remaining > 2.0:
            audio_filters.append("atempo=2.0")
            remaining /= 2.0
        while remaining < 0.5:
            audio_filters.append("atempo=0.5")
            remaining /= 0.5
        audio_filters.append(f"atempo={remaining:.8f}")

    elif op == "caption":
        text = str(operation.get("new_text") or "").strip()
        if not text:
            return _fail(op, source, "EDIT_CAPTION_EMPTY", "caption text is empty")
        font = next((p for p in FONT_CANDIDATES if p and os.path.exists(p)), None)
        if not font:
            return EditResult(
                "BLOCKED_NO_EDIT_ENGINE",
                op,
                str(source),
                error_code="BLOCKED_NO_FONT",
                error="caption font is unavailable",
            )
        safe = (
            text.replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace(",", "\\,")
        )
        filters.append(
            f"drawtext=fontfile='{font}':text='{safe}':fontcolor=white:"
            "fontsize=42:box=1:boxcolor=black@0.55:boxborderw=18:"
            "x=(w-text_w)/2:y=h-text_h-90"
        )

    elif op == "zoom":
        filters.append("scale=iw*1.12:ih*1.12,crop=iw/1.12:ih/1.12")

    elif op == "visual":
        value = str(operation.get("value", "")).lower()
        if "sepia" in value:
            filters.append(
                "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131"
            )
        else:
            filters.append("eq=saturation=1.08:contrast=1.04")

    else:
        return _fail(
            op,
            source,
            "EDIT_UNSUPPORTED_OPERATION",
            f"unsupported operation: {op}",
        )

    if filters:
        args += ["-vf", ",".join(filters)]
    if audio_filters:
        args += ["-af", ",".join(audio_filters)]

    args += [
        "-map_metadata", "-1",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(output),
    ]

    try:
        process = _run(args)
    except subprocess.TimeoutExpired:
        return _fail(op, source, "EDIT_TIMEOUT", "ffmpeg timed out")

    if process.returncode != 0:
        try:
            if output.exists():
                output.unlink()
        except OSError:
            pass
        return _fail(op, source, "EDIT_FFMPEG_ERROR", process.stderr[-2000:])

    if not output.is_file() or output.stat().st_size <= 0:
        return _fail(
            op,
            source,
            "EDIT_EMPTY_ARTIFACT",
            "ffmpeg returned success but output is missing or empty",
        )

    return EditResult(
        "EDITED",
        op,
        str(source),
        str(output),
        output.stat().st_size,
        _sha256(output),
    )
