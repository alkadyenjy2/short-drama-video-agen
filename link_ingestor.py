# link_ingestor.py - مكان تحط فيه أي لينك لقصة أو فكرة تعجبك وهو يكمل عليها
import os, json, re, hashlib
from datetime import datetime
from typing import Dict, List

STORAGE_FILE = "ingested_links.json"

def _load():
    path = os.path.join(os.path.dirname(__file__), STORAGE_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def _save(data):
    path = os.path.join(os.path.dirname(__file__), STORAGE_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ingest_link(url: str, note: str = "", user_id: str = "default") -> Dict:
    """حط لينك لأي قصة (TikTok, YouTube, Reddit, Webnovel, Article) وهو يكمل عليها"""
    link_id = f"link_{hashlib.sha256(url.encode()).hexdigest()[:12]}"
    # تحليل نوع اللينك
    platform = "unknown"
    if "tiktok.com" in url:
        platform = "tiktok"
    elif "youtube.com" in url or "youtu.be" in url:
        platform = "youtube"
    elif "instagram.com" in url:
        platform = "instagram"
    elif "reddit.com" in url:
        platform = "reddit"
    elif "webnovel" in url:
        platform = "webnovel"
    
    # استخراج فكرة مبدئية (في النسخة الحقيقية هنستخدم AI summarizer)
    record = {
        "link_id": link_id,
        "url": url,
        "platform_source": platform,
        "note": note,
        "user_id": user_id,
        "ingested_at": datetime.utcnow().isoformat() + "Z",
        "status": "QUEUED_FOR_ANALYSIS",
        "analysis": {
            "title_extracted": f"Story from {platform} - {url[:50]}",
            "outline_extracted": f"User noted: {note}. Original URL: {url}. Needs AI summarization + 80% transformative rewrite.",
            "beats_suggested": 4,
            "rights_note": f"Source {platform} - Must transform 80% original per {platform} rules, no direct reupload"
        },
        "next_steps": [
            "AI summarizes story from URL (transcript + captions)",
            "Generates 80% original adaptation with new characters",
            "Creates Character Bible + beats (3-6 videos)",
            "Recommends best platform + auth link"
        ]
    }
    
    data = _load()
    # منع التكرار
    if not any(d["url"] == url for d in data):
        data.append(record)
        _save(data)
    
    return record

def list_ingested(user_id: str = None) -> List[Dict]:
    data = _load()
    if user_id:
        return [d for d in data if d["user_id"] == user_id]
    return data

def continue_from_link(link_id: str) -> Dict:
    """كمل على لينك معين - يحوله لقصة جاهزة للتوليد"""
    data = _load()
    found = next((d for d in data if d["link_id"] == link_id), None)
    if not found:
        return {"error": "Link not found"}
    
    # تحويل للـ format بتاع trending_stories
    story = {
        "id": f"ingested_{found['link_id']}",
        "title": found["analysis"]["title_extracted"],
        "genre": "Drama",
        "story_outline": found["analysis"]["outline_extracted"],
        "beats": found["analysis"]["beats_suggested"],
        "hook": found["note"] or f"مستوحى من {found['platform_source']}",
        "tags": ["ingested", found["platform_source"], "original-adaptation"],
        "profit_score": 7,
        "views_estimate": "Unknown - new idea",
        "source_link_id": link_id,
        "rights_compliant": True
    }
    
    # حدث الحالة
    found["status"] = "CONVERTED_TO_STORY"
    found["converted_story_id"] = story["id"]
    _save(data)
    
    return {"story": story, "source": found, "next": "Call /generate with this story_id"}

def delete_link(link_id: str) -> bool:
    data = _load()
    new_data = [d for d in data if d["link_id"] != link_id]
    if len(new_data) != len(data):
        _save(new_data)
        return True
    return False
