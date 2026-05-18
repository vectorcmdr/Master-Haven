#!/usr/bin/env bash
# =====================================================================
# Travelers Archive — container entrypoint
# =====================================================================
# Runs on every container start:
#   1. Makes sure /data exists and has a media subfolder
#   2. Runs alembic migrations (idempotent — `alembic upgrade head`
#      only applies new ones)
#   3. Starts uvicorn on 0.0.0.0:8020
#
# Any step failing aborts the boot so the container is marked as
# unhealthy and we don't serve a half-broken stack.

set -euo pipefail

echo "[entrypoint] Travelers Archive starting..."
echo "[entrypoint] ENV=${ENV:-unset}  DATABASE_PATH=${DATABASE_PATH:-unset}"

# Make sure the data dir + media dir exist. /data itself is a bind
# mount from the host; subfolders may not exist on first boot.
mkdir -p "$(dirname "${DATABASE_PATH:-/data/archive.db}")"
mkdir -p "${MEDIA_PATH:-/data/media}"

# Apply any pending Alembic migrations. Alembic stores its applied-
# revision pointer in the `alembic_version` table inside the same DB,
# so re-running is safe.
echo "[entrypoint] running alembic upgrade head"
alembic upgrade head

# Seed mock data (idempotent — each insert is guarded by an existence
# check, so running on every boot is safe). Phase 2 adds this.
echo "[entrypoint] running seed"
python -m app.seed

# Start the ASGI server.
echo "[entrypoint] starting uvicorn on 0.0.0.0:8020"
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8020 \
    --proxy-headers \
    --forwarded-allow-ips='*'
