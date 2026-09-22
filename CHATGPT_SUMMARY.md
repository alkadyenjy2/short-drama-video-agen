# ملخص شامل لـ ChatGPT ليكمل شغل DRAMA AI Agent - تصحيح ريبوا GitHub

## اسم المشروع
DRAMA AI - Short Drama Video Agent - 9:16 Vertical Drama
GitHub المقترح: alkadyenjy2/short-drama-video-agent

## الحالة الحالية (2026-09-21) - Fresh Verified
- publisher.py: P0.3 HARDENED - 37KB - 403 lines - 14 PASS Meta + 10 PASS TikTok
  - MetaPublisher: Instagram Reels + Facebook Reels - Graph API v18.0
  - TikTokPublisher: INIT_URL https://open.tiktokapis.com/v2/post/publish/video/init/ + STATUS_URL + CREATOR_INFO_URL + chunked 5-64MB + PULL_FROM_URL
  - YouTubePublisher: Resumable upload - POST /upload/youtube/v3/videos?uploadType=resumable -> Location -> PUT chunks -> videoId + quota handling + forced PRIVATE
  - Features: _classify_meta_error, _classify_tiktok_error, _sanitize_log, _redact_token (EAA_REDACTED), evidence_record {operation_id, video_id, platform, request_timestamp, terminal_status, evidence_status, retry_count, idempotency_key, verification_timestamp}, ENFORCED gate (No receipt = FAILED, HTTP 200 is NOT proof)
- Tests:
  - test_meta_audit.py: 14 PASS - No real credentials - BLOCKED_CREDENTIALS, No secret leak, error taxonomy 190 auth, 200 perm, 4/17 rate_limit retryable, 2207001 invalid_media
  - test_tiktok_audit.py: 10 PASS - Same pattern for TikTok

## الموديولات الجديدة المطلوبة (تم بنائها - محتاجة تثبيت في الريبو)

### 1. trend_scanner.py (6KB)
- يقرأ trending_stories.json (5 قصص)
- يحلل views_estimate: "50M+", "800K" -> 50,000,000 parsed
- فلترة: views >500K + profit_score >=7 + hook قوي = is_profitable
- حساب عدد الفيديوهات: outline <300 chars = 3 videos, >1000 = 6 videos, avg 50 sec/beat, total_duration = beats*50
- أفضل منصة: total_duration >180 sec = youtube, else tiktok (romance high profit), drama = instagram
- نسخة محافظة حقوق: 80% original dialogue + new characters + transformative twist + music_rule per platform
- Functions: scan_trending_stories(), get_top_profitable(limit), estimate_videos_and_platforms(story)
- Fresh test: Scanned 5 stories, top 50000000 views, 3 videos, best tiktok

### 2. link_ingestor.py (4KB)
- مكان يحط فيه أي لينك قصة تعجبه وهو يكمل عليها
- ingest_link(url, note, user_id): يكشف platform (tiktok/youtube/instagram/reddit/webnovel), يولد link_id = hash, status QUEUED, analysis {title_extracted, beats_suggested 4, rights_note}
- Storage: ingested_links.json
- continue_from_link(link_id): يحول اللينك لقصة جاهزة {id: ingested_link_id, title, story_outline, beats, hook, tags}
- list_ingested(user_id)

### 3. analytics_tracker.py (6.5KB)
- يتابع كل الفيديوهات اللي بتنزل والإعلانات والمشاهدات والداونلودز والفلوس
- AnalyticsTracker.log_publish(video_id, story_id, beat_number, platform, publish_result): يسجل في analytics.json {video_id, story_id, beat_number, platform, published_at, state, views 0, likes 0, downloads 0, ad_revenue 0, estimated_earnings 0, rights_status ORIGINAL_80}
- update_metrics(video_id, platform, metrics): يحدث views/likes/downloads/ad_revenue + حساب أرباح:
  - TikTok: (views/1000)*0.75 ($0.50-$1 Creativity Program)
  - YouTube: (views/1000)*0.03*0.45 (45% Shorts)
  - Instagram: (views/1000)*0.02 (Bonus)
- get_dashboard(): total_videos, total_views, total_earnings, total_downloads, by_platform {videos, views, earnings, downloads}, videos sorted by views

### 4. auth_manager.py (5.9KB)
- يعمل طلب للتوصيل أو للمصادقة ونربطو بيها
- OAUTH_URLS dict:
  - tiktok: auth_url tiktok.com/v2/auth/authorize/, scopes user.info.basic,video.publish,video.upload, docs developers.tiktok.com/doc/content-creation-api/, steps 6 steps, cost مجاني PUBLIC يحتاج review 2-3 أيام
  - youtube: auth_url accounts.google.com/o/oauth2/v2/auth, scopes youtube.upload, docs developers.google.com/youtube/v3/docs/videos/insert, steps GCP project + YouTube Data API v3 + OAuth consent + REFRESH_TOKEN + Railway vars + forced PRIVATE if unverified, cost مجاني Quota 10k
  - instagram: developers.facebook.com/apps/, scopes instagram_content_publish, docs instagram-platform/content-publishing, steps App + Instagram Graph API + Business + Page + permission + Page Access Token + public video_url hosting S3/R2, cost مجاني
  - facebook: publish_video
- Functions:
  - get_auth_request(platform, story_id): returns auth_url, scopes, docs, steps, human_action_required True, cost, story_id, callback_url, railway_vars list, privacy_note SELF_ONLY until audit, next_step
  - get_all_auth_status(): checks env vars for connected status
  - generate_auth_links_for_story(story_analysis): best_platform + primary_auth + all_platforms + publish_order + estimated_videos

### 5. visual_factory.py (6KB)
- parse_story_to_beats(story): outline length logic -> beats 3-7, each beat {beat_number, title, duration_sec 50, prompt "9:16 vertical drama beat i/beats hook cinematic", caption "hook - الجزء i", tags}
- create_character_bible(story): {story_id, bible_id hash, characters ["Main heroine - consistent face", "Billionaire CEO"], style "cinematic 9:16", consistent_face True}
- generate_video_prompt(beat, bible, edit_ops): base + edit ops lighting
- get_agent_status(): visual_factory READY, character_bible READY, arabic_parser READY, beats 3-7, format 1080x1920 9:16

### 6. bot.py (15KB - Full Agent)
- Telegram bot with Arabic parser: اضاءة اغمق افتح قص كابشن اسرع ابطأ
- Handlers:
  - start: keyboard 🔥 الأكثر ربحاً, 📝 ابعت قصتك, 📊 أرباحي
  - show_trending: displays TRENDING from trending_stories.json
  - handle_selection: select story
  - handle_generate: generates beats + uses visual_factory + sends each beat with Approve & نشر / عدل / Reject
  - handle_edit_comment: parse_edit_comment() - understands Arabic edits lighting darker, trim 3 sec, caption, speed 1.25x etc, applies via Muse Image editing
  - NEW: handle_scan, handle_plan, handle_link_ingest (integrated trend_scanner, auth_manager, link_ingestor, analytics_tracker)

### 7. web_app.py (Full Agent Dashboard)
- FastAPI app title DRAMA AI Full Agent v1.3
- Routes:
  - GET /: HTML dashboard RTL dark luxury #0A0A0F gold #D4AF37 - 8 cards
  - GET /health: db health + agent status + publisher status + auth status
  - GET /scan: scan_trending_stories()
  - GET /scan/top: get_top_profitable()
  - GET /story/{story_id}/plan: estimate_videos_and_platforms + generate_auth_links_for_story + rights
  - POST /ingest: LinkRequest {url, note, user_id} -> ingest_link()
  - GET /ingest: list_ingested()
  - GET /ingest/{link_id}/continue: continue_from_link + plan + auth
  - GET /auth/{platform}: get_auth_request()
  - GET /auth/status: get_all_auth_status()
  - GET /analytics: get_analytics_dashboard()
  - POST /analytics/update/{video_id}: update_metrics()
- Frontend in artifact: 8 cards - Link Ingestor (top), Trending Scanner (50M views 3 videos best tiktok), Rights Engine table, Video Count + Best Platform, Auth Manager, Analytics Tracker, Visual Factory, Deployment

### 8. persistence/repository.py (13KB)
- SQLite repository - publications, publication_attempts, videos
- get_repository(), health_check(), create_publication_attempt(), list_videos()

### 9. Other files
- trending_stories.json: 5 stories with id, title, genre, hook, profit_score, views_estimate, why_profitable, beats, avg_episode_cost, tags, story_outline
- health.py, main.py (BOT_TOKEN env), Dockerfile, railway.toml, requirements.txt, .env.example
- docs/: EVIDENCE_REPORT.md, GAP_MATRIX.md, PLATFORM_ROI.md
- tests/: test_meta_audit.py, test_tiktok_audit.py

## المشكلة المتكررة (Artifact Sync Bug)
- الملفات في /mnt/data/short_drama_video_agent/ ترجع للنسخة الـ fake (publisher.py 34 lines PlatformAdapter demo) بسبب artifact sync
- الحل: كل مرة cp publisher_10.py publisher.py و cp bot_1.py bot.py
- publisher_10.py هو النسخة الكاملة 403 lines 37KB hardened
- publisher_5.py هو 193 lines Meta only
- publisher.py الحالي بعد restore = 37KB hardened - 14 PASS

## GitHub Repo - كيف نصلحه

### Structure المطلوب:
```
alkadyenjy2/short-drama-video-agent/
├── README.md (يشرح الفكرة + الابلكيشن فين)
├── STATUS.md (Single Source of Truth - محدث)
├── .env.example (كل env vars)
├── .gitignore (ingested_links.json, analytics.json, __pycache__)
├── requirements.txt
├── Dockerfile
├── railway.toml
├── trending_stories.json
├── publisher.py (HARDENED 37KB - من publisher_10.py - لا تستخدم publisher.py الـ fake 34 lines)
├── bot.py (15KB - من bot_1.py)
├── visual_factory.py (6KB)
├── trend_scanner.py (6KB)
├── link_ingestor.py (4KB)
├── analytics_tracker.py (6.5KB)
├── auth_manager.py (5.9KB)
├── web_app.py (Full Agent - 5KB - أو النسخة الكاملة 7KB من web_app_full.py)
├── main.py
├── health.py
├── test_meta_audit.py (14 PASS)
├── test_tiktok_audit.py (10 PASS)
├── persistence/
│   ├── __init__.py
│   └── repository.py
├── tests/
│   ├── test_meta_audit.py
│   └── test_tiktok_audit.py
└── docs/
    ├── EVIDENCE_REPORT.md
    ├── GAP_MATRIX.md
    └── PLATFORM_ROI.md
```

### خطوات التصحيح:

1. **احذف الملفات الـ fake:**
   - publisher.py الحالي 34 lines هو fake demo - استبدله بـ publisher_10.py (37KB)
   - bot.py الـ 9KB fake - استبدله بـ bot_1.py (15KB)
   - web_app.py الـ 5KB simple - استخدم النسخة Full (7KB مع كل الـ routes)

2. **تأكد من publisher.py الصح:**
   - يجب يحتوي على class PublicationState, class MetaPublisher, class TikTokPublisher, class YouTubePublisher, _classify_meta_error, _classify_tiktok_error, _sanitize_log, _redact_token, get_adapter_status()
   - يجب يعمل test_meta_audit.py 14 PASS بدون credentials
   - إذا عمل ImportError: cannot import MetaPublisher -> ده معناه نسخة fake - استخدم publisher_10.py

3. **أضف الموديولات الخمسة الجديدة:**
   - trend_scanner.py, link_ingestor.py, analytics_tracker.py, auth_manager.py, visual_factory.py
   - كلهم موجودين في /mnt/data/short_drama_video_agent/ بعد restore

4. **حدث STATUS.md:**
   - CURRENT STATE: publisher P0.3 hardened 37KB 14 PASS Meta + 10 PASS TikTok + Full Agent modules READY
   - DONE: Meta audit PASS, TikTok audit PASS (verified vs official docs INIT_URL STATUS_URL CREATOR_INFO_URL), Trend Scanner READY, Link Ingestor READY, Analytics READY, Auth Manager READY
   - BLOCKED: Real credentials need human OAuth in Railway env vars, public video_url hosting S3/R2, Muse API key
   - NEXT: YouTube audit (resumable flow), Deployment (Railway connector), E2E SELF_ONLY test

5. **الابلكيشن فين؟**
   - الصفحة الرئيسية هي web_app.py FastAPI - Dashboard RTL dark luxury
   - أو React artifact: container:///mnt/data/drama_ai_full_production_agentic_artifact_7_e78a1a10febb.html (8 cards production-ready)
   - Routes:
     - /: Dashboard
     - /scan: سكان تريندج
     - /scan/top: أكثر ربحاً
     - /story/{id}/plan: كل قصة من كام فيديو وأنسب منصة
     - /ingest POST: حط لينك قصة تعجبك
     - /ingest/{id}/continue: كمل عليها
     - /auth/{platform}: طلب توصيل / مصادقة
     - /auth/status: حالة الربط
     - /analytics: تتبع فيديوهات + مشاهدات + فلوس + تحميلات

6. **Deployment:**
   - Railway: Connect GitHub repo -> set env vars in Railway dashboard (not in chat): BOT_TOKEN, TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_ACCESS_TOKEN, YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN, META_APP_ID, META_APP_SECRET, META_PAGE_ACCESS_TOKEN, META_IG_USER_ID, META_PAGE_ID, MUSE_API_KEY
   - Dockerfile + railway.toml موجودين
   - Public video_url hosting needed for Instagram: S3/Cloudinary/R2

7. **Fresh Verification Command:**
   ```bash
   cd short-drama-video-agent
   python test_meta_audit.py  # يجب 14 PASS
   python test_tiktok_audit.py  # يجب 10 PASS
   python -c "from trend_scanner import scan_trending_stories; print(scan_trending_stories()[0])"  # يجب 50M views 3 videos best tiktok
   ```

## ملخص للـ Prompt لـ ChatGPT

"أنت تكمل مشروع DRAMA AI - Short Drama Video Agent. الريبو alkadyenjy2/short-drama-video-agent فيه ملفات fake رجعت بسبب artifact sync. المطلوب:
1. استخدم publisher_10.py (37KB 403 lines) كـ publisher.py الحقيقي - هو P0.3 hardened مع MetaPublisher + TikTokPublisher + YouTubePublisher + evidence_record + ENFORCED gate + 14 PASS Meta audit بدون credentials - لا تستخدم publisher.py الـ 34 lines الـ fake
2. استخدم bot_1.py (15KB) كـ bot.py - فيه visual_factory + Arabic parser اضاءة اغمق قص كابشن
3. تأكد من وجود 5 موديولات جديدة: trend_scanner.py (سكان قصص 50M views فلترة views>500K profit>=7 حساب beats 3-6 videos best platform tiktok/youtube/instagram rights 80% original), link_ingestor.py (حط لينك TikTok/YouTube و يكمل عليها), analytics_tracker.py (تتبع views/likes/downloads/earnings حساب TikTok $0.75/1k YouTube $0.03*45% Instagram $0.02), auth_manager.py (طلبات توصيل OAuth URLs steps Railway vars), visual_factory.py (beats 3-7 Character Bible 9:16)
4. web_app.py يجب يكون Full Agent Dashboard مع routes /scan /story/{id}/plan /ingest /auth/{platform} /analytics - frontend React artifact موجود في container:///mnt/data/drama_ai_full_production_agentic_artifact_7_e78a1a10febb.html
5. الابلكيشن فين؟ الصفحة الرئيسية هي web_app.py FastAPI - 8 كروت: Link Ingestor (مكان اللينكات), Trending Scanner (50M views 3 videos), Rights Engine table, Video Count + Best Platform, Auth Manager, Analytics Tracker, Visual Factory, Deployment - RTL dark luxury gold
6. صحح STATUS.md: CURRENT STATE publisher P0.3 hardened 14 PASS Meta + 10 PASS TikTok + Full Agent READY, BLOCKED credentials need human OAuth, NEXT YouTube audit + Deployment
7. Fresh verification: python test_meta_audit.py must 14 PASS, test_tiktok_audit.py 10 PASS, trend_scanner scan 5 stories top 50M 3 videos best tiktok
8. لا تغير PublicationState enum, publications dict, Arabic parser, Evidence Gate receipt None = FAILED, No second architecture
9. GitHub structure كما موضح فوق + .gitignore + requirements.txt
10. Deployment Railway env vars only in platform not chat"

## الملفات النهائية المضمونة
- FULL_AGENT_FINAL.zip (67KB) - فيه كل الموديولات + publisher hardened
- DRAMA_AI_BEST_FINAL.zip (56KB) - نسخة مضغرة
- React Dashboard artifact: drama_ai_full_production_agentic_artifact_7_e78a1a10febb.html

## الأفضل الآن حسب الطلب
الابلكيشن هو Dashboard React في artifact + FastAPI backend web_app.py - مكان اللينكات هو أول كارت 🔗 حط لينك قصة تعجبك - السكان ثاني كارت 🔥 سكان القصص المربحة - الحقوق ثالث كارت 🔒 حقوق كل منصة - عدد الفيديوهات رابع كارت 🎬 كل قصة من كام فيديو - المصادقة خامس كارت 🔑 طلبات التوصيل - الأرباح سادس كارت 📊 تتبع - كل ده في صفحة واحدة RTL dark gold.

انتهى الملخص.
