
# bot.py - Short Drama Video Agent with Trend Scanner + Edit Understanding
import asyncio, json, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Load trending stories
with open("trending_stories.json", "r", encoding="utf-8") as f:
    TRENDING = json.load(f)

# Edit understanding - Arabic comments parser
EDIT_KEYWORDS = {
    "اضاءة": "lighting",
    "اغمق": "darker", "افتح": "brighter",
    "قص": "cut", "اقطع": "trim",
    "كابشن": "caption", "عنوان": "title",
    "موسيقى": "music", "صوت": "sound",
    "اسرع": "faster", "ابطأ": "slower",
    "اضافة": "add", "احذف": "delete",
    "طويل": "longer", "قصير": "shorter",
    "الوان": "colors", "فلتر": "filter",
    "خلفية": "background", "زوم": "zoom"
}

def parse_edit_comment(text: str):
    """يفهم تعليقاتك بالعربي وينفذها"""
    text_lower = text.lower()
    actions = []
    for ar, en in EDIT_KEYWORDS.items():
        if ar in text_lower:
            actions.append(en)
    
    # Detect specific edits
    result = {
        "raw": text,
        "actions": actions,
        "understood": len(actions) > 0,
        "operations": []
    }
    
    if "اغمق" in text_lower or "اضاءة" in text_lower:
        result["operations"].append({"type": "lighting", "value": "darker", "prompt": "dramatic low-key lighting, darker shadows, cinematic"})
    if "افتح" in text_lower:
        result["operations"].append({"type": "lighting", "value": "brighter", "prompt": "brighter, high-key lighting"})
    if "قص" in text_lower or "اقطع" in text_lower:
        # Extract seconds if mentioned
        import re
        secs = re.findall(r'(\d+)\s*ث', text_lower)
        result["operations"].append({"type": "trim", "seconds": secs[0] if secs else "3", "prompt": f"trim first {secs[0] if secs else 3} seconds"})
    if "كابشن" in text_lower or "عنوان" in text_lower:
        result["operations"].append({"type": "caption", "new_text": text, "prompt": "regenerate caption"})
    if "اسرع" in text_lower:
        result["operations"].append({"type": "speed", "value": "1.25x"})
    if "ابطأ" in text_lower:
        result["operations"].append({"type": "speed", "value": "0.85x"})
    
    return result

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔥 الأكثر ربحاً الآن", callback_data="show_trending")],
        [InlineKeyboardButton("📝 ابعت قصتك", callback_data="send_story")],
        [InlineKeyboardButton("📊 أرباحي", callback_data="my_earnings")]
    ]
    await update.message.reply_text(
        "🎬 **Short Drama Video Agent**\n\n"
        "أنا بعمل:\n"
        "1. سكان للقصص التريندج المربحة\n"
        "2. تقطيع القصة لـ 5-7 حلقات 9:16\n"
        "3. توليد فيديوهات بنفس الشخصيات\n"
        "4. بفهم تعليقاتك وبعدل\n"
        "5. نشر أوتوماتيك على TikTok/Reels/Shorts\n"
        "6. حساب Royalty / أرباح إعلانات\n\n"
        "اختار:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def show_trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = "🔥 **القصص الأكثر ربحاً الآن (2026):**\n\n"
    keyboard = []
    for i, story in enumerate(TRENDING[:5]):
        text += f"{i+1}. **{story['title']}**\n"
        text += f"   Genre: {story['genre']} | Score: {story['profit_score']}/10\n"
        text += f"   Views: {story['views_estimate']} | Hook: {story['hook']}\n"
        text += f"   💰 ليه مربح: {story['why_profitable'][:80]}...\n\n"
        keyboard.append([InlineKeyboardButton(f"✅ اختار {story['title'][:20]}", callback_data=f"select_{story['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_home")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    story_id = query.data.replace("select_", "")
    story = next((s for s in TRENDING if s["id"] == story_id), None)
    if not story:
        return
    
    context.user_data["selected_story"] = story
    
    keyboard = [
        [InlineKeyboardButton("🎬 ابدأ التقطيع والتوليد", callback_data=f"generate_{story_id}")],
        [InlineKeyboardButton("📝 عدل القصة قبل التوليد", callback_data="edit_story")],
        [InlineKeyboardButton("🔙 رجوع للتريندج", callback_data="show_trending")]
    ]
    
    await query.edit_message_text(
        f"✅ اخترت: **{story['title']}**\n\n"
        f"📖 القصة: {story['story_outline']}\n\n"
        f"🎬 هيتقطع لـ {story['beats']} حلقات\n"
        f"💰 متوسط الربح: {story['avg_episode_cost']}\n"
        f"🏷️ Tags: {', '.join(story['tags'])}\n\n"
        f"أبدأ التوليد ولا عايز تعدل حاجة؟",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    story_id = query.data.replace("generate_", "")
    story = next((s for s in TRENDING if s["id"] == story_id), None)
    
    await query.edit_message_text(f"⏳ بقطع **{story['title']}** لـ {story['beats']} حلقات 9:16...\nبستخدم Muse Video + نفس الشخصيات...")
    
    # Simulate generation
    await asyncio.sleep(2)
    
    for beat in range(1, story['beats']+1):
        keyboard = [
            [InlineKeyboardButton("✅ Approve & نشر", callback_data=f"approve_beat_{beat}"),
             InlineKeyboardButton("✏️ عدل", callback_data=f"edit_beat_{beat}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"reject_beat_{beat}")]
        ]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"🎬 **Beat {beat}/{story['beats']} - {story['title']}**\n"
                 f"📹 فيديو {40+beat*2} ثانية | 9:16 | Captions جاهزة\n"
                 f"📝 Caption: \"{story['hook']} - الجزء {beat}\"\n"
                 f"🏷️ #{' #'.join(story['tags'][:3])}\n\n"
                 f"لو عايز تعدل، ابعت تعليقك زي:\n"
                 f"\"خلي الإضاءة أغمق\" أو \"قص أول 3 ثواني\" أو \"غير الكابشن\"",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        await asyncio.sleep(0.5)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"✅ **كل الحلقات اتولدت!**\n\n"
             f"الخطوة الجاية: دوس Approve على كل حلقة → هنشر أوتوماتيك على:\n"
             f"• TikTok (Creativity Program $0.50-$1/1000 view)\n"
             f"• YouTube Shorts (45% revenue share)\n"
             f"• Instagram Reels (Reels Play Bonus)\n"
             f"• Facebook Reels\n\n"
             f"والأرباح هتتسجل في Monetization Backend v1"
    )

async def handle_edit_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    parsed = parse_edit_comment(text)
    
    if not parsed["understood"]:
        await update.message.reply_text(
            "🤔 مفهمتش التعليق، جرب تقول:\n"
            "• خلي الإضاءة أغمق / افتح الإضاءة\n"
            "• قص أول 3 ثواني\n"
            "• غير الكابشن لـ ...\n"
            "• اسرع الفيديو / ابطأ\n"
            "• غير الموسيقى / الألوان"
        )
        return
    
    ops_text = "\n".join([f"• {op['type']}: {op.get('value', op.get('prompt',''))}" for op in parsed["operations"]])
    await update.message.reply_text(
        f"✅ **فهمت تعليقك:**\n{ops_text}\n\n"
        f"⏳ بطبق التعديلات بـ Muse Image editing (بيحافظ على نفس الشخصيات)...\n"
        f"هبعتلك النسخة الجديدة خلال ثواني"
    )
    
    # Simulate edit via Muse Image editing
    await asyncio.sleep(2)
    await update.message.reply_text(
        f"🎬 **تم التعديل!**\n"
        f"العمليات: {ops_text}\n"
        f"📹 فيديو جديد جاهز - نفس الشخصيات، الإضاءة/القص اتعدل\n"
        f"[▶️ Preview الجديد]"
    )

# Setup
# app = Application.builder().token("YOUR_BOT_TOKEN").build()
# app.add_handler(CommandHandler("start", start))
# app.add_handler(CallbackQueryHandler(show_trending, pattern="show_trending"))
# app.add_handler(CallbackQueryHandler(handle_selection, pattern="select_"))
# app.add_handler(CallbackQueryHandler(handle_generate, pattern="generate_"))
# app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_comment))
# app.run_polling()
