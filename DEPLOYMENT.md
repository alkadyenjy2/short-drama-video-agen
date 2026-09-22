# DEPLOYMENT.md - Video Agent v1.2 P0 Real Publisher APIs

## Scope
v1.2 P0: Deployment foundation + Real Publisher adapters (implementation-ready, Evidence Gate enforced)
No fake PUBLISHED, no fake receipts.

## Source of Truth
short_drama_video_agent_v1.2_deployment_ready.zip
Contains: bot.py, main.py, publisher.py (P0), health.py, persistence/repository.py, requirements.txt, Dockerfile, railway.toml, .env.example, trending_stories.json

## Architecture Lock
Trend Scanner -> Story/Edit Agent -> Telegram Approval Gate -> Operation Log + Versioning -> Publisher -> Evidence Gate -> Audit
This architecture is LOCKED, cannot be replaced.

## P0 Publisher APIs Status

### TikTok Content Posting API
- API: https://open.tiktokapis.com/v2/post/publish/video/init/ + /status/fetch/ + /creator_info/query/
- Auth: OAuth 2.0
- Scopes: user.info.basic + video.publish (Direct Post) + video.upload (Inbox)
- Modes: Direct Post (live immediately) + Upload to Inbox (draft)
- Privacy: SELF_ONLY forced until app audit, then PUBLIC_TO_EVERYONE
- Media: MP4/MOV/WebM, up to 4GB, up to 10 min, 9:16 recommended, chunked 5-64MB sequential max 1000 chunks
- PULL_FROM_URL: Requires verified domain, HTTPS, no redirects
- Rate: 6 req/min per token on init, 30 req/min on status, ~15-20 posts/day per creator
- State: REQUESTED->SUBMITTED->PLATFORM_RESPONSE (publish_id)->RECEIPT_VERIFIED (video_id via status fetch)->PUBLISHED
- Receipt: publish_id + video_id from /status/fetch/ PUBLISH_COMPLETE
- App Review: 5-10 business days, demo video, privacy policy, business entity required
- Evidence Gate: No publish_id + video_id = FAILED, never PUBLISHED
- Blocker: Needs TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_ACCESS_TOKEN (OAuth), domain verification for PULL_FROM_URL

### YouTube Data API v3
- API: POST https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable + videos.insert
- Auth: OAuth 2.0 (service accounts NOT supported)
- Scope: https://www.googleapis.com/auth/youtube.upload (sensitive, needs Google verification)
- Flow: resumable init -> Location header -> PUT chunks with Content-Range -> response id (videoId)
- Verify: GET /youtube/v3/videos? id=videoId & part=status to check processingStatus=processed
- Quota: 10k units/day default, 1600 per upload = 6 uploads/day max without increase
- Critical: Unverified projects after July 28 2020 forced to PRIVATE - cannot upload public until verified
- State: REQUESTED->SUBMITTED->PLATFORM_RESPONSE (Location)->RECEIPT_VERIFIED (videoId)->PUBLISHED
- Receipt: videoId (e.g. dQw4w9WgXcQ)
- App Review: 3-5 days initial verification, domain verification, privacy policy, demo video
- Evidence Gate: No videoId = FAILED
- Blocker: Needs YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN, Google verification for public

### Meta Graph API - Instagram + Facebook
- Instagram: POST /{ig-user-id}/media with media_type=REELS, video_url (public HTTPS, Meta cURLs it) -> container_id -> poll GET /{container-id}?fields=status_code until FINISHED -> POST /{ig-user-id}/media_publish with creation_id -> media_id receipt
- Facebook: POST https://graph-video.facebook.com/{version}/{page-id}/videos multipart/form-data -> video_id receipt, as of June 2025 all Facebook videos are Reels
- Auth: OAuth 2.0 server-side, Page access token never expires if derived from long-lived user token (60 days)
- Permissions: pages_manage_posts, pages_read_engagement, instagram_content_publish, instagram_basic
- Account: Business or Creator only, linked to Page, PPA if required
- Media: MP4 H.264, 100MB Reels up to 1GB standard, up to 90s (some 15 min), 1080x1920 9:16
- Rate: 50 posts/24h combined feed/Reels/Stories (some report 100 per 24h moving window)
- Resumable upload via rupload.facebook.com for large files
- State: REQUESTED->SUBMITTED->PLATFORM_RESPONSE (container_id)->RECEIPT_VERIFIED (media_id)->PUBLISHED
- Receipt: media_id (Instagram), video_id (Facebook)
- App Review: 2-7 business days, Business Verification, privacy policy, screencast
- Evidence Gate: No media_id/video_id = FAILED
- Blocker: Needs META_APP_ID, META_APP_SECRET, META_PAGE_ACCESS_TOKEN, META_IG_USER_ID, META_PAGE_ID, public video URL hosting

### Evidence Gate - Authoritative
- Never fake PUBLISHED
- Never fake receipt
- Never hardcoded success
- Never success based only on HTTP 200 or upload acceptance
- No fabricated webhook, screenshot, API response
- If no receipt/status verifiable: FAILED or PENDING_VERIFICATION, NOT PUBLISHED
- State machine: REQUESTED->SUBMITTED->PLATFORM_RESPONSE->RECEIPT_VERIFIED->PUBLISHED

### Royalty Verification
- No ROYALTY_EARNED from views, estimated RPM, engagement, fixed assumptions
- Only: verified platform data, official webhook, transaction/revenue record, evidence from provider
- Meta: X-Hub-Signature-256 HMAC verification with app secret
- YouTube: Analytics API revenue reports (separate OAuth)
- TikTok: Creator Fund API if available
- Else: PENDING_VERIFICATION

## Local Run
cp .env.example .env
# Edit .env: BOT_TOKEN from @BotFather
pip install -r requirements.txt
python main.py
# Health: curl http://localhost:8000/health -> {"status":"ok","persistence":"ok","version":"v1.2"}

## Docker
docker build -t video-agent:v1.2 .
docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/app/data video-agent:v1.2

## Env Classification
| Variable | Classification | When |
|---|---|---|
| BOT_TOKEN | REQUIRED_NOW + SECRET | Now |
| DATABASE_PATH | OPTIONAL | Now |
| TIKTOK_* | REQUIRED_LATER + SECRET | Publisher real - after OAuth/app setup |
| YOUTUBE_* | REQUIRED_LATER + SECRET | Publisher real - after OAuth/verification |
| META_* | REQUIRED_LATER + SECRET | Publisher real - after OAuth/Business Verification |
| DATABASE_URL | REQUIRED_LATER | Postgres migration after deployment proof |

Never commit secrets. All credentials env or provider-managed.

## Security
- No BOT_TOKEN in prompt output, no secrets in logs, no commit secrets, no hardcoded keys/tokens, no credentials in source, no access tokens in logs
- All credentials env secrets

## Cost/Quota Rule
Free -> Free Tier -> Existing Infrastructure -> Paid
Check cost/necessity before paid API, build minutes, deployment quota, provider quota, AI credits, storage, external calls
No new subscription without human approval

## No Duplicate Architecture
Forbidden: Temporal alternative, n8n orchestrator new, Make replacement, second Telegram router, second approval system, second persistence system, second Evidence Gate, duplicate publisher framework
Reuse existing.

## Verification Requirements per Implementation
SOURCE: exact file, exact function/class, what was inspected
CHANGE: exact modification, why required
EXECUTION: exact test executed, input, output, status
EVIDENCE: provider response, receipt, artifact, log, URL, ID
BLOCKER: real reason, what user action required, technical vs credential/provider approval
Do not convert blocker to PASS.

## Next: Deployment Boundary
Railway deployment is separate gate. No claim deployment succeeded without: Deployment ID, Public URL, /health=200, persistence healthy, runtime logs, Telegram init evidence. No fake deployment data.
