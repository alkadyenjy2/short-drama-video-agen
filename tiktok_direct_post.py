# tiktok_direct_post.py - live Content Posting API Direct Post adapter
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from urllib import request, error



INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_request(url, method, token, payload):
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json; charset=UTF-8")
    try:
        with request.urlopen(req, timeout=30) as res:
            raw = res.read().decode("utf-8")
            return res.status, json.loads(raw or "{}")
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw or "{}")
        except Exception:
            data = {"raw": raw[:1000]}
        return exc.code, data


def _classify(status, data):
    msg = str(data.get("error") or data.get("message") or data.get("data") or "")
    low = msg.lower()
    if status == 401 or "token" in low and "invalid" in low:
        return "authentication_failure", False
    if status == 403 or "scope" in low or "permission" in low:
        return "authorization_failure", False
    if status == 429 or "rate" in low:
        return "rate_limit", True
    if status >= 500:
        return "temporary_provider_failure", True
    return "provider_error", False


def _evidence(op_id, video_id, status, evidence_status, **extra):
    result = {
        "operation_id": op_id,
        "video_id": video_id,
        "platform": "tiktok",
        "request_timestamp": extra.pop("request_timestamp", _now()),
        "verification_timestamp": _now(),
        "terminal_status": status,
        "evidence_status": evidence_status,
    }
    result.update(extra)
    return result


class TikTokPublisher:
    def __init__(self):
        self.client_key = os.getenv("TIKTOK_CLIENT_KEY")
        self.client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
        self.access_token = os.getenv("TIKTOK_ACCESS_TOKEN")
        self.live_enabled = os.getenv("TIKTOK_LIVE_PUBLISH_ENABLED", "false").lower() == "true"
        self.poll_seconds = max(2, int(os.getenv("TIKTOK_STATUS_POLL_SECONDS", "5")))
        self.max_polls = max(1, int(os.getenv("TIKTOK_STATUS_MAX_POLLS", "12")))

    def _check_credentials(self):
        if not self.client_key or not self.client_secret:
            return False, "TIKTOK_CLIENT_KEY or TIKTOK_CLIENT_SECRET missing", "authentication_failure"
        if not self.access_token:
            return False, "TIKTOK_ACCESS_TOKEN missing - OAuth video.publish required", "authentication_failure"
        if not self.live_enabled:
            return False, "TIKTOK_LIVE_PUBLISH_ENABLED is false", "blocked_by_safety_gate"
        return True, "ok", "ok"

    def _creator_info(self):
        return _json_request(CREATOR_INFO_URL, "POST", self.access_token, {})

    def _upload_file(self, upload_url, path, size):
        chunk_size = max(5 * 1024 * 1024, min(64 * 1024 * 1024, size or 5 * 1024 * 1024))
        sent = 0
        with open(path, "rb") as fh:
            while sent < size:
                chunk = fh.read(min(chunk_size, size - sent))
                if not chunk:
                    raise RuntimeError("VIDEO_UPLOAD_TRUNCATED")
                end = sent + len(chunk) - 1
                req = request.Request(upload_url, data=chunk, method="PUT")
                req.add_header("Content-Type", "video/mp4")
                req.add_header("Content-Length", str(len(chunk)))
                req.add_header("Content-Range", f"bytes {sent}-{end}/{size}")
                try:
                    with request.urlopen(req, timeout=120) as res:
                        if res.status not in (200, 201, 202, 206):
                            raise RuntimeError(f"TIKTOK_UPLOAD_HTTP_{res.status}")
                except error.HTTPError as exc:
                    raise RuntimeError(f"TIKTOK_UPLOAD_HTTP_{exc.code}") from exc
                sent = end + 1
        return sent

    def publish_direct_post(self, video_url_or_path, caption, hashtags, publication_id,
                            privacy_level="SELF_ONLY", source="FILE_UPLOAD"):
        from publisher import PublicationState
        attempt_id = f"attempt_{uuid.uuid4().hex[:8]}"
        op_id = f"op_{uuid.uuid4().hex[:12]}"
        started = _now()
        idem = hashlib.sha256(f"{publication_id}:tiktok".encode()).hexdigest()[:16]
        ok, reason, category = self._check_credentials()
        if not ok:
            gate = "BLOCKED" if category != "blocked_by_safety_gate" else "ENFORCED - safety gate blocked live publish - HTTP 200 is NOT proof"
            flow = {"step1_init": INIT_URL, "step2_upload": "FILE_UPLOAD PUT to upload_url", "step3_status": STATUS_URL}
            return {"attempt_id": attempt_id, "operation_id": op_id, "provider": "tiktok",
                    "state": PublicationState.FAILED, "reason": reason, "category": category,
                    "receipt": None, "platform_id": None, "evidence_gate": gate, "flow": flow,
                    "evidence_record": _evidence(op_id, publication_id, "FAILED", "BLOCKED_CREDENTIALS",
                                                  idempotency_key=idem, request_timestamp=started)}

        path = os.path.abspath(video_url_or_path)
        if source != "FILE_UPLOAD" or not os.path.isfile(path):
            return {"attempt_id": attempt_id, "operation_id": op_id, "provider": "tiktok",
                    "state": PublicationState.FAILED, "reason": "FILE_UPLOAD requires an existing local video file",
                    "category": "invalid_media", "receipt": None, "platform_id": None,
                    "evidence_gate": "ENFORCED", "evidence_record": _evidence(op_id, publication_id, "FAILED", "FAILED_INVALID_MEDIA", idempotency_key=idem)}

        size = os.path.getsize(path)
        if size <= 0 or size > 4 * 1024 * 1024 * 1024:
            return {"attempt_id": attempt_id, "operation_id": op_id, "provider": "tiktok",
                    "state": PublicationState.FAILED, "reason": "Video size must be >0 and <=4GB",
                    "category": "invalid_media", "receipt": None, "platform_id": None,
                    "evidence_gate": "ENFORCED", "evidence_record": _evidence(op_id, publication_id, "FAILED", "FAILED_INVALID_MEDIA", idempotency_key=idem)}

        caption_full = (caption or "").strip()
        tags = [str(h).lstrip("#") for h in (hashtags or []) if str(h).strip()]
        if tags:
            caption_full = (caption_full + " " + " ".join(f"#{h}" for h in tags)).strip()
        if len(caption_full) > 2200:
            return {"attempt_id": attempt_id, "operation_id": op_id, "provider": "tiktok",
                    "state": PublicationState.FAILED, "reason": "Caption too long", "category": "invalid_media",
                    "receipt": None, "platform_id": None, "evidence_gate": "ENFORCED",
                    "evidence_record": _evidence(op_id, publication_id, "FAILED", "FAILED_INVALID_MEDIA", idempotency_key=idem)}

        cstatus, cdata = self._creator_info()
        if cstatus != 200 or cdata.get("error", {}).get("code") not in (None, "ok"):
            cat, retry = _classify(cstatus, cdata)
            return {"attempt_id": attempt_id, "operation_id": op_id, "provider": "tiktok",
                    "state": PublicationState.FAILED, "reason": "creator_info/query failed",
                    "category": cat, "retryable": retry, "receipt": None, "platform_id": None,
                    "evidence_gate": "ENFORCED", "evidence_record": _evidence(op_id, publication_id, "FAILED", "PROVIDER_ERROR", error_code=str(cstatus), idempotency_key=idem)}

        creator = cdata.get("data") or {}
        allowed = creator.get("privacy_level_options") or []
        if allowed and privacy_level not in allowed:
            return {"attempt_id": attempt_id, "operation_id": op_id, "provider": "tiktok",
                    "state": PublicationState.FAILED, "reason": f"Privacy level {privacy_level} is not allowed for this creator",
                    "category": "invalid_privacy", "allowed_privacy": allowed, "receipt": None,
                    "platform_id": None, "evidence_gate": "ENFORCED", "evidence_record": _evidence(op_id, publication_id, "FAILED", "FAILED_INVALID_PRIVACY", idempotency_key=idem)}

        init_payload = {
            "post_info": {"title": caption_full[:2200], "privacy_level": privacy_level, "disable_duet": False,
                           "disable_comment": False, "disable_stitch": False, "video_cover_timestamp_ms": 1000},
            "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                            "chunk_size": max(5 * 1024 * 1024, min(64 * 1024 * 1024, size)),
                            "total_chunk_count": 1 if size <= 64 * 1024 * 1024 else (size + (64 * 1024 * 1024) - 1) // (64 * 1024 * 1024)}
        }
        istatus, idata = _json_request(INIT_URL, "POST", self.access_token, init_payload)
        if istatus != 200:
            cat, retry = _classify(istatus, idata)
            return {"attempt_id": attempt_id, "operation_id": op_id, "provider": "tiktok", "state": PublicationState.FAILED,
                    "reason": "TikTok video/init failed", "category": cat, "retryable": retry, "receipt": None,
                    "platform_id": None, "evidence_gate": "ENFORCED", "evidence_record": _evidence(op_id, publication_id, "FAILED", "PROVIDER_ERROR", error_code=str(istatus), idempotency_key=idem)}

        data = idata.get("data") or {}
        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")
        if not publish_id or not upload_url:
            return {"attempt_id": attempt_id, "operation_id": op_id, "provider": "tiktok", "state": PublicationState.FAILED,
                    "reason": "TikTok init returned no publish_id/upload_url", "category": "provider_error", "receipt": None,
                    "platform_id": None, "evidence_gate": "ENFORCED", "evidence_record": _evidence(op_id, publication_id, "FAILED", "FAILED_NO_RECEIPT", idempotency_key=idem)}

        try:
            uploaded = self._upload_file(upload_url, path, size)
        except Exception as exc:
            return {"attempt_id": attempt_id, "operation_id": op_id, "provider": "tiktok", "state": PublicationState.FAILED,
                    "reason": str(exc), "category": "upload_failure", "receipt": None, "platform_id": None,
                    "publish_id": publish_id, "evidence_gate": "ENFORCED", "evidence_record": _evidence(op_id, publication_id, "FAILED", "UPLOAD_FAILED", publish_id=publish_id, idempotency_key=idem)}

        terminal = None
        last = {}
        for attempt in range(self.max_polls):
            status_code, status_data = _json_request(STATUS_URL, "POST", self.access_token, {"publish_id": publish_id})
            last = status_data
            state = (status_data.get("data") or {}).get("status") or status_data.get("status")
            if state in ("PUBLISH_COMPLETE", "FAILED"):
                terminal = state
                if state == "PUBLISH_COMPLETE":
                    receipt = {"publish_id": publish_id, "status": state, "uploaded_bytes": uploaded,
                               "verified_at": _now(), "provider_response": {"status": state}}
                    return {"attempt_id": attempt_id, "operation_id": op_id, "provider": "tiktok",
                            "state": PublicationState.PUBLISHED, "reason": "TikTok publish complete receipt verified",
                            "category": "ok", "receipt": receipt, "platform_id": publish_id, "publish_id": publish_id,
                            "evidence_gate": "RECEIPT_VERIFIED", "evidence_record": _evidence(op_id, publication_id, state, "RECEIPT_VERIFIED", provider_object_id=publish_id, publish_id=publish_id, idempotency_key=idem)}
                break
            time.sleep(self.poll_seconds)

        return {"attempt_id": attempt_id, "operation_id": op_id, "provider": "tiktok", "state": PublicationState.FAILED,
                "reason": "TikTok publish did not reach PUBLISH_COMPLETE", "category": "publish_timeout_or_failure",
                "receipt": None, "platform_id": None, "publish_id": publish_id, "last_status": terminal or last,
                "evidence_gate": "ENFORCED - no terminal receipt = FAILED",
                "evidence_record": _evidence(op_id, publication_id, terminal or "TIMEOUT", "FAILED_NO_TERMINAL_RECEIPT", publish_id=publish_id, idempotency_key=idem)}

