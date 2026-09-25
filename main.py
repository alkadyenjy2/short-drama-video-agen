# main.py - Video Agent production entrypoint
# Telegram uses webhook transport to avoid getUpdates polling conflicts.
# No hardcoded secrets; BOT_TOKEN is required.

import os
import asyncio
import signal
import json
from dotenv import load_dotenv

load_dotenv()

from persistence.repository import get_repository
from health import start_health_server, webhook_path
import bot as bot_module
from telegram import Update


async def main():
    print("=== Video Agent Starting (Telegram Webhook) ===")

    db_path = os.getenv("DATABASE_PATH", "./data/video_agent.db")
    repo = get_repository(db_path=db_path)
    repo.init_schema()
    if not repo.health_check():
        raise RuntimeError("Persistence health check failed after init")
    print("Persistence health: ok")

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    application = None
    shutdown_started = False
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    print("Initializing Telegram bot...")
    application = bot_module.build_application()
    token = bot_module.get_bot_token()
    path = webhook_path(token)

    base_url = (
        os.getenv("TELEGRAM_WEBHOOK_BASE_URL", "").strip().rstrip("/")
        or os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
        or ("https://" + os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip().rstrip("/"))
    )
    if not base_url or base_url == "https://":
        raise RuntimeError("Public webhook base URL is unavailable")

    telegram_url = f"{base_url}{path}"
    print("Telegram transport: webhook")
    print(f"Telegram webhook path: {path}")

    def receive_telegram_update(payload):
        update = Update.de_json(payload, application.bot)
        future = asyncio.run_coroutine_threadsafe(
            application.process_update(update), loop
        )
        def _report_update_error(done):
            try:
                done.result()
            except Exception as exc:
                print(f"Telegram update processing error: {exc}")
        future.add_done_callback(_report_update_error)

    worker_token = os.getenv("YOUTUBE_WORKER_TOKEN", "").strip()

    def worker_complete_handler(job, final_path):
        text = (
            "✅ الفيديو اتجاب من Browser Worker واتحقق واتسجل كـ active video.\\n"
            f"Title: {(job.get('title') or 'YouTube video')[:120]}\\n"
            f"Bytes: {job.get('bytes')}\\nSHA256: {job.get('sha256')}\\n\\n"
            "دلوقتي ابعت التعديل المطلوب، مثل: خلي الإضاءة أغمق"
        )
        future = asyncio.run_coroutine_threadsafe(
            application.bot.send_message(chat_id=int(job["user_id"]), text=text),
            loop,
        )
        future.result(timeout=30)

    def worker_fail_handler(job, error):
        text = (
            "🛑 Browser Worker مقدرش يجيب الفيديو؛ لم يتم تسجيل active video ولم أدّعِ نجاحاً.\\n"
            f"Reason: {str(error)[:500]}"
        )
        future = asyncio.run_coroutine_threadsafe(
            application.bot.send_message(chat_id=int(job["user_id"]), text=text),
            loop,
        )
        future.result(timeout=30)

    health_server, _health_thread = start_health_server(
        lambda: repo,
        host=host,
        port=port,
        telegram_handler=receive_telegram_update,
        telegram_path=path,
        worker_token=worker_token,
        worker_complete_handler=worker_complete_handler,
        worker_fail_handler=worker_fail_handler,
    )
    print(f"Health endpoint: http://{host}:{port}/health")

    async def shutdown():
        nonlocal shutdown_started
        if shutdown_started:
            return
        shutdown_started = True
        print("Shutting down gracefully...")
        if application is not None:
            try:
                await application.stop()
            except Exception as exc:
                print(f"Telegram application stop warning: {exc}")
            try:
                await application.shutdown()
            except Exception as exc:
                print(f"Telegram application shutdown warning: {exc}")
        try:
            health_server.shutdown()
        except Exception as exc:
            print(f"Health server shutdown warning: {exc}")
        shutdown_event.set()

    def handle_shutdown(signum, _frame):
        print(f"Received signal {signum}")
        asyncio.get_running_loop().create_task(shutdown())

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        await application.initialize()
        await application.bot.set_webhook(
            url=telegram_url,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
        )
        await application.start()

        print("=== Video Agent Ready ===")
        print("Telegram: webhook ACTIVE")
        print("Health: /health")
        print("Persistence: SQLite local")
        print("Publisher: Evidence Gate enforced; provider credentials required")

        await shutdown_event.wait()
    finally:
        if not shutdown_started:
            await shutdown()


if __name__ == "__main__":
    asyncio.run(main())
