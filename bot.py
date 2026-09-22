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


def get_bot_token() -> str:
    """Return BOT_TOKEN or fail fast before the Telegram runtime starts."""
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is missing; Telegram runtime cannot start")
    return token


def build_application() -> Application:
    """Build the real Telegram application and register all runtime handlers."""
    application = Application.builder().token(get_bot_token()).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(show_trending, pattern=r"^show_trending$"))
    application.add_handler(CallbackQueryHandler(handle_selection, pattern=r"^select_"))
    application.add_handler(CallbackQueryHandler(handle_generate, pattern=r"^generate_"))
    application.add_handler(CallbackQueryHandler(start_from_callback, pattern=r"^back_home$"))
    application.add_handler(CallbackQueryHandler(show_not_implemented, pattern=r"^(send_story|my_earnings|edit_story)$"))
    application.add_handler(CallbackQueryHandler(show_not_implemented, pattern=r"^(approve_beat_|edit_beat_|reject_beat_)"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_comment))

    return application


def parse_edit_comment(text: str):
    """يفهم تعليقاتك بالعربي وينفذها"""
    text_lower = text.lower()
    actions = []
    for ar, en in EDIT_KEYWORDS.items():
        if ar in text_lower:
            actions.append(en)

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


async def start_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)


async def show_not_implemented(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "ℹ️ الوظيفة دي لسه مش موصولة بتنفيذ حقيقي. لم يتم تسجيل أي نشر أو أرباح أو نجاح وهمي."
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
    if not story:
        await query.message.reply_text("❌ القصة غير موجودة.")
        return

    from visual_factory import create_character_bible, generate_video, parse_story_to_beats

    beats = parse_story_to_beats(story)
    bible = create_character_bible(story)
    await query.edit_message_text(
        f"⏳ ببدأ التوليد الحقيقي لـ **{story['title']}** — {len(beats)} حلقات...\n"
        "Evidence Gate مفعّل: لن يتم اعتبار أي فيديو Generated بدون artifact حقيقي."
    )

    generated = blocked = failed = 0
    for beat in beats:
        result = await asyncio.to_thread(generate_video, beat, bible)
        if not result.success:
            if result.state == "BLOCKED_CREDENTIALS":
                blocked += 1
            else:
                failed += 1
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(f"🛑 Beat {beat['beat_number']}/{len(beats)}: {result.state}\n"
                      f"Code: {result.error_code or 'UNKNOWN'}\n"
                      "لم يتم إنشاء نجاح أو فيديو وهمي."),
            )
            continue

        generated += 1
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(f"🎬 Beat {beat['beat_number']}/{len(beats)} GENERATED\n"
                  f"Provider: {result.provider}\nModel: {result.model}\n"
                  f"Artifact bytes: {result.artifact_bytes}\nSHA256: {result.artifact_sha256}\n"
                  "⏳ لم يتم النشر؛ الـApproval Gate وPublisher منفصلان."),
        )
        try:
            with open(result.artifact_path, "rb") as video_file:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=video_file,
                    caption=f"Preview — Beat {beat['beat_number']}/{len(beats)}",
                    supports_streaming=True,
                )
        except Exception as exc:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"⚠️ Artifact generated and verified, لكن إرسال الـpreview إلى Telegram فشل: {exc}",
            )

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(f"📊 Generation result: {generated} generated / {blocked} blocked / {failed} failed.\n"
              "لا يوجد PUBLISHED أو نجاح نشر من خطوة التوليد."),
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

    ops_text = "\n".join([f"• {op['type']}: {op.get('value', op.get('prompt', ''))}" for op in parsed["operations"]])
    await update.message.reply_text(
        f"🧩 **فهمت تعليقك:**\n{ops_text}\n\n"
        "⚠️ محرّك التعديل الحقيقي غير موصول بعد. لم يتم الادعاء بتنفيذ التعديل."
    )
