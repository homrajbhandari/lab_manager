#!/usr/bin/env bash
# Container entrypoint for the lab-manager FastAPI app.
#
# Responsibilities (in order):
#   1. Apply any pending Alembic migrations (if Alembic is wired in).
#      Falls back to the in-process bootstrap migrations in app/migrations.py
#      so the current SQLite-friendly flow keeps working.
#   2. Ensure a bootstrap admin user exists.
#   3. exec the supplied CMD (gunicorn by default from the Dockerfile).

set -euo pipefail

# Resolve app dir regardless of where Docker mounts us.
APP_DIR="${APP_HOME:-/app}"
cd "${APP_DIR}"

log()  { printf '[entrypoint] %s\n' "$*" >&2; }
die()  { printf '[entrypoint][FATAL] %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Wait for the database to accept connections.
# ---------------------------------------------------------------------------
wait_for_db() {
    local url="${DATABASE_URL:-sqlite:///./lab_manager.db}"
    log "Waiting for database: ${url%%@*}@<redacted>"

    # SQLite: nothing to wait for, but make sure the parent dir exists.
    if [[ "${url}" == sqlite:* ]]; then
        local db_file="${url#sqlite:///}"
        local db_dir
        db_dir="$(dirname "${db_file}")"
        mkdir -p "${db_dir}"
        return 0
    fi

    # PostgreSQL (or any TCP DB) — wait up to 60s for the port to accept
    # connections. We deliberately do not use the ORM here so a missing
    # driver or wrong host fails the container fast.
    local host port timeout
    timeout="${DB_WAIT_TIMEOUT:-60}"

    if [[ "${url}" =~ @(.*?)(:|/) ]]; then
        host="${BASH_REMATCH[1]}"
    else
        host="db"
    fi

    # Crude port extraction; good enough for postgresql:// and
    # postgresql+psycopg2:// variants.
    port="$(printf '%s' "${url}" | sed -E 's#.*://[^@]+@[^:/]+:?([0-9]+)?.*#\1#')"
    port="${port:-5432}"

    log "Probing ${host}:${port} (timeout=${timeout}s)"

    local start now
    start="$(date +%s)"
    while :; do
        if (echo > "/dev/tcp/${host}/${port}") 2>/dev/null; then
            log "Database is reachable"
            return 0
        fi
        now="$(date +%s)"
        if (( now - start > timeout )); then
            die "Database ${host}:${port} not reachable after ${timeout}s"
        fi
        sleep 2
    done
}

# ---------------------------------------------------------------------------
# 2. Run migrations.
#    Alembic is the long-term answer. Until it is wired in, the bootstrap
#    migrations in app/migrations.py run on first import of app.main.
# ---------------------------------------------------------------------------
run_migrations() {
    if [[ -f "${APP_DIR}/alembic.ini" ]]; then
        log "Running Alembic migrations"
        if ! alembic upgrade head; then
            die "Alembic migration failed"
        fi
    else
        log "No alembic.ini found — relying on in-process migrations on app startup"
    fi
}

# ---------------------------------------------------------------------------
# 3. Bootstrap admin user.
# ---------------------------------------------------------------------------
create_admin() {
    local user="${ADMIN_USERNAME:-}"
    local email="${ADMIN_EMAIL:-}"
    local pass="${ADMIN_PASSWORD:-}"

    if [[ -z "${user}" || -z "${email}" || -z "${pass}" ]]; then
        log "ADMIN_USERNAME/EMAIL/PASSWORD not all set — skipping bootstrap"
        return 0
    fi

    # Bail if a user with this username already exists. Done in Python so
    # the project's password hashing is used (and stays in one place).
    ADMIN_USERNAME="${user}" \
    ADMIN_EMAIL="${email}" \
    ADMIN_PASSWORD="${pass}" \
    python - <<'PY'
import os, sys
from sqlalchemy import select
from app.database import SessionLocal
from app import models
from app.security import hash_password

u = os.environ["ADMIN_USERNAME"]
e = os.environ["ADMIN_EMAIL"]
p = os.environ["ADMIN_PASSWORD"]

with SessionLocal() as db:
    exists = db.execute(
        select(models.User).where(models.User.username == u)
    ).scalar_one_or_none()
    if exists is not None:
        print(f"[entrypoint] admin user '{u}' already exists", file=sys.stderr)
        sys.exit(0)

    user = models.User(
        username=u,
        email=e,
        hashed_password=hash_password(p),
        is_active=True,
        role="admin",
    )
    db.add(user)
    db.commit()
    print(f"[entrypoint] created admin user '{u}'", file=sys.stderr)
PY
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
log "lab-manager entrypoint starting (env=${APP_ENV:-unset})"

wait_for_db
run_migrations
create_admin

log "Handing off to: $*"
exec "$@"
