# =====================================================================
# Travelers Archive — Dockerfile (multi-stage as of Phase 5)
# =====================================================================
# Stage 1: build the Vite + React frontend.
# Stage 2: Python 3.12 image with the backend + frontend dist copied in.
#
# The single final image serves both the FastAPI backend at /api/*
# and the SPA at / on port 8020.

# ---- Stage 1: frontend build ----------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /frontend

# Install deps from package.json+lock if present. The cache layer is
# invalidated only when package.json or lockfile change.
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund

# Copy the rest and build.
COPY frontend/ ./
RUN npm run build


# ---- Stage 2: Python runtime ----------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: curl for healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (best cache layer)
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy backend code (excludes frontend/ via .dockerignore)
COPY . .

# Copy the built frontend from stage 1
COPY --from=frontend /frontend/dist /app/frontend_dist

RUN chmod +x ./entrypoint.sh

EXPOSE 8020

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8020/health || exit 1

CMD ["./entrypoint.sh"]
