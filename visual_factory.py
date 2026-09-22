# visual_factory.py - Short Drama Visual Factory
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

MODEL_ID = os.getenv("VIDEO_MODEL_ID", "Wan-AI/Wan2.1-T2V-1.3B")
HF_PROVIDER = os.getenv("HF_VIDEO_PROVIDER", "fal-ai")
OUTPUT_DIR = Path(os.getenv("VIDEO_OUTPUT_DIR", "./data/generated"))


@dataclass
class GenerationResult:
    state: str
    provider: str
    model: str
    artifact_path: Optional[str] = None
    artifact_sha256: Optional[str] = None
    artifact_bytes: int = 0
    error_code: Optional[str] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.state == "GENERATED" and bool(
            self.artifact_path and self.artifact_sha256 and self.artifact_bytes > 0
        )


def parse_story_to_beats(story):
    outline = story.get("story_outline", "")
    beats = story.get("beats", 4)
    if len(outline) < 300:
        beats = 3
    elif len(outline) > 1000:
        beats = 6
    beats = max(3, min(7, beats))
    result = []
    for i in range(1, beats + 1):
        result.append({
            "beat_number": i,
            "title": f"{story.get('title')} - الجزء {i}",
            "duration_sec": 50,
            "prompt": f"9:16 vertical drama, beat {i}/{beats}, {story.get('hook', '')}, cinematic",
            "caption": f"{story.get('hook', '')} - الجزء {i}",
            "tags": story.get("tags", [])[:3],
        })
    return result


def create_character_bible(story):
    story_id = story.get("id", "")
    return {
        "story_id": story_id,
        "bible_id": f"bible_{hashlib.sha256(story_id.encode()).hexdigest()[:12]}",
        "characters": ["Main heroine - consistent face", "Billionaire CEO"],
        "style": "cinematic 9:16, dramatic lighting",
        "consistent_face": True,
    }


def generate_video_prompt(beat, bible, edit_ops=None):
    base = beat["prompt"]
    if edit_ops:
        for op in edit_ops:
            if op["type"] == "lighting":
                base += f", {op.get('prompt', '')}"
    return base


def _provider_status() -> dict[str, Any]:
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        return {
            "state": "BLOCKED_CREDENTIALS",
            "error_code": "GENERATION_BLOCKED_CREDENTIALS",
        }
    return {
        "state": "READY",
        "provider": HF_PROVIDER,
        "model": MODEL_ID,
    }


def generate_video(
    beat: dict,
    bible: dict,
    edit_ops: Optional[list[dict]] = None,
) -> GenerationResult:
    """
    Real text-to-video generation through Hugging Face Inference Providers.

    Evidence Gate:
    - Missing HF_TOKEN => BLOCKED_CREDENTIALS
    - Provider exception => FAILED
    - Empty/non-bytes output => FAILED
    - Only a non-empty persisted video artifact with SHA-256 may be GENERATED.
    """
    status = _provider_status()
    if status["state"] != "READY":
        return GenerationResult(
            state="BLOCKED_CREDENTIALS",
            provider=HF_PROVIDER,
            model=MODEL_ID,
            error_code=status["error_code"],
        )

    try:
        from huggingface_hub import InferenceClient
    except ImportError as exc:
        return GenerationResult(
            state="FAILED",
            provider=HF_PROVIDER,
            model=MODEL_ID,
            error_code="GENERATION_DEPENDENCY_MISSING",
            error=str(exc),
        )

    prompt = generate_video_prompt(beat, bible, edit_ops)
    client = InferenceClient(
        provider=HF_PROVIDER,
        api_key=os.environ["HF_TOKEN"],
    )

    try:
        video = client.text_to_video(prompt, model=MODEL_ID)
    except Exception as exc:
        return GenerationResult(
            state="FAILED",
            provider=HF_PROVIDER,
            model=MODEL_ID,
            error_code="GENERATION_PROVIDER_ERROR",
            error=str(exc),
        )

    if not isinstance(video, (bytes, bytearray)) or len(video) == 0:
        return GenerationResult(
            state="FAILED",
            provider=HF_PROVIDER,
            model=MODEL_ID,
            error_code="GENERATION_EMPTY_ARTIFACT",
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    story_id = str(bible.get("story_id", "story"))
    beat_number = beat.get("beat_number", 1)
    digest = hashlib.sha256(video).hexdigest()
    path = OUTPUT_DIR / f"{story_id}_beat_{beat_number}_{digest[:12]}.mp4"
    path.write_bytes(video)

    if not path.exists() or path.stat().st_size != len(video):
        return GenerationResult(
            state="FAILED",
            provider=HF_PROVIDER,
            model=MODEL_ID,
            error_code="GENERATION_ARTIFACT_WRITE_FAILED",
        )

    return GenerationResult(
        state="GENERATED",
        provider=HF_PROVIDER,
        model=MODEL_ID,
        artifact_path=str(path),
        artifact_sha256=digest,
        artifact_bytes=len(video),
    )


def get_agent_status():
    provider = _provider_status()
    return {
        "visual_factory": "READY",
        "generation_provider": provider,
        "character_bible": "Consistent Face - metadata only",
        "arabic_parser": "اضاءة اغمق قص كابشن اسرع ابطأ - READY",
        "beats": "3-7 per story",
        "format": "1080x1920 9:16 target",
    }
