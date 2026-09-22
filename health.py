# health.py - Minimal HTTP health endpoint for Railway + Docker
# GET /health returns 200 only when app + persistence initialized

import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class HealthHandler(BaseHTTPRequestHandler):
    def __init__(self, repository_getter, *args, **kwargs):
        self.repository_getter = repository_getter
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path == "/health":
            try:
                repo = self.repository_getter()
                healthy = repo.health_check() if repo else False
                if healthy:
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    response = {
                        "status": "ok",
                        "service": "video-agent",
                        "persistence": "ok",
                        "version": "v1.2"
                    }
                    self.wfile.write(json.dumps(response).encode())
                else:
                    self.send_response(503)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    response = {
                        "status": "error",
                        "service": "video-agent",
                        "persistence": "failed",
                        "version": "v1.2"
                    }
                    self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(503)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                response = {
                    "status": "error",
                    "service": "video-agent",
                    "persistence": "exception",
                    "version": "v1.2"
                }
                self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        return

def start_health_server(repository_getter, host="0.0.0.0", port=8000):
    # Factory to inject repository_getter
    def handler(*args, **kwargs):
        HealthHandler(repository_getter, *args, **kwargs)
    
    # Use closure to pass getter
    class CustomHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                try:
                    repo = repository_getter()
                    healthy = repo.health_check() if repo else False
                    if healthy:
                        self.send_response(200)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        response = {
                            "status": "ok",
                            "service": "video-agent",
                            "persistence": "ok",
                            "version": "v1.2"
                        }
                        self.wfile.write(json.dumps(response).encode())
                    else:
                        self.send_response(503)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        response = {
                            "status": "error",
                            "service": "video-agent",
                            "persistence": "failed",
                            "version": "v1.2"
                        }
                        self.wfile.write(json.dumps(response).encode())
                except Exception as e:
                    self.send_response(503)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    response = {
                        "status": "error",
                        "service": "video-agent",
                        "persistence": "exception",
                        "version": "v1.2",
                        "error": "hidden"  # Do not expose internal stack traces
                    }
                    self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            return
    
    server = HTTPServer((host, port), CustomHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
