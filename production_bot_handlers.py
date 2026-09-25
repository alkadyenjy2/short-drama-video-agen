"""Production Telegram handlers for real Short Drama generation.

This module is deliberately thin: the existing bot remains the canonical
workflow, while generation is delegated to the evidence-first HF adapter.
"""
import asyncio
import os

from hf_gradio_video_generation import generate_story_video


async def _send_verified_video(message, user_id, story_text, parsed_value="story_input"):
    import bot

    artifact = await asyncio.to_thread(generate_story_video, story_text)
    video_id = f"vid_{artifact.sha256[:12]}"
    log = bot.create_operation_log(
        user_id=str(user_id),
        video_id=video_id,
        operation_type="generation",
        parsed_value=parsed_value,
        generated_prompt=story_text,
    )
    try:
        with open(artifact.local_path, "rb") as fh:
            await message.reply_video(
                video=fh,
                caption=(                    "🎬 Generation VERIFIED\n"
                    f"Provider: {artifact.provider}\n"
                    f"Bytes: {artifact.size_bytes}\n"
                    f"SHA256: {artifact.sha256}\n"
                    f"Operation: {log['operation_id']}"
                ),
                supports_streaming=True,
            )
    finally:
        try:
            os.remove(artifact.local_path)
        except OSError:
            pass
    return artifact


async def handle_generate_real(update, context):
    query = update.callback_query
    await query.answer()
    import bot

    story_id = query.data.replace("generate_", "")
    story = next((s for s in bot.TRENDING if s["id"] == story_id), None)
    if not story:
        await query.edit_message_text("Story evidence is unavailable; generation is blocked.")
        return

    await query.edit_message_text(
        f"⏳ Generating a real 9:16 preview for: {story['title']}\n"
        "Evidence Gate: waiting for real MP4 + SHA-256."
    )
    try:
        artifact = await _send_verified_video(
            query.message,
            query.from_user.id,
            story["story_outline"],
            parsed_value=story_id,
        )
    except Exception as exc:
        await query.message.reply_text(
            f"🛑 Generation blocked; no success claimed.\n"
            f"Reason: {type(exc).__name__}: {str(exc)[:500]}"
        )
        return
    await query.message.reply_text(
        "Evidence Gate: PASS — real MP4 bytes were generated, hashed, and Telegram delivery returned successfully.\n"
        "Publishing remains blocked until platform OAuth + receipt evidence exists."
    )


async def handle_text_real(update, context):
    text = (update.message.text or "").strip()
    parsed = None
    try:
        import bot
        parsed = bot.parse_edit_comment(text)
    except Exception:
        parsed = {"understood": False}

    if not parsed.get("understood") and (
        len(text) >= 40
        or text.lower().startswith(("story:", "plot:", "قصة:", "حكاية:"))
    ):
        await update.message.reply_text(
            "⏳ Story accepted. Generating a real 9:16 preview; "
            "I will not claim success without bytes + SHA-256."
        )
        try:
            artifact = await _send_verified_video(
                update.message,
                update.effective_user.id,
                text,
            )
        except Exception as exc:
            await update.message.reply_text(
                f"🛑 Generation blocked; no success claimed.\n"
                f"Reason: {type(exc).__name__}: {str(exc)[:500]}"
            )
            return

        context.user_data["last_video_id"] = f"vid_{artifact.sha256[:12]}"
        await update.message.reply_text(
            "Evidence Gate: PASS — real MP4 bytes were generated, hashed, and delivered to Telegram.\n"
            "Publishing remains blocked until platform OAuth + receipt evidence exists."
        )
        return

    import bot
    await bot.handle_edit_comment(update, context)
