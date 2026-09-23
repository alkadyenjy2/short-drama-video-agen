# health.py - Minimal HTTP + Telegram webhook endpoint for Railway
# GET /health returns 200 when persistence is initialized.
# POST /telegram/webhook/<token-hash> forwards verified Telegram updates.

import asyncio
import hashlib
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


def webhook_path(bot_token: str) -> str:
    digest = hashlib.sha256(bot_token.encode("utf-8")).hexdigest()
    return f"/telegram/webhook/{digest}"


def start_health_server(repository_getter, host="0.0.0.0", port=8000,
                        telegram_handler=None, telegram_path=None):
    class CustomHandler(BaseHTTPRequestHandler):
        def _json(self, status, payload):
            self.send_response(status)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def do_GET(self):
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

    server = HTTPServer((host, port), CustomHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
