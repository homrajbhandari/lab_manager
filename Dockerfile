# syntax=docker/dockerfile:1.6
# ---------- Stage 1: builder ----------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build deps required by some wheels (cryptography, asyncpg, etc.)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
        curl \
 && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first so dependency layer is cached
# separately from application code.
COPY requirements.txt ./
# If a dev requirements file is provided, layer it on top of the base
# requirements so the dev image includes test/lint tools.
COPY requirements-dev.txt* ./

RUN pip install --upgrade pip \
 && pip install --prefix=/install \
        -r requirements.txt

# ---------- Stage 2: production ----------
FROM python:3.11-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app \
    PORT=8000 \
    WORKERS=2 \
    LOG_LEVEL=info \
    ACCESS_LOG=-

# Runtime system deps only — no compilers.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tini \
 && rm -rf /var/lib/apt/lists/*

# Create non-root user and group for the app.
RUN groupadd --system --gid 1001 app \
 && useradd  --system --uid 1001 --gid app \
        --home-dir /app --shell /usr/sbin/nologin app

# Copy installed Python packages from the builder.
COPY --from=builder /install /usr/local

WORKDIR ${APP_HOME}

# Copy only the application source.
COPY --chown=app:app app/        ./app/
COPY --chown=app:app scripts/    ./scripts/
COPY --chown=app:app alembic.ini* ./
COPY --chown=app:app pyproject.toml* ./

# Ensure the entrypoint is executable and prepare runtime dirs.
RUN chmod +x ./scripts/entrypoint.sh \
 && mkdir -p /app/uploads /app/logs \
 && chown -R app:app /app

USER app

EXPOSE 8000

# Lightweight, in-container liveness check. The container-level HEALTHCHECK
# below calls scripts/healthcheck.py for a deeper check.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python scripts/healthcheck.py || exit 1

# tini gives us proper signal handling (SIGTERM, SIGINT) for graceful
# shutdown of the gunicorn workers.
ENTRYPOINT ["/usr/bin/tini", "--", "/app/scripts/entrypoint.sh"]

# Default command — overridden in docker-compose / k8s as needed.
CMD ["gunicorn", "app.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "50", \
     "--log-level", "info"]
