# test_tiktok_audit.py - P0.9 TikTok Audit Tests - No Real Credentials
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
for k in ["TIKTOK_CLIENT_KEY","TIKTOK_CLIENT_SECRET","TIKTOK_ACCESS_TOKEN"]:
    os.environ.pop(k, None)

from publisher import TikTokPublisher, PublicationState, _classify_tiktok_error

def test(name, cond, details=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {details}")
    return cond

print("=== P0.9 TikTok Audit Tests ===\n")

print("--- Test 1: Missing credentials blocked ---")
tk = TikTokPublisher()
res = tk.publish_direct_post("https://example.com/video.mp4", "test", ["drama"], "pub_test_1")
test("TikTok blocked without creds", res["state"] == PublicationState.FAILED and res["receipt"] is None, f"state={res['state']}")
test("No fake PUBLISHED", res["state"] != PublicationState.PUBLISHED)
test("Evidence BLOCKED_CREDENTIALS", "evidence_record" in res and res["evidence_record"]["evidence_status"] == "BLOCKED_CREDENTIALS")

print("\n--- Test 2: Error classification ---")
cat, retry = _classify_tiktok_error("access_token_invalid", 401, "Access token invalid")
test("Auth invalid not retryable", cat == "authentication_failure" and not retry)
cat2, retry2 = _classify_tiktok_error("scope_not_authorized", 403, "Scope not authorized")
test("Perm scope not retryable", cat2 == "authorization_failure" and not retry2)
cat3, retry3 = _classify_tiktok_error("rate_limit_exceeded", 429, "Rate limit")
test("Rate limit retryable", cat3 == "rate_limit" and retry3)

print("\n--- Test 3: Even with creds but no real API, not PUBLISHED ---")
os.environ["TIKTOK_CLIENT_KEY"]="key"; os.environ["TIKTOK_CLIENT_SECRET"]="secret"; os.environ["TIKTOK_ACCESS_TOKEN"]="token"
tk2 = TikTokPublisher()
res2 = tk2.publish_direct_post("https://example.com/video.mp4", "test", ["drama"], "pub_test_2")
test("Even with creds not PUBLISHED", res2["state"] == PublicationState.FAILED and "ENFORCED" in res2["evidence_gate"])
test("HTTP 200 is NOT proof", "HTTP 200 is NOT proof" in res2["evidence_gate"])
for k in ["TIKTOK_CLIENT_KEY","TIKTOK_CLIENT_SECRET","TIKTOK_ACCESS_TOKEN"]:
    os.environ.pop(k, None)

print("\n--- Test 4: Flow docs present ---")
os.environ["TIKTOK_CLIENT_KEY"]="k"; os.environ["TIKTOK_CLIENT_SECRET"]="s"; os.environ["TIKTOK_ACCESS_TOKEN"]="t"
tk3 = TikTokPublisher()
res3 = tk3.publish_direct_post("https://example.com/video.mp4", "test", ["drama"], "pub_test_3")
test("Flow INIT_URL present", "INIT_URL" in str(res3.get("flow",{})) or "init" in str(res3.get("flow",{})).lower())
test("Flow STATUS_URL present", "status" in str(res3.get("flow",{})).lower())
for k in ["TIKTOK_CLIENT_KEY","TIKTOK_CLIENT_SECRET","TIKTOK_ACCESS_TOKEN"]:
    os.environ.pop(k, None)

print("\n=== Summary TikTok ===")
