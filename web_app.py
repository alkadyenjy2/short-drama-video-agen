# web_app.py - Application Layer - Full Agent: Scan + Rights + Auth + Analytics + Link Ingestor
import os, json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional

from persistence.repository import get_repository
from visual_factory import get_agent_status
from publisher import get_adapter_status
from trend_scanner import scan_trending_stories, get_top_profitable, estimate_videos_and_platforms
from link_ingestor import ingest_link, list_ingested, continue_from_link
from analytics_tracker import get_analytics_dashboard, AnalyticsTracker
from auth_manager import get_auth_request, get_all_auth_status, generate_auth_links_for_story

app = FastAPI(title="DRAMA AI - Full Agent", version="1.3")

class LinkRequest(BaseModel):
    url: str
    note: str = ""
    user_id: str = "default"

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
<!DOCTYPE html>
<html dir="rtl" lang="ar"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>DRAMA AI Full</title>
<style>body{background:#0A0A0F;color:#F5F5F7;font-family:Tajawal,sans-serif;margin:0;padding:20px}.header{background:linear-gradient(135deg,#0A0A0F 0%,#1a1a2e 100%);padding:30px;border-radius:20px;border:1px solid #D4AF37}.logo{font-size:32px;font-weight:900;color:#D4AF37}.card{background:#1a1a2e;padding:20px;border-radius:15px;margin:15px 0;border:1px solid #333}.gold{color:#D4AF37}button{background:#D4AF37;color:#000;border:none;padding:12px 24px;border-radius:10px;font-weight:bold;cursor:pointer;margin:5px}button:hover{background:#E50914;color:#fff}input{padding:10px;border-radius:8px;border:1px solid #333;width:70%}</style>
</head><body>
<div class="header"><div class="logo">🎬 DRAMA AI - Full Agent</div><p>سكان + فلترة + حقوق + تتبع أرباح + لينكات</p>
<p><a href="/docs"><button>📚 API Docs</button></a> <a href="/scan"><button>🔥 سكان تريندج</button></a> <a href="/analytics"><button>📊 الأرباح</button></a> <a href="/auth/status"><button>🔑 حالة الربط</button></a></p></div>

<div class="card"><h3 class="gold">🔗 حط لينك قصة تعجبك وهو يكمل عليها</h3>
<input id="url" placeholder="https://tiktok.com/... أو يوتيوب أو ريديت"><input id="note" placeholder="ملاحظة: عايزها رومانسية أكتر"><button onclick="ingest()">حلل اللينك</button><div id="ingestResult"></div></div>

<div class="card"><h3 class="gold">🔥 سكان القصص المربحة (فلترة تلقائية)</h3><div id="scan">جاري التحميل...</div></div>

<div class="card"><h3 class="gold">📊 تتبع الفيديوهات والمشاهدات والفلوس</h3><div id="analytics">جاري التحميل...</div></div>

<div class="card"><h3 class="gold">🔑 طلبات التوصيل / المصادقة</h3><div id="auth">جاري التحميل...</div></div>

<script>
function ingest(){fetch('/ingest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:document.getElementById('url').value,note:document.getElementById('note').value})}).then(r=>r.json()).then(d=>{document.getElementById('ingestResult').innerHTML=`<p>✅ تم: ${d.link_id} - ${d.platform_source} - <a href='/ingest/${d.link_id}/continue'><button>كمل عليها</button></a></p>`})}
fetch('/scan').then(r=>r.json()).then(data=>{document.getElementById('scan').innerHTML=data.stories.slice(0,5).map(s=>`<p>🎬 ${s.title} - ${s.views_parsed} مشاهدة - ${s.beats_recommended} فيديو - أفضل منصة: ${s.best_platform} - <a href='/story/${s.id}/plan'><button>خطة النشر</button></a></p>`).join('')})
fetch('/analytics').then(r=>r.json()).then(d=>{document.getElementById('analytics').innerHTML=`<p>📹 ${d.total_videos} فيديو - 👁️ ${d.total_views} مشاهدة - 💰 $${d.total_earnings} - 📥 ${d.total_downloads} تحميل</p>`+Object.entries(d.by_platform).map(([k,v])=>`<p>${k}: ${v.videos} فيديو - ${v.views} مشاهدة - $${v.earnings.toFixed(2)}</p>`).join('')})
fetch('/auth/status').then(r=>r.json()).then(d=>{document.getElementById('auth').innerHTML=Object.entries(d).map(([k,v])=>`<p>${k}: ${v.connected?'✅ متصل':'❌ محتاج ربط'} - <a href='/auth/${k}'><button>اربط ${k}</button></a></p>`).join('')})
</script>
</body></html>
"""

@app.get("/health")
def health():
    repo = get_repository()
    return {"status": "ok", "db": repo.health_check(), "agent": get_agent_status(), "publisher": get_adapter_status(), "auth": get_all_auth_status()}

@app.get("/scan")
def scan():
    stories = scan_trending_stories()
    return {"count": len(stories), "profitable_count": len([s for s in stories if s["is_profitable"]]), "stories": stories}

@app.get("/scan/top")
def scan_top(limit: int = 10):
    top = get_top_profitable(limit)
    return {"count": len(top), "stories": top}

@app.get("/story/{story_id}/plan")
def story_plan(story_id: str):
    stories = scan_trending_stories()
    story = next((s for s in stories if s["id"] == story_id), None)
    if not story:
        # check ingested
        from link_ingestor import _load
        ing = _load()
        story = next((s for s in ing if s["link_id"] == story_id), None)
        if not story:
            raise HTTPException(404, "Story not found")
    plan = estimate_videos_and_platforms(story)
    auth_links = generate_auth_links_for_story(plan)
    return {"story": story, "plan": plan, "auth": auth_links, "rights": plan.get("rights_compliant")}

@app.post("/ingest")
def ingest(req: LinkRequest):
    result = ingest_link(req.url, req.note, req.user_id)
    return result

@app.get("/ingest")
def list_ingest(user_id: str = None):
    return {"links": list_ingested(user_id)}

@app.get("/ingest/{link_id}/continue")
def continue_link(link_id: str):
    result = continue_from_link(link_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    plan = estimate_videos_and_platforms(result["story"])
    auth_links = generate_auth_links_for_story(plan)
    return {**result, "plan": plan, "auth": auth_links}

@app.get("/auth/{platform}")
def auth_platform(platform: str, story_id: str = None):
    return get_auth_request(platform, story_id)

@app.get("/auth/status")
def auth_status():
    return get_all_auth_status()

@app.get("/analytics")
def analytics():
    return get_analytics_dashboard()

@app.post("/analytics/update/{video_id}")
def analytics_update(video_id: str, platform: str = Query(...), views: int = Query(0), likes: int = Query(0), downloads: int = Query(0), ad_revenue: float = Query(0.0)):
    tracker = AnalyticsTracker()
    return tracker.update_metrics(video_id, platform, {"views": views, "likes": likes, "downloads": downloads, "ad_revenue": ad_revenue})

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
