import os, tempfile
from tiktok_direct_post import TikTokPublisher
from publisher import PublicationState
import tiktok_direct_post as mod

os.environ["TIKTOK_CLIENT_KEY"] = "test-key"
os.environ["TIKTOK_CLIENT_SECRET"] = "test-secret"
os.environ["TIKTOK_ACCESS_TOKEN"] = "test-token"
os.environ["TIKTOK_LIVE_PUBLISH_ENABLED"] = "true"

responses = iter([
    (200, {"data": {"privacy_level_options": ["SELF_ONLY"]}}),
    (200, {"data": {"publish_id": "publish_test_123", "upload_url": "https://upload.invalid/test"}}),
    (200, {"data": {"status": "PUBLISH_COMPLETE"}}),
])
mod._json_request = lambda *args, **kwargs: next(responses)

with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
    f.write(b"fake-video-bytes")
    path = f.name

p = TikTokPublisher()
p._upload_file = lambda upload_url, path, size: size
r = p.publish_direct_post(path, "Test drama", ["drama"], "pub_test_live", privacy_level="SELF_ONLY")
assert r["state"] == PublicationState.PUBLISHED
assert r["receipt"]["publish_id"] == "publish_test_123"
assert r["evidence_gate"] == "RECEIPT_VERIFIED"
print("[PASS] Mocked TikTok Direct Post: creator_info -> init -> upload -> PUBLISH_COMPLETE -> receipt verified")
