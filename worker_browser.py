# Browser-backed YouTube worker for Short Drama Video Agent.
# Runs on an authorized Windows desktop so yt-dlp can reuse the local Firefox session.
import hashlib
import http.client
import json
import os
import shutil
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import urllib.request
import yt_dlp


_LOCAL_ENV = Path(__file__).with_name(".env")
if _LOCAL_ENV.is_file():
    for _line in _LOCAL_ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _value = _line.split("=", 1)
            os.environ.setdefault(_key.strip(), _value.strip().strip('"').strip("'"))


AGENT_URL = os.getenv("VIDEO_AGENT_URL", "https://short-drama-video-agen-production.up.railway.app").rstrip("/")
WORKER_TOKEN = os.getenv("YOUTUBE_WORKER_TOKEN", "").strip()
BROWSER = os.getenv("YTDLP_BROWSER", "firefox").strip()
DENO_PATH = os.getenv("YTDLP_DENO_PATH", r"C:\Users\LTC\AppData\Local\Deno\deno.exe").strip()
OUTPUT_DIR = Path(os.getenv("YTDLP_OUTPUT_DIR", r"C:\Users\LTC\Downloads\short-drama-browser-worker"))
POLL_SECONDS = max(2, int(os.getenv("YTDLP_POLL_SECONDS", "5")))
MAX_BYTES = 200 * 1024 * 1024
MAX_SECONDS = 600


def _json_request(url, method="GET", payload=None):
    data = None
    headers = {"X-Worker-Token": WORKER_TOKEN, "User-Agent": "ShortDramaBrowserWorker/1.0"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else {}


def _upload_file(job_id, path, video_id, title):
    parsed = urlsplit(f"{AGENT_URL}/worker/jobs/{job_id}/complete")
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parsed.netloc, timeout=300)
    size = path.stat().st_size
    headers = {
        "X-Worker-Token": WORKER_TOKEN,
        "X-Video-Id": str(video_id)[:200],
        "X-Video-Title": str(title)[:200],
        "Content-Type": "video/mp4",
        "Content-Length": str(size),
        "User-Agent": "ShortDramaBrowserWorker/1.0",
    }
    try:
        with path.open("rb") as stream:
            conn.request("POST", parsed.path or "/", body=stream, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"worker upload HTTP {response.status}: {raw[:500].decode('utf-8', 'replace')}")
        return json.loads(raw.decode("utf-8")) if raw else {}
    finally:
        conn.close()


def _fail_job(job_id, error):
    try:
        return _json_request(
            f"{AGENT_URL}/worker/jobs/{job_id}/fail",
            method="POST",
            payload={"error": str(error)[:1000]},
        )
    except Exception as exc:
        print(f"[worker] failure callback error: {exc}")
        return None


def _download(job):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    job_id = str(job["job_id"])
    output_template = str(OUTPUT_DIR / f"{job_id}.%(ext)s")
    ffmpeg_available = shutil.which("ffmpeg") is not None
    fmt = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b" if ffmpeg_available else "b[ext=mp4]/b"
    options = {
        "format": fmt,
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "max_filesize": MAX_BYTES,
        "match_filter": yt_dlp.utils.match_filter_func(f"duration <= {MAX_SECONDS}"),
        "cookiesfrombrowser": (BROWSER,),
        "js_runtimes": {"deno": DENO_PATH},
        "quiet": True,
        "no_warnings": False,
        "restrictfilenames": True,
        "overwrites": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(job["url"], download=True)
        path = Path(ydl.prepare_filename(info))
        if not path.is_file():
            mp4 = path.with_suffix(".mp4")
            if mp4.is_file():
                path = mp4
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError("worker downloaded artifact is missing or empty")
        if path.stat().st_size > MAX_BYTES:
            raise RuntimeError("worker downloaded artifact exceeds 200 MB")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return path, str(info.get("id") or job_id), str(info.get("title") or "YouTube video"), digest.hexdigest()


def run():
    if not WORKER_TOKEN:
        raise RuntimeError("YOUTUBE_WORKER_TOKEN is missing")
    if not DENO_PATH or not Path(DENO_PATH).is_file():
        raise RuntimeError(f"Deno runtime not found: {DENO_PATH}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[worker] online -> {AGENT_URL}")
    print(f"[worker] browser={BROWSER}, deno={DENO_PATH}")
    while True:
        try:
            payload = _json_request(f"{AGENT_URL}/worker/jobs?limit=1")
            jobs = payload.get("jobs") or []
            if not jobs:
                time.sleep(POLL_SECONDS)
                continue
            for job in jobs:
                job_id = job["job_id"]
                print(f"[worker] claimed job {job_id}")
                try:
                    path, video_id, title, digest = _download(job)
                    result = _upload_file(job_id, path, video_id, title)
                    print(f"[worker] completed {job_id}: {result.get('status')} sha256={digest}")
                    try:
                        path.unlink(missing_ok=True)
                    except Exception:
                        pass
                except Exception as exc:
                    print(f"[worker] job {job_id} failed: {exc}")
                    _fail_job(job_id, str(exc))
        except Exception as exc:
            print(f"[worker] poll error: {exc}")
            time.sleep(min(POLL_SECONDS * 3, 30))


if __name__ == "__main__":
    run()
