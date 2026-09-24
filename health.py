# health.py - Minimal HTTP + Telegram webhook endpoint for Railway
# GET /health returns 200 when persistence is initialized.
# POST /telegram/webhook/<token-hash> forwards verified Telegram updates.

import asyncio
import hashlib
import json
import os
import hashlib
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler


def webhook_path(bot_token: str) -> str:
    digest = hashlib.sha256(bot_token.encode("utf-8")).hexdigest()
    return f"/telegram/webhook/{digest}"


def start_health_server(repository_getter, host="0.0.0.0", port=8000,
                        telegram_handler=None, telegram_path=None,
                        worker_token=None, worker_complete_handler=None,
                        worker_fail_handler=None):
    class CustomHandler(BaseHTTPRequestHandler):
        def _json(self, status, payload):
            self.send_response(status)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def _authorized_worker(self):
            configured = (worker_token or "").strip()
            return bool(configured) and self.headers.get("X-Worker-Token", "") == configured

        def do_GET(self):
            if self.path.startswith("/worker/jobs"):
                if not self._authorized_worker():
                    self._json(401, {"ok": False, "error": "WORKER_UNAUTHORIZED"})
                    return
                try:
                    repo = repository_getter()
                    limit = 1
                    if "?" in self.path:
                        from urllib.parse import parse_qs, urlsplit
                        raw_limit = parse_qs(urlsplit(self.path).query).get("limit", ["1"])[0]
                        limit = max(1, min(int(raw_limit), 5))
                    jobs = repo.claim_download_jobs(limit)
                    self._json(200, {"ok": True, "jobs": jobs})
                except Exception as exc:
                    self._json(500, {"ok": False, "error": str(exc)[:500]})
                return

            if self.path != "/health":
                self.send_response(404)
                self.end_headers()
                return
            try:
                repo = repository_getter()
                healthy = bool(repo and repo.health_check())
                if healthy:
                    self._json(200, {
                        "status": "ok",
                        "service": "video-agent",
                        "persistence": "ok",
                        "version": "v1.3",
                        "telegram_transport": "webhook",
                    })
                else:
                    self._json(503, {
                        "status": "error",
                        "service": "video-agent",
                        "persistence": "failed",
                    })
            except Exception:
                self._json(503, {
                    "status": "error",
                    "service": "video-agent",
                    "persistence": "exception",
                })

        def do_POST(self):
            if self.path.startswith("/worker/jobs/"):
                if not self._authorized_worker():
                    self._json(401, {"ok": False, "error": "WORKER_UNAUTHORIZED"})
                    return
                parts = self.path.strip("/").split("/")
                if len(parts) != 4 or parts[0] != "worker" or parts[1] != "jobs":
                    self._json(404, {"ok": False, "error": "NOT_FOUND"})
                    return
                job_id, action = parts[2], parts[3]
                repo = repository_getter()
                job = repo.get_download_job(job_id)
                if not job:
                    self._json(404, {"ok": False, "error": "JOB_NOT_FOUND"})
                    return

                if action == "fail":
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        if length > 64 * 1024:
                            self._json(413, {"ok": False, "error": "ERROR_TOO_LARGE"})
                            return
                        raw = self.rfile.read(length) if length else b""
                        payload = json.loads(raw.decode("utf-8") or "{}")
                        error = str(payload.get("error") or "worker download failed")[:1000]
                        repo.fail_download_job(job_id, error)
                        if worker_fail_handler:
                            worker_fail_handler(job, error)
                        self._json(200, {"ok": True, "status": "FAILED"})
                    except Exception as exc:
                        self._json(400, {"ok": False, "error": str(exc)[:500]})
                    return

                if action != "complete":
                    self._json(404, {"ok": False, "error": "NOT_FOUND"})
                    return

                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > 200 * 1024 * 1024:
                        self._json(413, {"ok": False, "error": "VIDEO_TOO_LARGE"})
                        return
                    upload_dir = os.getenv("VIDEO_UPLOAD_DIR", "./data/uploads")
                    os.makedirs(upload_dir, exist_ok=True)
                    temp_path = os.path.join(upload_dir, f".worker-{job_id}.part")
                    final_path = os.path.join(upload_dir, f"{job_id}.mp4")
                    digest = hashlib.sha256()
                    total = 0
                    with open(temp_path, "wb") as out:
                        remaining = length
                        while remaining:
                            chunk = self.rfile.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise RuntimeError("worker upload ended before Content-Length")
                            out.write(chunk)
                            digest.update(chunk)
                            total += len(chunk)
                            remaining -= len(chunk)
                    if total <= 0:
                        raise RuntimeError("worker uploaded empty artifact")
                    os.replace(temp_path, final_path)
                    video_id = (self.headers.get("X-Video-Id") or job_id).strip()[:200]
                    title = (self.headers.get("X-Video-Title") or "YouTube video").strip()[:200]
                    sha256 = digest.hexdigest()
                    repo.set_active_video(job["user_id"], video_id, final_path, sha256, total)
                    updated = repo.complete_download_job(job_id, {
                        "status": "COMPLETE",
                        "video_id": video_id,
                        "title": title,
                        "path": final_path,
                        "sha256": sha256,
                        "bytes": total,
                        "error": None,
                    })
                    if worker_complete_handler:
                        try:
                            worker_complete_handler(updated, final_path)
                        except Exception as notify_exc:
                            print(f"Worker completion notification warning: {notify_exc}")
                    self._json(200, {
                        "ok": True,
                        "status": "COMPLETE",
                        "video_id": video_id,
                        "bytes": total,
                        "sha256": sha256,
                    })
                except Exception as exc:
                    try:
                        partial = os.path.join(os.getenv("VIDEO_UPLOAD_DIR", "./data/uploads"), f".worker-{job_id}.part")
                        if os.path.exists(partial):
                            os.remove(partial)
                    except Exception:
                        pass
                    repo.fail_download_job(job_id, str(exc))
                    if worker_fail_handler:
                        worker_fail_handler(job, str(exc))
                    self._json(400, {"ok": False, "error": str(exc)[:500]})
                return

            if not telegram_path or self.path != telegram_path or telegram_handler is None:
                self.send_response(404)
                self.end_headers()
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 10 * 1024 * 1024:
                    self.send_response(400)
                    self.end_headers()
                    return
                raw = self.rfile.read(length)
                payload = json.loads(raw.decode("utf-8"))
                telegram_handler(payload)
                self._json(200, {"ok": True})
            except Exception:
                self._json(400, {"ok": False})

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer((host, port), CustomHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
