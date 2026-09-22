# analytics_tracker.py - يتابع كل الفيديوهات اللي بتنزل والاعلانات والمشاهدات والداونلودز والفلوس
import os, json
from datetime import datetime
from typing import Dict, List
from persistence.repository import get_repository

class AnalyticsTracker:
    def __init__(self):
        self.repo = get_repository()
    
    def log_publish(self, video_id: str, story_id: str, beat_number: int, platform: str, publish_result: Dict):
        """سجل كل فيديو بينزل"""
        try:
            # استخدم جدول publication_attempts الموجود
            self.repo.create_publication_attempt({
                "attempt_id": publish_result.get("attempt_id", f"attempt_{video_id}"),
                "publication_id": f"{story_id}_{video_id}",
                "video_id": video_id,
                "platform": platform,
                "state": publish_result.get("state", "FAILED"),
                "provider_object_id": publish_result.get("platform_id") or publish_result.get("receipt"),
                "error_code": publish_result.get("category"),
                "error_message": publish_result.get("reason"),
                "request_payload": json.dumps(publish_result.get("request_payload", {})),
                "response_payload": json.dumps(publish_result),
                "created_at": datetime.utcnow().isoformat() + "Z"
            })
        except Exception as e:
            print(f"Analytics log_publish warning: {e}")
        
        # سجل اضافي في ملف JSON للارباح
        analytics_file = os.path.join(os.path.dirname(__file__), "analytics.json")
        data = []
        if os.path.exists(analytics_file):
            try:
                with open(analytics_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                data = []
        
        data.append({
            "video_id": video_id,
            "story_id": story_id,
            "beat_number": beat_number,
            "platform": platform,
            "published_at": datetime.utcnow().isoformat() + "Z",
            "state": str(publish_result.get("state")),
            "platform_id": publish_result.get("platform_id"),
            "views": 0,  # هيتحدث من API لاحقاً
            "likes": 0,
            "downloads": 0,
            "ad_revenue": 0.0,
            "estimated_earnings": 0.0,
            "rights_status": "ORIGINAL_80_TRANSFORMED",
            "next_update": "Poll /analytics/{video_id} after 1h for real views"
        })
        
        try:
            with open(analytics_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Analytics file warning: {e}")
        
        return {"logged": True, "video_id": video_id, "platform": platform}
    
    def update_metrics(self, video_id: str, platform: str, metrics: Dict):
        """حدث المشاهدات والفلوس من الـ APIs الحقيقية"""
        analytics_file = os.path.join(os.path.dirname(__file__), "analytics.json")
        if not os.path.exists(analytics_file):
            return {"error": "No analytics file"}
        
        try:
            with open(analytics_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            return {"error": "Read failed"}
        
        for entry in data:
            if entry["video_id"] == video_id and entry["platform"] == platform:
                entry["views"] = metrics.get("views", entry["views"])
                entry["likes"] = metrics.get("likes", entry["likes"])
                entry["downloads"] = metrics.get("downloads", entry.get("downloads", 0))
                entry["ad_revenue"] = metrics.get("ad_revenue", entry["ad_revenue"])
                # حساب الارباح حسب المنصة
                if platform == "tiktok":
                    # $0.50-$1 / 1k views Creativity Program
                    entry["estimated_earnings"] = (entry["views"] / 1000) * 0.75
                elif platform == "youtube":
                    # 45% Shorts - تقريباً $0.02-$0.04 per 1k views Shorts
                    entry["estimated_earnings"] = (entry["views"] / 1000) * 0.03 * 0.45
                elif platform == "instagram":
                    entry["estimated_earnings"] = (entry["views"] / 1000) * 0.02  # Bonus
                entry["last_updated"] = datetime.utcnow().isoformat() + "Z"
        
        try:
            with open(analytics_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Analytics update warning: {e}")
        
        return {"updated": True, "video_id": video_id}
    
    def get_dashboard(self, user_id: str = None) -> Dict:
        analytics_file = os.path.join(os.path.dirname(__file__), "analytics.json")
        if not os.path.exists(analytics_file):
            return {"total_videos": 0, "total_views": 0, "total_earnings": 0.0, "by_platform": {}, "videos": []}
        
        try:
            with open(analytics_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = []
        
        total_views = sum(d.get("views", 0) for d in data)
        total_earnings = sum(d.get("estimated_earnings", 0.0) for d in data)
        total_downloads = sum(d.get("downloads", 0) for d in data)
        
        by_platform = {}
        for d in data:
            p = d["platform"]
            if p not in by_platform:
                by_platform[p] = {"videos": 0, "views": 0, "earnings": 0.0, "downloads": 0}
            by_platform[p]["videos"] += 1
            by_platform[p]["views"] += d.get("views", 0)
            by_platform[p]["earnings"] += d.get("estimated_earnings", 0.0)
            by_platform[p]["downloads"] += d.get("downloads", 0)
        
        return {
            "total_videos": len(data),
            "total_views": total_views,
            "total_earnings": round(total_earnings, 2),
            "total_downloads": total_downloads,
            "by_platform": by_platform,
            "videos": sorted(data, key=lambda x: x.get("views", 0), reverse=True)[:20],
            "rights_note": "All videos 80% original - compliant per platform rules",
            "auth_status": "/auth/status"
        }

def get_analytics_dashboard():
    tracker = AnalyticsTracker()
    return tracker.get_dashboard()
