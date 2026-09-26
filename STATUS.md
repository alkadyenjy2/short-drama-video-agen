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
5. TikTok audit → Done PASS - flow markers + blocked-credential Evidence Gate verified
6. YouTube audit → Done PASS - resumable init + Location + PUT/Content-Range + videoId receipt gate + quota/error markers verified against official Google API flow; real OAuth remains blocked
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

## VERIFIED RUNTIME UPDATE (2026-09-27)
- [VERIFIED] Railway production deployment `e41bcade-f1c5-4ca3-9340-5d60ce204782` is SUCCESS on commit `500a2ca9fe0ea725877ce0276f1fac5679e70246`.
- [VERIFIED] Production `/health` = HTTP 200; persistence=ok; editor.ready=true; FFmpeg=/usr/bin/ffmpeg; FreeSans available.
- [VERIFIED] Production `/editor/status` = HTTP 200 with editor.ready=true.
- [VERIFIED] Local audit suite: video editor 19/19, runtime pipeline 1/1, Meta audit PASS, TikTok audit PASS; process exit 0.
- [VERIFIED] Telegram behavioral E2E: video was registered as active video with 65,419 bytes and SHA256 `9f1822b3345180708412829e5aab2739aea82b7896562c32c56d13c2bdc51b6c`; command `خلي الإضاءة أغمق` produced `EDITED`, operation=lighting, 39,501 bytes, SHA256 `eb84e4b933fb9bf0ed5e46384ed6df29c2159b6abc8c270686ab6355cbc80d18`.
- [BLOCKED] I2V provider generation remains credential/quota blocked: Railway production has no `HF_TOKEN` variable; public ZeroGPU route previously returned quota exhaustion. No I2V success is claimed.
- [IMPORTANT] `railway-src/main` is the production canonical repo and is unrelated in Git history to `origin/main` (`alkadyenjy2/alkadyenjy2-short-drama-video-agent`). Do not merge or force-push between them without an explicit migration plan.
