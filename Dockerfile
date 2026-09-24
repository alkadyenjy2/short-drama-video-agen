# Dockerfile - Video Agent v1.2 Deployment Foundation
FROM python:3.11-slim

# Runtime app user; entrypoint prepares Railway's runtime-mounted volume
RUN useradd -m -u 1000 appuser

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    ffmpeg \
    fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

# Dependencies - deterministic from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Prepare the image-layer data directory and runtime entrypoint
RUN mkdir -p /app/data \
    && chown -R appuser:appuser /app \
    && chmod +x /app/docker-entrypoint.sh

# No secrets baked into image
# ENV values must be provided at runtime

# Start as root only long enough for the entrypoint to fix the runtime volume
# ownership, then drop to appuser before starting the application.
USER root

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).getcode()==200 else 1)" || exit 1

# Expose health port
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Graceful shutdown handled by python-telegram-bot
CMD ["python", "main.py"]
