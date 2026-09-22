# Dockerfile - Video Agent v1.2 Deployment Foundation
FROM python:3.11-slim

# Security: non-root
RUN useradd -m -u 1000 appuser

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Dependencies - deterministic from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Ensure data directory exists and owned by appuser
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# No secrets baked into image
# ENV values must be provided at runtime

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).getcode()==200 else 1)" || exit 1

# Expose health port
EXPOSE 8000

# Graceful shutdown handled by python-telegram-bot
# Production entrypoint
CMD ["python", "main.py"]
