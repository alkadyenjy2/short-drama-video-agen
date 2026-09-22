# main.py - Video Agent v1.2 Deployment Foundation - Production entrypoint
# Combines: persistence init + health server + telegram bot
# No hardcoded secrets, fail-fast on BOT_TOKEN missing

import os
import asyncio
import signal
from dotenv import load_dotenv

# Load .env if exists (dev), but env vars take precedence (prod)
load_dotenv()

from persistence.repository import get_repository
from health import start_health_server

# Import bot components from bot.py v1.1 (we reuse behavior)
import bot as bot_module

def get_bot_token():
    return bot_module.get_bot_token()

async def main():
    print("=== Video Agent v1.2 Deployment Foundation Starting ===")
    
    # 1. Persistence init
    db_path = os.getenv("DATABASE_PATH", "./data/video_agent.db")
    print(f"Initializing persistence: {db_path}")
    repo = get_repository(db_path=db_path)
    try:
        repo.init_schema()
        print("Persistence schema initialized")
        if not repo.health_check():
            raise RuntimeError("Persistence health check failed after init")
        print("Persistence health: ok")
    except Exception as e:
        print(f"FATAL: Persistence init failed: {e}")
        # Health endpoint will report 503
        raise
    
    # 2. Health server - non-blocking
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting health server on {host}:{port}")
    health_server, health_thread = start_health_server(lambda: repo, host=host, port=port)
    print(f"Health endpoint: http://{host}:{port}/health")
    
    # 3. Telegram bot - fail-fast on BOT_TOKEN missing (already in get_bot_token)
    print("Initializing Telegram bot...")
    try:
        application = bot_module.build_application()
        # Inject repository into bot context if needed (for future)
        # For v1.2, bot.py still uses in-memory but we will integrate
        print("Telegram bot initialized - BOT_TOKEN present")
    except RuntimeError as e:
        print(f"FATAL: {e}")
        raise
    except Exception as e:
        print(f"FATAL: Bot init failed: {e}")
        raise
    
    # 4. Graceful shutdown
    def handle_shutdown(signum, frame):
        print(f"Received signal {signum}, shutting down gracefully...")
        health_server.shutdown()
        # application.stop() would be called in real polling loop
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    print("=== Video Agent v1.2 Ready ===")
    print("Health: GET /health")
    print("Bot: polling mode (for production, run with polling or webhook)")
    print("Persistence: SQLite local - migration path to Postgres in DEPLOYMENT.md")
    print("Publisher: Evidence Gate enforced - no real APIs yet")
    
    # For v1.2 foundation, we don't start polling indefinitely in this demo
    # Production would: await application.initialize(); await application.start(); await application.updater.start_polling()
    # For testing, we just verify init works
    return {"repo": repo, "health_server": health_server, "application": application}

if __name__ == "__main__":
    asyncio.run(main())
