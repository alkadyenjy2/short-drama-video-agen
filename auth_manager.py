# auth_manager.py - يعمل طلب للتوصيل او للمصادقة ونربطو بيها
import os
from typing import Dict
from datetime import datetime

OAUTH_URLS = {
    "tiktok": {
        "auth_url": "https://www.tiktok.com/v2/auth/authorize/",
        "scopes": "user.info.basic,video.publish,video.upload",
        "docs": "https://developers.tiktok.com/doc/content-creation-api/",
        "steps": [
            "1. انشئ app على https://developers.tiktok.com",
            "2. فعل scopes: user.info.basic + video.publish + video.upload",
            "3. حط Redirect URI: https://your-app.com/callback/tiktok",
            "4. خد CLIENT_KEY + CLIENT_SECRET",
            "5. اعمل OAuth flow للحصول على ACCESS_TOKEN + REFRESH_TOKEN",
            "6. حطهم في Railway Variables: TIKTOK_CLIENT_KEY, SECRET, ACCESS_TOKEN"
        ],
        "human_action_required": True,
        "cost": "مجاني - لكن PUBLIC_TO_EVERYONE يحتاج app review (2-3 أيام)"
    },
    "youtube": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "scopes": "https://www.googleapis.com/auth/youtube.upload",
        "docs": "https://developers.google.com/youtube/v3/docs/videos/insert",
        "steps": [
            "1. انشئ project على https://console.cloud.google.com",
            "2. فعل YouTube Data API v3",
            "3. انشئ OAuth consent screen + credentials (OAuth Client ID)",
            "4. خد CLIENT_ID + CLIENT_SECRET",
            "5. اعمل OAuth للحصول على REFRESH_TOKEN",
            "6. حطهم في Railway: YOUTUBE_CLIENT_ID, SECRET, REFRESH_TOKEN",
            "7. Unverified projects forced PRIVATE - لازم verification for PUBLIC"
        ],
        "human_action_required": True,
        "cost": "مجاني - Quota 10k/day default"
    },
    "instagram": {
        "auth_url": "https://developers.facebook.com/apps/",
        "scopes": "instagram_content_publish,pages_show_list",
        "docs": "https://developers.facebook.com/docs/instagram-platform/content-publishing",
        "steps": [
            "1. انشئ app على https://developers.facebook.com",
            "2. اضف Instagram Graph API product",
            "3. اربط Business Instagram account بـ Facebook Page",
            "4. فعل permission: instagram_content_publish",
            "5. خد Page Access Token (long-lived via /me/accounts)",
            "6. حطهم في Railway: META_APP_ID, SECRET, PAGE_ACCESS_TOKEN, IG_USER_ID, PAGE_ID",
            "7. لازم public video_url hosting (S3/R2) لان Meta بتعمل curl للفيديو"
        ],
        "human_action_required": True,
        "cost": "مجاني"
    },
    "facebook": {
        "auth_url": "https://developers.facebook.com/apps/",
        "scopes": "pages_show_list,pages_read_engagement,publish_video",
        "docs": "https://developers.facebook.com/docs/page-videos",
        "steps": ["نفس خطوات انستجرام + publish_video permission"],
        "human_action_required": True,
        "cost": "مجاني"
    }
}

def get_auth_request(platform: str, story_id: str = None) -> Dict:
    platform = platform.lower()
    if platform not in OAUTH_URLS:
        return {"error": f"Unknown platform {platform}", "supported": list(OAUTH_URLS.keys())}
    
    info = OAUTH_URLS[platform]
    return {
        "platform": platform,
        "auth_url": info["auth_url"],
        "scopes": info["scopes"],
        "docs": info["docs"],
        "steps": info["steps"],
        "human_action_required": info["human_action_required"],
        "cost": info["cost"],
        "story_id": story_id,
        "callback_url": f"/callback/{platform}?story_id={story_id or ''}",
        "railway_vars": {
            "tiktok": ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN"],
            "youtube": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"],
            "instagram": ["META_APP_ID", "META_APP_SECRET", "META_PAGE_ACCESS_TOKEN", "META_IG_USER_ID", "META_PAGE_ID"],
            "facebook": ["META_APP_ID", "META_APP_SECRET", "META_PAGE_ACCESS_TOKEN", "META_PAGE_ID"]
        }.get(platform, []),
        "privacy_note": "SELF_ONLY until audit - لا تنشر PUBLIC إلا بعد اختبار SELF_ONLY + verification",
        "rights_note": f"Platform {platform} requires 80% original content - no reupload",
        "next_step": f"بعد ما تحط الـ tokens في Railway → /publish/{platform}/{story_id or 'test'}?privacy=SELF_ONLY للاختبار"
    }

def get_all_auth_status() -> Dict:
    import os
    status = {}
    for platform in OAUTH_URLS.keys():
        if platform == "tiktok":
            ok = bool(os.getenv("TIKTOK_CLIENT_KEY") and os.getenv("TIKTOK_ACCESS_TOKEN"))
        elif platform == "youtube":
            ok = bool(os.getenv("YOUTUBE_CLIENT_ID") and os.getenv("YOUTUBE_REFRESH_TOKEN"))
        elif platform in ["instagram", "facebook"]:
            ok = bool(os.getenv("META_APP_ID") and os.getenv("META_PAGE_ACCESS_TOKEN"))
        else:
            ok = False
        status[platform] = {"connected": ok, "auth_url": OAUTH_URLS[platform]["auth_url"], "needs_human": not ok}
    return status

def generate_auth_links_for_story(story_analysis: Dict) -> Dict:
    best = story_analysis.get("best_platform", "tiktok")
    return {
        "best_platform": best,
        "primary_auth": get_auth_request(best, story_analysis.get("story_id") or story_analysis.get("id")),
        "all_platforms": {p: get_auth_request(p, story_analysis.get("story_id") or story_analysis.get("id")) for p in ["tiktok", "youtube", "instagram"]},
        "publish_order": f"1. {best} (SELF_ONLY test) → 2. YouTube Shorts (private) → 3. Instagram Reels",
        "estimated_videos": story_analysis.get("beats", 4),
        "total_duration": f"{story_analysis.get('total_duration_sec', 200)} sec"
    }
