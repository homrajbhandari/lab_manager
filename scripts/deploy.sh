#!/usr/bin/env bash
# Blue-green deploy for lab-manager.
#
# Usage:
#   scripts/deploy.sh <image:tag>            # full blue-green with smoke test
#   scripts/deploy.sh --no-blue-green <tag>  # plain rolling restart
#
# The script is environment-aware via DEPLOY_ENV (default: production).
# It assumes docker compose is available and that the project name resolves
# to a set of running services with the conventional names "app_blue",
# "app_green", "nginx" (see docker-compose.blue-green.yml).

set -euo pipefail

log()  { printf '[deploy] %s\n' "$*" >&2; }
die()  { printf '[deploy][FATAL] %s\n' "$*" >&2; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "$1 is required"; }

require_cmd docker
require_cmd curl
require_cmd awk

DEPLOY_ENV="${DEPLOY_ENV:-production}"
PROJECT="${COMPOSE_PROJECT_NAME:-lab_manager}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8000/health}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-90}"
SMOKE_TIMEOUT="${SMOKE_TIMEOUT:-60}"
IMAGE="$*"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
BLUE_GREEN=1
ARGS=()
while (( $# )); do
    case "$1" in
        --no-blue-green) BLUE_GREEN=0 ;;
        -h|--help)
            sed -n '2,12p' "$0"
            exit 0
            ;;
        *) ARGS+=("$1") ;;
    esac
    shift
done

if [[ ${#ARGS[@]} -lt 1 ]]; then
    die "usage: $0 <image:tag> [--no-blue-green]"
fi
IMAGE="${ARGS[0]}"

log "Deploying ${IMAGE} to ${DEPLOY_ENV} (blue-green=${BLUE_GREEN})"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
service_state() {
    # Echo "blue" if the blue slot is the one currently receiving traffic,
    # otherwise "green".
    local active
    active="$(
        docker compose \
            -p "${PROJECT}" \
            --env-file ".env.${DEPLOY_ENV}" \
            ps --services --status running 2>/dev/null \
        | awk -v target="nginx" '$0 == target { found=1 } END { print found ? "running" : "stopped" }'
    )"
    printf '%s\n' "$active"
}

wait_healthy() {
    local url="$1" deadline timeout
    timeout="${HEALTH_TIMEOUT}"
    deadline=$(( $(date +%s) + timeout ))
    while (( $(date +%s) < deadline )); do
        if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    return 1
}

smoke() {
    local target="$1" deadline
    deadline=$(( $(date +%s) + SMOKE_TIMEOUT ))
    while (( $(date +%s) < deadline )); do
        if curl -fsS --max-time 3 "${target}/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    return 1
}

# ---------------------------------------------------------------------------
# Blue-green
# ---------------------------------------------------------------------------
if (( BLUE_GREEN )); then
    log "Determining inactive slot"
    CURRENT="$(
        docker compose -p "${PROJECT}" \
            --env-file ".env.${DEPLOY_ENV}" \
            --profile blue-green \
            ps --services 2>/dev/null \
        | grep -E '^(app_blue|app_green)$' \
        | while read -r svc; do
            running="$(docker compose -p "${PROJECT}" --env-file ".env.${DEPLOY_ENV}" \
                ps --services --status running "$svc" 2>/dev/null | grep -c . || true)"
            printf '%s %s\n' "$svc" "$running"
        done \
        | sort -k2 -n \
        | head -1 \
        | awk '{print $1}'
    )"

    if [[ -z "${CURRENT}" ]]; then
        CURRENT="app_blue"
        log "No slot running, defaulting to ${CURRENT}"
    fi
    TARGET="app_green"
    [[ "${CURRENT}" == "app_green" ]] && TARGET="app_blue"

    log "Current slot: ${CURRENT}, deploying to: ${TARGET}"

    # Stop the target slot if it was left running from a previous attempt.
    docker compose -p "${PROJECT}" --env-file ".env.${DEPLOY_ENV}" \
        --profile blue-green stop "${TARGET}" 2>/dev/null || true

    log "Pulling image ${IMAGE}"
    docker pull "${IMAGE}"

    log "Starting ${TARGET} with new image"
    IMAGE="${IMAGE}" \
    docker compose -p "${PROJECT}" \
        --env-file ".env.${DEPLOY_ENV}" \
        --profile blue-green \
        up -d "${TARGET}"

    log "Waiting for ${TARGET} to become healthy"
    TARGET_URL="http://$(docker compose -p "${PROJECT}" \
        --env-file ".env.${DEPLOY_ENV}" \
        --profile blue-green \
        port "${TARGET}" 8000 2>/dev/null | awk -F: '{print $1}'):8000"

    if ! smoke "${TARGET_URL}"; then
        log "Smoke check on ${TARGET} failed — leaving ${CURRENT} active"
        docker compose -p "${PROJECT}" --env-file ".env.${DEPLOY_ENV}" \
            --profile blue-green stop "${TARGET}" || true
        die "smoke check failed on ${TARGET}"
    fi

    log "Switching nginx upstream to ${TARGET}"
    # Atomically swap the upstream config and reload nginx.
    TMP_CONF="$(mktemp)"
    trap 'rm -f "${TMP_CONF}"' EXIT
    sed "s/server app_blue:[0-9]*;/server ${TARGET}:8000;/g; \
         s/server app_green:[0-9]*;/server ${TARGET}:8000;/g" \
        nginx/conf.d/app.conf > "${TMP_CONF}"
    docker compose -p "${PROJECT}" --env-file ".env.${DEPLOY_ENV}" \
        exec -T nginx sh -c "cat > /etc/nginx/conf.d/app.conf" < "${TMP_CONF}"
    docker compose -p "${PROJECT}" --env-file ".env.${DEPLOY_ENV}" \
        exec -T nginx nginx -s reload

    log "Final public health check"
    if ! wait_healthy "${HEALTHCHECK_URL}"; then
        log "Final health check failed — rolling nginx back to ${CURRENT}"
        sed -i "s/server ${TARGET}:8000;/server ${CURRENT}:8000;/g" nginx/conf.d/app.conf
        docker compose -p "${PROJECT}" --env-file ".env.${DEPLOY_ENV}" \
            exec -T nginx sh -c "cat > /etc/nginx/conf.d/app.conf" < nginx/conf.d/app.conf
        docker compose -p "${PROJECT}" --env-file ".env.${DEPLOY_ENV}" \
            exec -T nginx nginx -s reload
        die "post-switch health check failed"
    fi

    log "Stopping previous slot ${CURRENT}"
    docker compose -p "${PROJECT}" --env-file ".env.${DEPLOY_ENV}" \
        --profile blue-green stop "${CURRENT}" || true

    log "Deployment of ${IMAGE} to ${DEPLOY_ENV} complete"
    exit 0
fi

# ---------------------------------------------------------------------------
# Rolling restart
# ---------------------------------------------------------------------------
log "Rolling restart with ${IMAGE}"
docker pull "${IMAGE}"
docker compose -p "${PROJECT}" --env-file ".env.${DEPLOY_ENV}" \
    up -d --no-deps app
if ! wait_healthy "${HEALTHCHECK_URL}"; then
    die "post-deploy health check failed"
fi
log "Rolling deploy complete"
