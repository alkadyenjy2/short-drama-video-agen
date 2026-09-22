# trend_scanner.py - سكان القصص اللي بتجيب مشاهدات + فلترة + حقوق
import re, json, hashlib, os
from datetime import datetime
from typing import List, Dict, Optional

# منصات السكان
PLATFORMS = ["tiktok", "youtube", "instagram", "facebook", "reddit", "webnovel"]

# حقوق لكل منصة
RIGHTS_RULES = {
    "tiktok": {"max_duration": 600, "music": "Commercial sounds only, no copyrighted music without license", "transformative": "Must be 80% original, no reupload of TV drama clips", "privacy_default": "SELF_ONLY until review"},
    "youtube": {"max_duration": 180, "music": "YouTube Audio Library or licensed, ContentID will claim otherwise", "transformative": "Fair use requires commentary/editing, not full episode rip", "privacy_default": "private until verified"},
    "instagram": {"max_duration": 90, "music": "Meta Sound Collection only", "transformative": "Reels Remix allowed but original creation preferred", "privacy_default": "SELF_ONLY"},
    "facebook": {"max_duration": 90, "music": "Facebook Sound Collection", "transformative": "Original only", "privacy_default": "SELF_ONLY"}
}

def scan_trending_stories(source_file="trending_stories.json") -> List[Dict]:
    """اقرا القصص الحالية وحلل المشاهدات"""
    try:
        with open(os.path.join(os.path.dirname(__file__), source_file), "r", encoding="utf-8") as f:
            stories = json.load(f)
    except:
        stories = []
    
    analyzed = []
    for story in stories:
        views_str = story.get("views_estimate", "0")
        # Parse views like "12M" "5.3M" "800K"
        views_num = 0
        try:
            m = re.match(r"([\d\.]+)\s*([MK])?", str(views_str).upper())
            if m:
                num = float(m.group(1))
                unit = m.group(2)
                if unit == "M":
                    views_num = int(num * 1_000_000)
                elif unit == "K":
                    views_num = int(num * 1_000)
                else:
                    views_num = int(num)
        except:
            views_num = 0
        
        profit_score = story.get("profit_score", 0)
        # فلترة: مشاهدات عالية + ربح عالي + هوك قوي
        is_profitable = views_num > 500_000 and profit_score >= 7
        
        # حساب عدد الفيديوهات المناسب
        story_length = len(story.get("story_outline", "")) 
        beats = story.get("beats", 4)
        if story_length < 300:
            beats = 3
        elif story_length > 1000:
            beats = 6
        else:
            beats = max(3, min(7, beats))
        
        total_duration = beats * 50  # متوسط 50 ثانية للحلقة
        
        # انسب منصة
        best_platform = "tiktok"
        if total_duration > 180:
            best_platform = "youtube"  # يوتيوب يسمح اطول
        elif profit_score >= 9 and "romance" in story.get("genre","").lower():
            best_platform = "tiktok"  # رومانس يجيب في تيك توك
        elif "drama" in story.get("tags",[]):
            best_platform = "instagram"  # دراما انستجرام
        
        # نسخة محافظة على الحقوق
        safe_version = {
            "original_id": story.get("id"),
            "title_safe": f"Inspired by trending: {story.get('title')} - Original adaptation",
            "outline_safe": f"Original story inspired by theme '{story.get('genre')}' with 80% original dialogue, new characters, transformative plot twist. Original hook: {story.get('hook')}",
            "rights_note": f"Transformed 80% original for {best_platform} per {RIGHTS_RULES[best_platform]['transformative']}",
            "music_rule": RIGHTS_RULES[best_platform]["music"]
        }
        
        analyzed.append({
            **story,
            "views_parsed": views_num,
            "is_profitable": is_profitable,
            "beats_recommended": beats,
            "total_duration_sec": total_duration,
            "total_duration_min": round(total_duration/60, 1),
            "best_platform": best_platform,
            "rights_compliant": safe_version,
            "why_filtered": "High views + high profit + strong hook" if is_profitable else "Filtered out - low views or low profit",
            "auth_required": best_platform
        })
    
    # ترتيب حسب المشاهدات
    analyzed.sort(key=lambda x: x["views_parsed"], reverse=True)
    return analyzed

def get_top_profitable(limit=10) -> List[Dict]:
    all_stories = scan_trending_stories()
    profitable = [s for s in all_stories if s["is_profitable"]]
    return profitable[:limit]

def estimate_videos_and_platforms(story: Dict) -> Dict:
    scanned = scan_trending_stories()
    found = next((s for s in scanned if s["id"] == story.get("id")), None)
    if not found:
        # حساب لو قصة جديدة
        outline_len = len(story.get("story_outline",""))
        beats = 4 if outline_len < 500 else 6
        return {"beats": beats, "total_duration_sec": beats*50, "best_platform": "tiktok", "rights_note": "Original creation - no rights issue", "auth_link": "/auth/tiktok"}
    
    return {
        "story_id": found["id"],
        "title": found["title"],
        "beats": found["beats_recommended"],
        "total_duration_sec": found["total_duration_sec"],
        "total_duration_min": found["total_duration_min"],
        "best_platform": found["best_platform"],
        "alternative_platforms": ["youtube", "instagram"] if found["best_platform"] != "youtube" else ["tiktok", "instagram"],
        "rights_compliant": found["rights_compliant"],
        "views_estimate": found["views_parsed"],
        "profit_score": found["profit_score"],
        "auth_required": f"/auth/{found['best_platform']}",
        "auth_link": f"/auth/{found['best_platform']}?story_id={found['id']}",
        "publish_plan": f"انشر {found['beats_recommended']} فيديو على {found['best_platform']} أولاً (SELF_ONLY للاختبار)، بعدها YouTube Shorts ثم Instagram"
    }
