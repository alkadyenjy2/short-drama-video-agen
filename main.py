# main.py - Video Agent v1.2 Production entrypoint
# Combines: persistence init + health server + real Telegram polling
# No hardcoded secrets, fail-fast on BOT_TOKEN missing

import os
import asyncio
import signal
from dotenv import load_dotenv

load_dotenv()

from persistence.repository import get_repository
from health import start_health_server
import bot as bot_module


async def main():
    print("=== Video Agent v1.2 Starting ===")

    db_path = os.getenv("DATABASE_PATH", "./data/video_agent.db")
    print(f"Initializing persistence: {db_path}")
    repo = get_repository(db_path=db_path)
    repo.init_schema()
    if not repo.health_check():
        raise RuntimeError("Persistence health check failed after init")
    print("Persistence health: ok")

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting health server on {host}:{port}")
    health_server, _health_thread = start_health_server(
        lambda: repo, host=host, port=port
    )
    print(f"Health endpoint: http://{host}:{port}/health")

    application = None
    shutdown_started = False
    shutdown_event = asyncio.Event()

    async def shutdown():
        nonlocal shutdown_started
        if shutdown_started:
            return
        shutdown_started = True

        print("Shutting down gracefully...")

        if application is not None:
            try:
                if application.updater is not None:
                    await application.updater.stop()
            except Exception as exc:
                print(f"Telegram updater shutdown warning: {exc}")

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

    print("Initializing Telegram bot...")
    try:
        application = bot_module.build_application()
    except RuntimeError:
        health_server.shutdown()
        raise
    except Exception:
        health_server.shutdown()
        raise

    print("Telegram bot initialized - BOT_TOKEN present")

    try:
        await application.initialize()

        if application.updater is None:
            raise RuntimeError("Telegram updater is unavailable")

        await application.start()
        await application.updater.start_polling()

        print("=== Video Agent v1.2 Ready ===")
        print("Telegram: polling ACTIVE")
        print("Health: /health")
        print("Persistence: SQLite local")
        print("Publisher: Evidence Gate enforced; provider credentials required")

        await shutdown_event.wait()
    finally:
        if not shutdown_started:
            await shutdown()


if __name__ == "__main__":
    asyncio.run(main())
