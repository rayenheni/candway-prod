#!/usr/bin/env bash
#
# Candway safe migration + deploy workflow (H-4).
#
# Ordering guarantees:
#   1. Backup the database BEFORE anything touches it.
#   2. Run `alembic upgrade head` as a SINGLE explicit runner BEFORE the
#      app containers swap, so the new schema is in place before new code
#      boots. Production startup refuses to start on a migration mismatch
#      (see backend/startup.py), so this step is mandatory — doing it as a
#      one-shot `docker compose run` avoids the 4-worker auto-upgrade race.
#   3. Swap containers.
#   4. Poll the health endpoint; fail loudly if the app never becomes
#      healthy.
#
# Run from the checkout root on the production host:
#     bash scripts/deploy.sh
#
# Precondition: the host checkout is current (CI syncs it with
# `git fetch && git reset --hard origin/main` before invoking this).
#
set -euo pipefail

cd "$(dirname "$0")/.."

log() { echo "==> $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

PY="${PYTHON:-python3}"
command -v "${PY}" >/dev/null 2>&1 || fail "${PY} not found (set PYTHON to your interpreter)"


log "1/5 Backing up the database"
"${PY}" scripts/db_backup.py || fail "Database backup failed — aborting deploy."

log "2/5 Pulling latest images"
docker compose pull || fail "docker compose pull failed."

log "3/5 Applying alembic migrations (single runner, BEFORE app start)"
docker compose run --rm --no-deps backend alembic upgrade head || \
    fail "alembic upgrade head failed — new containers NOT started. Old stack still running."

log "4/5 Starting application"
docker compose up -d --remove-orphans
docker system prune -f >/dev/null 2>&1 || true

log "5/5 Waiting for health check"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/v1/monitoring/health}"
for _ in $(seq 1 30); do
    if curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
        log "Health OK at ${HEALTH_URL}"
        exit 0
    fi
    sleep 5
done

fail "Health check FAILED after 150s — application did not become healthy at ${HEALTH_URL}"
