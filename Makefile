# =============================================================================
# lab-manager — Makefile
# Common entry points for local development, testing, and deployment.
# Run `make help` to see the list of targets.
# =============================================================================

# Make 4.x with .PHONY is supported; we don't depend on GNU extensions
# beyond .PHONY and basic pattern rules, so this should work on macOS too.
SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

# ---- Configuration ----------------------------------------------------------
PYTHON        ?= python3.11
PIP           ?= $(PYTHON) -m pip
VENV          ?= venv
VENV_BIN      := $(VENV)/bin
PYTEST        := $(VENV_BIN)/pytest
BLACK         := $(VENV_BIN)/black
ISORT         := $(VENV_BIN)/isort
FLAKE8        := $(VENV_BIN)/flake8
MYPY          := $(VENV_BIN)/mypy
UVICORN       := $(VENV_BIN)/uvicorn
ALEMBIC       := $(VENV_BIN)/alembic

IMAGE_NAME    ?= lab-manager
IMAGE_TAG     ?= dev
COMPOSE       ?= docker compose

.DEFAULT_GOAL := help

# ---- Help -------------------------------------------------------------------
.PHONY: help
help: ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
		/^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' \
		$(MAKEFILE_LIST)

# ---- Setup ------------------------------------------------------------------
.PHONY: install
install: ## Create venv and install all (dev + prod) dependencies.
	@if [[ ! -d "$(VENV)" ]]; then $(PYTHON) -m venv $(VENV); fi
	$(PIP) install --upgrade pip wheel
	$(PIP) install -r requirements.txt
	@if [[ -f requirements-dev.txt ]]; then $(PIP) install -r requirements-dev.txt; fi
	@if [[ -f .pre-commit-config.yaml ]] && command -v pre-commit >/dev/null; then \
		pre-commit install; \
	fi

.PHONY: update
update: ## Update pinned dependencies in requirements*.txt.
	$(PIP) install --upgrade pip
	$(PIP) install --upgrade -r requirements.txt
	@if [[ -f requirements-dev.txt ]]; then $(PIP) install --upgrade -r requirements-dev.txt; fi

# ---- Run --------------------------------------------------------------------
.PHONY: dev
dev: ## Run the dev server with hot reload on :8000.
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: run
run: ## Run the prod-style server (gunicorn + uvicorn workers).
	$(VENV_BIN)/gunicorn app.main:app \
		--bind 0.0.0.0:8000 \
		--workers ${WORKERS:-2} \
		--worker-class uvicorn.workers.UvicornWorker

# ---- Quality ----------------------------------------------------------------
.PHONY: format
format: ## Auto-format with black + isort.
	$(BLACK) app scripts tests
	$(ISORT) --profile black app scripts tests

.PHONY: lint
lint: ## Lint with flake8 (read-only).
	$(FLAKE8) app scripts tests

.PHONY: typecheck
typecheck: ## Run mypy on the app package.
	$(MYPY) app

.PHONY: format-check
format-check: ## Verify formatting without modifying files.
	$(BLACK) --check --diff app scripts tests
	$(ISORT) --check-only --profile black app scripts tests

.PHONY: security
security: ## Run bandit + pip-audit locally.
	$(VENV_BIN)/bandit -r app --severity-level medium --confidence-level medium
	$(PIP) install pip-audit
	$(VENV_BIN)/pip-audit -r requirements.txt

.PHONY: qa
qa: format-check lint typecheck ## Run the full quality gate (no tests).

# ---- Test -------------------------------------------------------------------
.PHONY: test
test: ## Run the pytest suite (uses .env.test).
	@if [[ -f .env.test ]]; then set -a; . ./.env.test; set +a; fi
	$(PYTEST) -v

.PHONY: test-cov
test-cov: ## Run pytest with coverage and fail under 60% line coverage.
	@if [[ -f .env.test ]]; then set -a; . ./.env.test; set +a; fi
	$(PYTEST) --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=60

.PHONY: test-watch
test-watch: ## Re-run pytest on file changes.
	@if [[ -f .env.test ]]; then set -a; . ./.env.test; set +a; fi
	$(PYTEST) -f

# ---- Database migrations ----------------------------------------------------
.PHONY: migrate
migrate: ## Apply Alembic migrations (alembic upgrade head).
	@if [[ -f alembic.ini ]]; then $(ALEMBIC) upgrade head; else \
		echo "alembic.ini not found; relying on in-process migrations"; \
	fi

.PHONY: makemigrations
makemigrations: ## Generate a new Alembic revision.
	$(ALEMBIC) revision --autogenerate -m "$(name)"

.PHONY: db-reset
db-reset: ## Drop and recreate the dev SQLite database.
	@rm -f lab_manager.db
	@$(PYTHON) -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"

# ---- Docker -----------------------------------------------------------------
.PHONY: docker-build
docker-build: ## Build the production Docker image.
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

.PHONY: docker-build-dev
docker-build-dev: ## Build a dev image (target=builder) with dev deps.
	docker build --target builder -t $(IMAGE_NAME):$(IMAGE_TAG)-dev .

.PHONY: docker-up
docker-up: ## Start the full stack (dev override is auto-merged).
	$(COMPOSE) up -d --build
	@$(COMPOSE) ps

.PHONY: docker-down
docker-down: ## Stop the stack and remove containers (volumes preserved).
	$(COMPOSE) down

.PHONY: docker-clean
docker-clean: ## Stop the stack and remove named volumes.
	$(COMPOSE) down -v

.PHONY: docker-logs
docker-logs: ## Tail logs from all services.
	$(COMPOSE) logs -f --tail=200

.PHONY: docker-shell
docker-shell: ## Open a shell in the running app container.
	$(COMPOSE) exec app /bin/bash || $(COMPOSE) exec app /bin/sh

.PHONY: docker-test
docker-test: ## Run pytest inside the app container.
	$(COMPOSE) exec app $(PYTEST) -v

.PHONY: docker-prod-up
docker-prod-up: ## Start the production-shape stack (no dev override).
	$(COMPOSE) -f docker-compose.yml up -d --build

# ---- Backup / restore -------------------------------------------------------
.PHONY: backup
backup: ## Run the database backup utility (uses DATABASE_URL + BACKUP_* env).
	@if [[ -f .env.production ]]; then set -a; . ./.env.production; set +a; fi
	$(PYTHON) scripts/backup.py

# ---- Deploy / rollback ------------------------------------------------------
.PHONY: deploy
deploy: ## Run scripts/deploy.sh IMAGE (blue-green). DEPLOY_ENV=production.
	@if [[ -z "$(image)" ]]; then echo "Usage: make deploy image=<image:tag>"; exit 1; fi
	DEPLOY_ENV=$${DEPLOY_ENV:-production} bash scripts/deploy.sh "$(image)"

.PHONY: rollback
rollback: ## Run scripts/rollback.sh (uses .deploy/<env>.previous).
	@if [[ -n "$(image)" ]]; then bash scripts/rollback.sh "$(image)"; else bash scripts/rollback.sh; fi

# ---- Maintenance ------------------------------------------------------------
.PHONY: clean
clean: ## Remove __pycache__, .pytest_cache, .mypy_cache, *.egg-info, build dirs.
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -prune -exec rm -rf {} +
	find . -type d -name '.mypy_cache'   -prune -exec rm -rf {} +
	find . -type d -name '.ruff_cache'   -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info'    -prune -exec rm -rf {} +
	rm -rf build/ dist/ htmlcov/ .coverage coverage.xml

.PHONY: clean-all
clean-all: clean ## clean + remove the venv.
	rm -rf $(VENV)
