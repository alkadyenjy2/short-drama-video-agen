# bot.py - Short Drama Video Agent with Trend Scanner + Edit Understanding
import asyncio, hashlib, json, os, re, unicodedata
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
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("research", research_command))
    application.add_handler(CommandHandler("trending", trending_command))
    application.add_handler(CommandHandler("earnings", earnings_command))
    application.add_handler(CommandHandler("save", save_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("execute", execute_command))
    application.add_handler(CallbackQueryHandler(show_trending, pattern=r"^show_trending$"))
    application.add_handler(CallbackQueryHandler(handle_selection, pattern=r"^select_"))
    application.add_handler(CallbackQueryHandler(handle_generate, pattern=r"^generate_"))
    application.add_handler(CallbackQueryHandler(start_from_callback, pattern=r"^back_home$"))
    application.add_handler(CallbackQueryHandler(handle_send_story, pattern=r"^send_story$"))
    application.add_handler(CallbackQueryHandler(earnings_callback, pattern=r"^my_earnings$"))
    application.add_handler(CallbackQueryHandler(handle_edit_story, pattern=r"^edit_story$"))
    application.add_handler(CallbackQueryHandler(show_not_implemented, pattern=r"^(approve_beat_|edit_beat_|reject_beat_)"))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video_upload))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_comment))

    return application


def normalize_arabic(text: str) -> str:
    """Normalize common Arabic spelling/diacritics so natural comments match reliably."""
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    text = text.replace("ـ", "")
    text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ؤ": "و", "ئ": "ي"}))
    return re.sub(r"\s+", " ", text).strip().lower()


def _extract_seconds(text: str):
    match = re.search(r"(\d+)\s*(?:ثانيه|ثواني|ثانية|ثوان|ث|sec|secs|second|seconds)", text)
    return int(match.group(1)) if match else None


def _extract_caption(text: str):
    match = re.search(r"(?:الكابشن|كابشن|العنوان|عنوان)\s*(?:(?:لـ|ل|إلى|الى)\s*)?(?::|=)?\s*(.+)$", text)
    return match.group(1).strip() if match else None


def parse_edit_comment(text: str):
    """Convert a natural Arabic edit comment into a structured EDIT_REQUEST.

    Parsing only. This function never edits or regenerates a video.
    """
    normalized = normalize_arabic(text)
    actions = []
    operations = []

    def add_action(name):
        if name not in actions:
            actions.append(name)

    if any(k in normalized for k in ("اضاءة", "اضاء")):
        add_action("lighting")
        if any(k in normalized for k in ("اغمق", "غمق", "داكن", "مظلم")):
            operations.append({"type": "lighting", "value": "darker", "prompt": "dramatic low-key lighting, darker shadows, cinematic"})
        elif any(k in normalized for k in ("افتح", "فاتح", "اشرق", "ساطع")):
            operations.append({"type": "lighting", "value": "brighter", "prompt": "brighter, high-key lighting"})
        else:
            operations.append({"type": "lighting", "value": "adjust", "prompt": "adjust lighting as requested"})

    seconds = _extract_seconds(normalized)
    if any(k in normalized for k in ("قص", "اقطع", "شيل")):
        add_action("trim")
        operations.append({
            "type": "trim",
            "seconds": seconds if seconds is not None else 3,
            "position": "start",
            "prompt": f"trim first {seconds if seconds is not None else 3} seconds",
        })

    caption = _extract_caption(normalized)
    if caption:
        add_action("caption")
        operations.append({"type": "caption", "new_text": caption, "prompt": "replace caption"})
    elif "كابشن" in normalized or "عنوان" in normalized:
        add_action("caption")
        operations.append({"type": "caption", "new_text": None, "prompt": "regenerate caption"})

    if any(k in normalized for k in ("اسرع", "سرع", "تسريع")):
        add_action("speed")
        operations.append({"type": "speed", "value": "1.25x"})
    elif any(k in normalized for k in ("ابطا", "بطء", "بطيء", "تبطيء")):
        add_action("speed")
        operations.append({"type": "speed", "value": "0.85x"})

    if "موسيقى" in normalized or "موسيقا" in normalized:
        add_action("music")
        operations.append({"type": "music", "value": "change", "prompt": "replace music track"})

    if any(k in normalized for k in ("الوان", "لون", "فلتر")):
        add_action("visual")
        operations.append({"type": "visual", "value": "colors_or_filter", "prompt": "adjust colors/filter as requested"})

    if any(k in normalized for k in ("خلفيه", "خلفية")):
        add_action("background")
        operations.append({"type": "background", "value": "change", "prompt": "change background"})

    if any(k in normalized for k in ("زوم", "تقريب", "كبر اللقطه", "قرب اللقطه")):
        add_action("zoom")
        operations.append({"type": "zoom", "value": "adjust", "prompt": "adjust camera zoom"})

    return {
        "type": "EDIT_REQUEST",
        "raw": text,
        "normalized": normalized,
        "actions": actions,
        "understood": bool(operations),
        "operations": operations,
        "execution_state": "BLOCKED_NO_EDIT_ENGINE" if operations else "UNUNDERSTOOD",
    }


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧭 **الأوامر المتاحة**\\n\\n"
        "/start — الصفحة الرئيسية\\n"
        "/trending — القصص التريند\\n"
        "/research <كلمة> — بحث داخل قاعدة القصص الحالية\\n"
        "/save <فكرة> — حفظ فكرة محلياً\\n"
        "/analyze — تحليل القصة المختارة\\n"
        "/earnings — لوحة الأرباح المسجلة فعلياً\\n"
        "/status — حالة مكونات النظام\\n"
        "/execute — حالة التنفيذ الحقيقي\\n"
        "/help — المساعدة",
        parse_mode="Markdown"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from auth_manager import get_all_auth_status
    auth = get_all_auth_status()
    try:
        from visual_factory import _provider_status
        generation = _provider_status()
    except Exception as exc:
        generation = {"state": "FAILED", "error": str(exc)}
    connected = ", ".join("{}: {}".format(p, "CONNECTED" if v["connected"] else "NOT_CONNECTED") for p, v in auth.items())
    await update.message.reply_text(
        "🟢 **System status**\\n\\n"
        "Telegram runtime: ACTIVE\\n"
        f"Video generation: {generation.get('state')}\\n"
        f"Publisher auth: {connected}\\n"
        "Evidence Gate: ENFORCED\\n"
        "Fake PUBLISHED: BLOCKED",
        parse_mode="Markdown"
    )

async def research_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args).strip().lower()
    if not query:
        await update.message.reply_text("🔎 استخدم: /research <كلمة أو نوع قصة>")
        return
    matches = []
    for story in TRENDING:
        haystack = " ".join([str(story.get("title", "")), str(story.get("genre", "")), str(story.get("hook", "")), " ".join(map(str, story.get("tags", []))) ]).lower()
        if query in haystack:
            matches.append(story)
    if not matches:
        await update.message.reply_text(f"🔎 لم أجد تطابقاً في قاعدة القصص المحلية الحالية لـ: {query}\\nهذا الأمر لا يدّعي بحثاً على الويب؛ محرك web research الخارجي غير موصول في هذا runtime.")
        return
    lines = [f"🔎 نتائج البحث: {query}"]
    for i, story in enumerate(matches[:5], 1):
        lines.append(f"{i}. {story.get('title')}\\nGenre: {story.get('genre')} | Score: {story.get('profit_score')}/10\\nViews: {story.get('views_estimate')}\\nHook: {story.get('hook')}")
    await update.message.reply_text("\\n\\n".join(lines))

async def trending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 استخدم زر **الأكثر ربحاً الآن** من /start لفتح قائمة القصص واختيار قصة.", parse_mode="Markdown")

async def earnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from analytics_tracker import get_analytics_dashboard
    dashboard = get_analytics_dashboard()
    await update.message.reply_text(
        "📊 **الأرباح المسجلة فعلياً**\\n\\nVideos: {}\\nViews: {}\\nDownloads: {}\\nEstimated earnings: ${:.2f}\\n\\n⚠️ الأرقام من سجل النظام فقط، وليست إثباتاً لمدفوعات من المنصات.".format(dashboard["total_videos"], dashboard["total_views"], dashboard["total_downloads"], dashboard["total_earnings"]),
        parse_mode="Markdown"
    )

async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idea = " ".join(context.args).strip()
    if not idea:
        await update.message.reply_text("💾 استخدم: /save <الفكرة>")
        return
    data_dir = os.getenv("DATA_DIR", "./data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "saved_ideas.json")
    data = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: data = json.load(f)
        except Exception: data = []
    from datetime import datetime
    data.append({"idea": idea, "saved_at": datetime.utcnow().isoformat() + "Z"})
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    await update.message.reply_text("✅ الفكرة اتحفظت محلياً. لم يتم الادعاء بحفظها في خدمة خارجية.")

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    story = context.user_data.get("selected_story")
    if not story:
        await update.message.reply_text("🧠 اختار قصة أولاً من 🔥 الأكثر ربحاً الآن.")
        return
    await update.message.reply_text("🧠 **تحليل القصة**\\n\\nTitle: {}\\nGenre: {}\\nBeats: {}\\nProfit score: {}/10\\nViews estimate: {}\\nRights: {}\\n\\nالتحليل مبني على البيانات الموجودة في trending_stories.json.".format(story.get("title"), story.get("genre"), story.get("beats"), story.get("profit_score"), story.get("views_estimate"), story.get("rights_compliant")), parse_mode="Markdown")

async def execute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ **Execution status**\\n\\nGeneration: موصول بمحرك Hugging Face ويتطلب HF_TOKEN صالحاً.\\nPublishing: موصول بالكود مع Evidence Gate، لكن حسابات المنصات غير متصلة.\\nEditing: parser + deterministic FFmpeg editor موصولان؛ Evidence Gate يمنع النجاح الوهمي.\\nلا يوجد تنفيذ وهمي أو PUBLISHED وهمي.", parse_mode="Markdown")

async def handle_send_story(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data["awaiting_story"] = True
    await query.message.reply_text("📝 ابعت ملخص القصة أو النص هنا في رسالة واحدة.\\nهسجله كـ story input؛ لن أدّعي تحليل رابط/فيديو لم أستطع الوصول إليه.")

async def earnings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    from analytics_tracker import get_analytics_dashboard
    dashboard = get_analytics_dashboard()
    await query.message.reply_text("📊 Videos: {} | Views: {} | Downloads: {} | Estimated: ${:.2f}\\nالأرقام من سجل النظام فقط، وليست إثبات دفع من منصة.".format(dashboard["total_videos"], dashboard["total_views"], dashboard["total_downloads"], dashboard["total_earnings"]))

async def handle_edit_story(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data["awaiting_story_edit"] = True
    await query.message.reply_text("📝 ابعت التعديل المطلوب على القصة. هسجله كطلب تعديل بدون ادعاء تنفيذ قبل وجود محرك تعديل حقيقي.")

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

async def handle_video_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.video:
        return
    video = await message.video.get_file()
    upload_dir = os.getenv("VIDEO_UPLOAD_DIR", "./data/uploads")
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, f"{message.video.file_unique_id}.mp4")
    await video.download_to_drive(path)
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    size = os.path.getsize(path)
    user_id = str(update.effective_user.id if update.effective_user else message.chat_id)
    video_id = str(message.video.file_unique_id)
    from persistence.repository import get_repository
    repo = get_repository()
    repo.init_schema()
    repo.set_active_video(user_id, video_id, path, digest, size)
    context.user_data["active_video"] = path
    context.user_data["active_video_id"] = video_id
    context.user_data["active_video_sha256"] = digest
    context.user_data["active_video_bytes"] = size
    await message.reply_text(
        f"🎬 الفيديو اتسجل كـ active video.\\nBytes: {size}\\nSHA256: {digest}\\n\\n"
        "ابعت التعديل المطلوب، مثل: خلي الإضاءة أغمق"
    )

async def handle_edit_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if context.user_data.pop("awaiting_story", False):
        context.user_data["story_input"] = text
        await update.message.reply_text("✅ استلمت القصة. تم حفظ الإدخال داخل جلسة Telegram؛ لا يوجد ادعاء بتحليل أو توليد قبل تشغيل المحرك المناسب.")
        return
    if context.user_data.pop("awaiting_story_edit", False):
        context.user_data["story_edit_request"] = text
        await update.message.reply_text("📝 تم تسجيل تعديل القصة. لم يتم ادعاء إعادة توليد بدون محرك التوليد.")
        return

    parsed = parse_edit_comment(text)
    if not parsed["understood"]:
        await update.message.reply_text(
            "🤔 مفهمتش التعليق، جرب: خلي الإضاءة أغمق / قص أول 3 ثواني / غير الكابشن / اسرع الفيديو"
        )
        return

    from persistence.repository import get_repository
    repo = get_repository()
    repo.init_schema()
    user_id = str(update.effective_user.id if update.effective_user else update.message.chat_id)

    active_video = context.user_data.get("active_video")
    active_sha = context.user_data.get("active_video_sha256")
    active_video_id = context.user_data.get("active_video_id")

    if not active_video or not os.path.isfile(active_video):
        persisted = repo.get_active_video(user_id)
        if persisted and os.path.isfile(persisted["path"]):
            active_video = persisted["path"]
            active_sha = persisted["sha256"]
            active_video_id = persisted["video_id"]
            context.user_data["active_video"] = active_video
            context.user_data["active_video_sha256"] = active_sha
            context.user_data["active_video_id"] = active_video_id
            context.user_data["active_video_bytes"] = persisted["bytes"]

    if not active_video or not os.path.isfile(active_video):
        await update.message.reply_text(
            "🛑 EDIT_REQUEST مفهوم، لكن لا يوجد active video للتنفيذ. ابعت الفيديو أولاً."
        )
        return

    from video_editor import edit_video
    from datetime import datetime, timezone
    from uuid import uuid4

    last_result = None
    for operation in parsed["operations"]:
        output_dir = os.getenv("VIDEO_OUTPUT_DIR", "./data/edited")
        os.makedirs(output_dir, exist_ok=True)
        output = os.path.join(output_dir, f"{uuid4().hex}.mp4")
        result = await asyncio.to_thread(edit_video, active_video, operation, output)
        last_result = result
        if not result.success:
            await update.message.reply_text(
                f"🛑 التعديل فشل.\\nState: {result.state}\\nCode: {result.error_code or 'UNKNOWN'}\\n"
                "لم يتم تسجيل نجاح وهمي."
            )
            return

        parent_version = active_sha or context.user_data.get("active_video_sha256")
        new_version = result.artifact_sha256
        try:
            video_id = active_video_id or context.user_data.get("active_video_id", update.effective_user.id if update.effective_user else "telegram")
            repo.create_or_update_video_version(str(video_id), new_version)
            repo.create_operation_log({
                "operation_id": uuid4().hex,
                "user_id": str(update.effective_user.id if update.effective_user else "telegram"),
                "video_id": str(video_id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "parent_version": parent_version,
                "new_version": new_version,
                "operation_type": operation.get("type", "edit"),
                "parsed_value": json.dumps(operation, ensure_ascii=False),
                "generated_prompt": operation.get("prompt"),
                "preview_reference": result.output_path,
                "status": "EDITED",
            })
        except Exception as exc:
            await update.message.reply_text(f"🛑 Artifact موجود لكن persistence verification failed: {exc}")
            return

        repo.set_active_video(
            user_id,
            str(video_id),
            result.output_path,
            result.artifact_sha256,
            result.artifact_bytes,
        )
        active_video = result.output_path
        active_sha = result.artifact_sha256
        active_video_id = str(video_id)
        context.user_data["active_video"] = result.output_path
        context.user_data["active_video_sha256"] = result.artifact_sha256
        context.user_data["active_video_bytes"] = result.artifact_bytes
        context.user_data["active_video_id"] = str(video_id)

    await update.message.reply_video(
        video=open(last_result.output_path, "rb"),
        caption=(
            f"✅ EDITED\\nOperation: {last_result.operation}\\n"
            f"Bytes: {last_result.artifact_bytes}\\nSHA256: {last_result.artifact_sha256}"
        ),
    )
