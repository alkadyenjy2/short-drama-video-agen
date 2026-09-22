# short-drama-video-agent - DRAMA AI

> قصص تريندينج.. بتتولد في ثواني - 9:16 Vertical Drama Agent

## Architecture
- `bot.py` - Telegram bot + Approval Gate + Arabic edit parser + versioning v1→v2→v3
- `visual_factory.py` - Agent Core: parse to beats, Character Bible (consistent face), prompt generation
- `publisher.py` - P0.3 Hardened: TikTok/YouTube/Instagram/Facebook - Evidence Gate ENFORCED, no fake success
- `persistence/` - SQLite repo + migration path to Postgres
- `main.py` + `health.py` + `web_app.py` - Deployment foundation + Dashboard
- `trending_stories.json` - Trending stories source

## Quick Start
```bash
pip install -r requirements.txt
# .env from .env.example
python main.py  # bot polling + health server
# or
python web_app.py  # marketing dashboard
```

## Evidence Gate (Critical)
- Never return success=True without real receipt (media_id/video_id)
- receipt=None → FAILED, never PUBLISHED
- HTTP 200 is NOT proof of publication
- No secrets in logs (EAA_REDACTED)

## Platforms ROI
1. TikTok 70% - fastest growth + Creativity Program
2. YouTube Shorts 20% - long-term revenue 45%
3. Instagram Reels 10% - B2B clients

See STATUS.md for current state.
