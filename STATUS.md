# STATUS.md - Single Source of Truth - Short Drama Video Agent

## CURRENT STATE (2026-09-21)
- Source: short_drama_video_agent_v1.2_P0_real_publishers.zip → now P0.3 hardened
- publisher.py: P0.3 Meta hardened - 23k, _classify_meta_error, _sanitize_log, _redact_token, evidence_record with operation_id, video_id, platform, request_timestamp, terminal_status, evidence_status, retry_count, idempotency_key, ENFORCED gate
- visual_factory.py: NEW - Character Bible + beat parser + prompt builder - READY
- bot.py: Updated to use visual_factory - handle_generate now creates beats + bible_id
- web_app.py: NEW - FastAPI dashboard RTL Arabic - READY
- main.py: Deployment foundation - READY (needs BOT_TOKEN env)
- persistence/: SQLite ready, migration path documented
- Tests: test_meta_audit.py - 14 PASS (P0.9 - no real credentials)

## DONE WITH EVIDENCE
- [PASS] Meta audit: missing creds → FAILED BLOCKED_CREDENTIALS
- [PASS] No secret leak: EAA_REDACTED
- [PASS] Error classification: 190 auth, 200 perm, 4/17 rate_limit retryable, 2207001 invalid_media
- [PASS] No receipt → not PUBLISHED
- [PASS] HTTP 200 is NOT proof - ENFORCED
- [PASS] Evidence record required fields present
- Publisher ZIP: short_drama_video_agent_v1.3_AGENT_APP_COMPLETE.zip (88k)

## BLOCKED - HUMAN ACTION REQUIRED
- [BLOCKED] Real TikTok credentials: TIKTOK_CLIENT_KEY, CLIENT_SECRET, ACCESS_TOKEN missing - requires developer.tiktok.com app registration + OAuth video.publish + app review for PUBLIC_TO_EVERYONE. Cannot proceed without human OAuth.
- [BLOCKED] Real YouTube credentials: YOUTUBE_CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN missing - requires GCP project + YouTube Data API v3 + OAuth consent + verification. Unverified projects forced PRIVATE.
- [BLOCKED] Real Meta credentials: META_APP_ID, SECRET, PAGE_ACCESS_TOKEN, IG_USER_ID, PAGE_ID missing - requires developers.facebook.com app + instagram_content_publish permission + Business account linked to Page + public video_url hosting. Page token never expires via /me/accounts.
- [BLOCKED] Public video_url hosting: Instagram requires public HTTPS URL that Meta cURLs directly (no auth wall). Need S3/Cloudinary/R2 public bucket.
- [BLOCKED] Muse Video API: MUSE_API_KEY missing - actual video generation requires live endpoint.

## NEXT AUTONOMOUS ACTION (No human needed)
1. Source → Done, now in repo
2. Audit Meta → Done PASS
3. Meta patch → Done P0.3 hardened
4. Tests → Done PASS
5. TikTok audit → TODO - implement TikTokPublisher real flow: INIT_URL https://open.tiktokapis.com/v2/post/publish/video/init/ + chunked 5-64MB + STATUS_URL polling → video_id, error taxonomy, evidence record (can be done without real creds, blocked same as Meta)
6. YouTube audit → TODO - implement YouTubePublisher resumable: POST /upload/youtube/v3/videos?uploadType=resumable → Location → PUT chunks → videoId, quota handling, forced PRIVATE note
7. Deployment → TODO - Dockerfile + railway.toml ready, needs Railway connector + env vars set in platform (not chat)
8. E2E verification → TODO - after human provides creds in platform env, run real publish with SELF_ONLY privacy to verify receipt
9. Documentation → TODO - update DEPLOYMENT.md with real flow

## DO NOT CHANGE
- PublicationState enum: REQUESTED → SUBMITTED → PLATFORM_RESPONSE → RECEIPT_VERIFIED → PUBLISHED → FAILED + others
- publications dict structure + idempotency_key logic
- bot.py Arabic parser: اضاءة اغمق افتح قص كابشن اسرع ابطأ
- Evidence Gate: receipt None = FAILED
- No second architecture

## EXECUTION SETUP REQUIRED (One-time - 5 steps from user)
1. Put original files in GitHub repo or Project Files/Library → avoid SOURCE_ACCESS_BLOCKED
2. Connect GitHub to project → can read/edit/review instead of ZIP loop
3. Connect Railway/Vercel/Convex/Notion → verify state + continue operations
4. Put secrets inside platform itself (Railway env vars) not in chat → use env var names only
5. Single stop rule: only stop when money/upgrade/2FA/legal approval/OAuth human required → otherwise continue autonomously

## REPO STRUCTURE PROPOSED
```
alkadyenjy2/
├── short-drama-video-agent/  <- this repo
│   ├── README.md
│   ├── STATUS.md (this file)
│   ├── .env.example
│   ├── docs/
│   ├── tests/
│   ├── src/ (future)
│   ├── bot.py, publisher.py, visual_factory.py, web_app.py, main.py
│   └── persistence/
├── za-media-ai-growth-engine
├── ze-outsourcing
└── enjY-ai-coo
```
