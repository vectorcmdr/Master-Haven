# =====================================================================
# Travelers Archive — Dockerfile
# =====================================================================
# Phase 1: backend only. Phase 5 will refactor to multi-stage so the
# Vite frontend gets built in a separate stage and copied into the
# final image.

FROM python:3.12-slim

# Don't write .pyc files; flush stdout/stderr immediately so Docker
# logs show output in real time.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps:
# - curl for healthcheck / debugging inside the container
# - libpq / libjpeg / zlib not needed yet but Pillow needs build tools
#   on some platforms. python:3.12-slim has wheels for arm64 so this
#   should be a no-op install for Pillow.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so this layer is cached when only app code
# changes.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy everything else (entrypoint, alembic, app, sql)
COPY . .

# Entrypoint runs migrations then starts the server.
RUN chmod +x ./entrypoint.sh

EXPOSE 8020

# Healthcheck against /health. Docker marks the container `healthy`
# once this passes; docker compose ps shows it.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8020/health || exit 1

CMD ["./entrypoint.sh"]
