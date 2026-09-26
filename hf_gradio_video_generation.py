"""Free/public Hugging Face Gradio generation adapter for Short Drama.

Uses two public ZeroGPU Spaces:
- mcp-tools/Z-Image-Turbo for a 9:16 starting frame
- ysharma/wan2-1-fast for Wan 2.1 I2V video generation

The adapter is evidence-first: it returns only after a real MP4 is fetched and
its SHA-256 is computed. Provider failures are raised instead of being marked
successful.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


class GradioGenerationError(RuntimeError):
    pass


@dataclass
class GenerationArtifact:
    video_url: str
    image_url: str
    provider: str
    local_path: str
    sha256: str
    size_bytes: int
    duration_sec: Optional[float]


def _sse_result(response: requests.Response, timeout: float) -> Any:
    event = None
    payload = None
    started = time.time()
    for raw in response.iter_lines(decode_unicode=True):
        if time.time() - started > timeout:
            raise GradioGenerationError("Gradio SSE polling timeout")
        line = (raw or "").strip()
        if not line:
            continue
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            payload = line.split(":", 1)[1].strip()
            if event == "complete":
                try:
                    return json.loads(payload)
                except json.JSONDecodeError as exc:                    raise GradioGenerationError("Invalid Gradio completion payload") from exc
            if event == "error":
                raise GradioGenerationError(payload)
    raise GradioGenerationError("Gradio stream ended without completion")


def _call_gradio(base_url: str, api_name: str, data: List[Any], timeout: float = 180.0) -> Any:
    base_url = base_url.rstrip("/")
    headers = {}
    token = os.getenv("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(
        f"{base_url}/gradio_api/call/{api_name.lstrip('/')}",
        json={"data": data},
        headers=headers,
        timeout=30,
    )
    if r.status_code not in (200, 202):
        raise GradioGenerationError(f"Gradio submit failed: HTTP {r.status_code}: {r.text[:300]}")
    try:
        event_id = r.json()["event_id"]
    except Exception as exc:
        raise GradioGenerationError("Gradio submit response missing event_id") from exc
    stream = requests.get(
        f"{base_url}/gradio_api/call/{api_name.lstrip('/')}/{event_id}",
        stream=True,
        timeout=(30, timeout),
        headers={**headers, "Accept": "text/event-stream"},
    )
    if stream.status_code != 200:
        raise GradioGenerationError(f"Gradio stream failed: HTTP {stream.status_code}")
    with stream:        return _sse_result(stream, timeout)


def _file_url(result: Any, key: str = "url") -> str:
    if isinstance(result, dict):
        if result.get(key):
            return str(result[key])
        if result.get("path") and str(result["path"]).startswith("http"):
            return str(result["path"])
    if isinstance(result, list) and result:
        return _file_url(result[0], key=key)
    raise GradioGenerationError("Provider result did not contain a public file URL")


def generate_story_video(
    story_text: str,
    output_dir: str = "./data/generated",
    timeout: float = 240.0,
) -> GenerationArtifact:
    if not story_text.strip():
        raise ValueError("story_text is required")

    image_space = os.getenv("HF_IMAGE_SPACE_URL", "https://mcp-tools-z-image-turbo.hf.space")
    video_space = os.getenv("HF_VIDEO_SPACE_URL", "https://ysharma-wan2-1-fast.hf.space")

    image_prompt = (
        "Cinematic realistic vertical 9:16 short-drama keyframe. "
        "Keep one fictional protagonist visually consistent. "        "Modern Egyptian/Cairo setting, realistic film lighting, natural skin and clothing, "
        "no text, no logos, no copyrighted characters. Story: " + story_text[:1800]
    )
    image_result = _call_gradio(
        image_space,
        "generate",
        [image_prompt, "720x1280 ( 9:16 )", 42, 8, 3.0, True],
        timeout=timeout,
    )
    image_url = _file_url(image_result)

    video_prompt = (
        "Animate this keyframe as a realistic short-drama shot. "
        "Preserve the protagonist and scene. Subtle cinematic camera movement, "
        "natural acting, suspenseful motion, no text, no logos. Story beat: " + story_text[:1200]
    )
    # Gradio's public File input accepts the generated image URL directly.
    # Using a FileData dict here caused the Railway runtime call to stall.
    video_result = _call_gradio(
        video_space,
        "generate-video",
        [image_url, video_prompt, 512, 896,         "Bright tones, overexposed, static, blurred details, subtitles, watermark, text, signature",
         2.0, 1.0, 4, 42, True],
        timeout=timeout,
    )
    video_url = _file_url(video_result, key="video")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = out_dir / "generation_download.tmp.mp4"
    vr = requests.get(video_url, stream=True, timeout=60, headers=headers if "headers" in locals() else {})
    if vr.status_code != 200:
        raise GradioGenerationError(f"Generated artifact download failed: HTTP {vr.status_code}")
    digest = hashlib.sha256()
    size = 0
    with vr:
        with tmp_path.open("wb") as fh:
            for chunk in vr.iter_content(chunk_size=1024 * 256):
                if chunk:
                    fh.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
    if size <= 0:
        raise GradioGenerationError("Generated artifact is empty")
    final_path = out_dir / f"{digest.hexdigest()}.mp4"
    tmp_path.replace(final_path)

    return GenerationArtifact(
        video_url=video_url,        image_url=image_url,
        provider="huggingface-wan2.1-gradio",
        local_path=str(final_path),
        sha256=digest.hexdigest(),
        size_bytes=size,
        duration_sec=2.0,
    )
