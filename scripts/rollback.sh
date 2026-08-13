#!/usr/bin/env bash
# Roll back to the previously deployed image.
#
# Resolution order for the target image:
#   1. ${ROLLBACK_IMAGE}   (env override)
#   2. ${IMAGE_<slot>}.previous  (set by a successful deploy.sh run)
#   3. <current-image>.previous  (parsed from the active service labels)
#
# Usage:
#   scripts/rollback.sh                 # roll back to the previous image
#   scripts/rollback.sh <image:tag>     # roll back to a specific image

set -euo pipefail

log()  { printf '[rollback] %s\n' "$*" >&2; }
die()  { printf '[rollback][FATAL] %s\n' "$*" >&2; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "$1 is required"; }

require_cmd docker
require_cmd curl

DEPLOY_ENV="${DEPLOY_ENV:-production}"
PROJECT="${COMPOSE_PROJECT_NAME:-lab_manager}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8000/health}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-90}"

CURRENT_IMAGE="$(
    docker compose -p "${PROJECT}" --env-file ".env.${DEPLOY_ENV}" \
        ps -q app 2>/dev/null \
    | head -1 \
    | xargs -I {} docker inspect --format '{{ index .Config.Labels "com.docker.compose.image" }}' {} 2>/dev/null \
    || true
)"

if [[ $# -ge 1 ]]; then
    TARGET_IMAGE="$1"
elif [[ -n "${ROLLBACK_IMAGE:-}" ]]; then
    TARGET_IMAGE="${ROLLBACK_IMAGE}"
elif [[ -f ".deploy/${DEPLOY_ENV}.previous" ]]; then
    TARGET_IMAGE="$(cat ".deploy/${DEPLOY_ENV}.previous")"
else
    die "No rollback target — pass an image:tag or set ROLLBACK_IMAGE"
fi

if [[ -z "${TARGET_IMAGE}" ]]; then
    die "Resolved rollback image is empty"
fi

log "Rolling back ${DEPLOY_ENV}: ${CURRENT_IMAGE:-<unknown>} -> ${TARGET_IMAGE}"

# Record the current image so a *second* rollback reverts this one.
mkdir -p ".deploy"
if [[ -n "${CURRENT_IMAGE}" ]]; then
    printf '%s\n' "${CURRENT_IMAGE}" > ".deploy/${DEPLOY_ENV}.current"
fi

# Drive the same deploy script in rolling-restart mode against the target.
"$(dirname "$0")/deploy.sh" --no-blue-green "${TARGET_IMAGE}"

# Health check is already performed by deploy.sh, but double-check here so
# rollback.sh is safe to call directly.
if ! curl -fsS --max-time 3 "${HEALTHCHECK_URL}" >/dev/null; then
    die "post-rollback health check failed"
fi

log "Rollback to ${TARGET_IMAGE} complete"
