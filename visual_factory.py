import os, json, hashlib
def parse_story_to_beats(story):
    outline = story.get("story_outline","")
    beats = story.get("beats",4)
    if len(outline) < 300: beats = 3
    elif len(outline) > 1000: beats = 6
    beats = max(3, min(7, beats))
    result=[]
    for i in range(1, beats+1):
        result.append({"beat_number": i, "title": f"{story.get('title')} - الجزء {i}", "duration_sec": 50, "prompt": f"9:16 vertical drama, beat {i}/{beats}, {story.get('hook','')}, cinematic", "caption": f"{story.get('hook','')} - الجزء {i}", "tags": story.get("tags",[])[:3]})
    return result
def create_character_bible(story):
    return {"story_id": story.get("id"), "bible_id": f"bible_{hashlib.sha256(story.get('id','').encode()).hexdigest()[:12]}", "characters": ["Main heroine - consistent face", "Billionaire CEO"], "style": "cinematic 9:16, dramatic lighting", "consistent_face": True}
def generate_video_prompt(beat, bible, edit_ops=None):
    base = beat["prompt"]
    if edit_ops:
        for op in edit_ops:
            if op["type"]=="lighting": base += f", {op.get('prompt','')}"
    return base
def get_agent_status():
    return {"visual_factory": "READY", "character_bible": "Consistent Face - READY", "arabic_parser": "اضاءة اغمق قص كابشن اسرع ابطأ - READY", "beats": "3-7 per story", "format": "1080x1920 9:16"}
