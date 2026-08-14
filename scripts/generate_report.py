"""Generate the lab-manager project report as a Word document.

Run from the project root:
    python scripts/generate_report.py

Output: lab-manager-report.docx in the project root.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT_ROOT / "lab-manager-report.docx"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def set_paragraph_font(paragraph, *, size: int = 12, bold: bool = False) -> None:
    for run in paragraph.runs:
        run.font.name = "Calibri"
        run.font.size = Pt(size)
        run.font.bold = bold


def add_heading(doc: Document, text: str, *, level: int = 1) -> None:
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.name = "Calibri"
        run.font.color.rgb = RGBColor(0x1F, 0x3A, 0x68)


def add_paragraph(
    doc: Document,
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    justify: bool = True,
) -> None:
    p = doc.add_paragraph()
    if justify:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(12)
    run.bold = bold
    run.italic = italic


def add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="List Bullet")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(12)


def add_qa(doc: Document, question: str, answer: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    q = p.add_run("Q: " + question + "\n")
    q.bold = True
    q.font.name = "Calibri"
    q.font.size = Pt(12)
    a = p.add_run("A: " + answer)
    a.font.name = "Calibri"
    a.font.size = Pt(12)


def add_page_break(doc: Document) -> None:
    doc.add_page_break()


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------
def build_document() -> Document:
    doc = Document()

    # --- Page margins ------------------------------------------------------
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # --- Title -------------------------------------------------------------
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t = title.add_run(
        "Research Laboratory Management System\n"
        "Software Project Report"
    )
    t.bold = True
    t.font.name = "Calibri"
    t.font.size = Pt(20)
    t.font.color.rgb = RGBColor(0x1F, 0x3A, 0x68)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    s = sub.add_run(
        "Version Control, Dockerization, Continuous Integration,\n"
        "Clean Coding, API Documentation, and Test Coverage"
    )
    s.italic = True
    s.font.name = "Calibri"
    s.font.size = Pt(13)

    spacer = doc.add_paragraph()
    spacer.add_run("").font.size = Pt(8)

    # =======================================================================
    # 1. Title of Software Project
    # =======================================================================
    add_heading(doc, "1. Title of Software Project", level=1)
    add_paragraph(
        doc,
        "Research Laboratory Management System (lab-manager) — A FastAPI + SQLAlchemy "
        "backend for managing the day-to-day resources of a research laboratory: "
        "projects, tasks, inventory items, and samples, with role-based authentication, "
        "CSV / Excel import-export, file attachments, and barcode scanning support.",
    )

    # =======================================================================
    # 2. Introduction
    # =======================================================================
    add_heading(doc, "2. Introduction of Software", level=1)
    add_paragraph(
        doc,
        "The Research Laboratory Management System is a backend web service that gives "
        "research groups a single place to track the moving parts of their work — the "
        "projects they are running, the tasks inside each project, the physical items "
        "they have in stock, and the samples they generate along the way. It is built "
        "on FastAPI for the HTTP layer, SQLAlchemy for the database access layer, and "
        "Pydantic for request and response validation, and it ships with role-based "
        "authentication, CSV / Excel import-export, file attachments for project "
        "documents and sample images, and barcode-based inventory lookup. The system "
        "uses SQLite during local development and PostgreSQL in containerised and "
        "production environments, and every endpoint returns a consistent JSON "
        "response envelope that makes front-end integration and error handling "
        "straightforward. The rest of this report walks through how the team used "
        "version control, how the application was Dockerised, how Continuous "
        "Integration was set up, the clean-coding practices that were followed, how "
        "the API is documented, and how test coverage was generated and used.",
    )

    # =======================================================================
    # 3. Implementation
    # =======================================================================
    add_heading(doc, "3. Implementation", level=1)

    # ---- 3.1 Version control ---------------------------------------------
    add_heading(doc, "3.1 How did your group use version control during the project?", level=2)
    add_paragraph(
        doc,
        "The project is hosted on Git. The repository uses two long-lived branches: "
        "main for production-ready code and develop for the next release. Feature "
        "work is done on short-lived topic branches off develop, merged in through "
        "pull requests, and then fast-forwarded into main once the release is "
        "ready. Every commit message describes a single logical change, and the "
        "team tried to keep commits small so the diff history is easy to read.",
    )
    add_paragraph(
        doc,
        "The .gitignore file keeps virtual environments, build artefacts, test "
        "caches, IDE settings, and local secrets out of the repository. The recent "
        "commit history shows the work flowing in the order it was actually done: "
        "pagination accuracy, project-assignment for users, authentication, data "
        "validation and bulk operations, and finally project document attachments "
        "and barcode support. There are five distinct feature commits on top of an "
        "initial project scaffold, which is exactly the kind of incremental history "
        "that makes blame, code review, and reverts easy.",
    )
    add_paragraph(
        doc,
        "Status checks are also done before each push. The CI pipeline (described "
        "in section 3.3) runs the linter, the test suite, and a Docker build on "
        "every push and pull request, so broken code is caught before it lands on "
        "main. The team is also leaning on GitHub Protected Branches so that "
        "pull requests require at least one review and a passing CI run before "
        "they can be merged.",
    )

    # ---- 3.2 Dockerization ------------------------------------------------
    add_heading(doc, "3.2 How did you dockerize the application?", level=2)
    add_paragraph(
        doc,
        "The application is fully containerised. There is a production-ready "
        "multi-stage Dockerfile, a docker-compose.yml for the production-shape "
        "stack, a docker-compose.override.yml for local development, and a "
        "comprehensive .dockerignore that keeps the image small and the build "
        "cache efficient.",
    )
    add_paragraph(
        doc,
        "The Dockerfile has two stages. The first, named builder, starts from "
        "python:3.11-slim, installs build tools such as gcc and libpq-dev, copies "
        "only the requirements file in (so the dependency layer is cached "
        "independently of the application code), and installs the Python packages "
        "into a /install prefix. The second stage, named production, starts again "
        "from python:3.11-slim, copies the installed packages from the builder, "
        "creates a dedicated non-root user (uid 1001) for the app, copies only the "
        "app, scripts, and configuration files it needs, and exposes port 8000. "
        "The default command runs gunicorn with uvicorn worker class, four workers "
        "in production, graceful timeout, and request recycling so memory leaks "
        "are bounded. A tini init is wired in as PID 1 so SIGTERM is handled "
        "cleanly during container shutdown.",
    )
    add_paragraph(
        doc,
        "The docker-compose.yml defines four services: app (the FastAPI service), "
        "db (PostgreSQL 15 with a named volume for persistence and a healthcheck "
        "based on pg_isready), redis (Redis 7 with an append-only file and an LRU "
        "eviction policy, used for caching and rate limiting), and nginx (a reverse "
        "proxy that terminates TLS, applies security headers, and forwards "
        "requests to the app). All services have explicit healthchecks, the app "
        "waits for db and redis to become healthy before starting, and named "
        "volumes keep state across restarts. The db service also mounts an "
        "initdb directory so first-time startup creates the role and database "
        "automatically.",
    )
    add_paragraph(
        doc,
        "The docker-compose.override.yml is loaded automatically by docker "
        "compose up and switches the app service into development mode: it mounts "
        "the local app, scripts, and tests folders read-only into the container, "
        "runs a single uvicorn process with --reload so source changes on the "
        "host are picked up immediately, sets APP_ENV=development, enables DEBUG, "
        "and points the app at a separate lab_manager_dev database that is seeded "
        "with sample data. This means a developer can run docker compose up and "
        "have a fully working stack with hot reload, sample data, and an admin "
        "user in a single command.",
    )
    add_paragraph(
        doc,
        "The .dockerignore file excludes Python cache directories, virtual "
        "environments, the .git folder, .env files (except the example and "
        "production templates), logs, databases, IDE settings, tests, the "
        "GitHub workflow files, and the Dockerfile itself. This keeps the build "
        "context small and prevents secrets and credentials from being copied "
        "into the image.",
    )

    # ---- 3.3 Continuous Integration --------------------------------------
    add_heading(doc, "3.3 How did you implement Continuous Integration (CI) with automated testing?", level=2)
    add_paragraph(
        doc,
        "CI is implemented as a set of GitHub Actions workflows in .github/workflows/. "
        "Three workflows cover the full pipeline: ci.yml for the everyday checks, "
        "deploy.yml for getting new versions into dev, staging, and production, "
        "and security.yml for ongoing security scanning.",
    )
    add_paragraph(
        doc,
        "The ci.yml workflow runs on every push and pull request to main and "
        "develop. It declares four jobs that run in order. The first job, lint, "
        "checks out the code, sets up Python 3.11, installs black, isort, flake8, "
        "and mypy, and runs them against the app, scripts, and tests folders. "
        "Black and isort run in --check mode, so formatting regressions fail the "
        "build. The second job, test, depends on lint. It spins up PostgreSQL 15 "
        "and Redis 7 as service containers, waits for them to be healthy, installs "
        "the application and dev dependencies, creates the schema, and runs pytest "
        "with coverage. Coverage is enforced with --cov-fail-under=60, the XML "
        "report is uploaded to Codecov if a token is configured, and the JUnit-style "
        "artefacts are kept for 14 days so failed runs are easy to inspect.",
    )
    add_paragraph(
        doc,
        "The third job, build, depends on the first two. It sets up Docker Buildx, "
        "logs in to GitHub Container Registry, computes image tags from the commit "
        "SHA and branch name, and builds and pushes the image with provenance and "
        "SBOM enabled. The fourth job, trivy, scans the just-built image and the "
        "filesystem for HIGH and CRITICAL vulnerabilities and uploads the results "
        "to the GitHub Security tab using the SARIF format. Pull requests get a "
        "build but no push, so forks cannot leak secrets into the registry.",
    )
    add_paragraph(
        doc,
        "The deploy.yml workflow drives the actual release. A push to main "
        "auto-deploys to the development environment: it runs the in-process "
        "migrations, then calls scripts/deploy.sh with the just-built image. A "
        "manual workflow_dispatch trigger is used for staging and production. "
        "Staging also runs a small load test (Locust against /health) before the "
        "deploy. Production is gated through a GitHub Environment with required "
        "reviewers, requires an explicit image tag (no SHA shortcuts), takes a "
        "PostgreSQL backup to S3 first, performs a blue-green swap, runs a final "
        "health check, and posts a Slack message on success or failure.",
    )
    add_paragraph(
        doc,
        "The security.yml workflow runs on every push and pull request plus a "
        "weekly cron job. It runs Bandit for Python static analysis, Trivy for "
        "filesystem vulnerability scanning, Gitleaks for secret detection, "
        "pip-audit for known-vulnerable Python packages, and OWASP dependency-check "
        "for a broader transitive scan on pushes to main. All of these write SARIF "
        "reports that show up in the GitHub Security tab, so vulnerabilities are "
        "tracked alongside code in one place.",
    )

    # ---- 3.4 Clean coding ------------------------------------------------
    add_heading(doc, "3.4 What clean coding practices or principles did you follow?", level=2)
    add_paragraph(
        doc,
        "Several small but consistent practices are baked into the codebase and "
        "the tooling around it:",
    )
    add_bullet(
        doc,
        "A consistent response envelope on every endpoint (success or error), "
        "so client code only has to learn one shape — { success, message, data, "
        "error }. This lives in app/utils.py and is reused everywhere.",
    )
    add_bullet(
        doc,
        "A clear separation of concerns: app/main.py is just routes, "
        "app/crud.py is the database access layer, app/models.py is the "
        "SQLAlchemy schema, app/schemas.py is the Pydantic request/response "
        "schema, app/auth.py is authentication, and app/database.py is the engine "
        "and session. New code follows the same pattern.",
    )
    add_bullet(
        doc,
        "Type hints throughout the application code, with mypy run in CI. Pydantic "
        "schemas are the single source of truth for request and response shapes, "
        "so the OpenAPI document, the runtime validation, and the editor hints "
        "all stay in sync.",
    )
    add_bullet(
        doc,
        "Consistent naming: snake_case for functions and variables, PascalCase "
        "for classes, UPPER_SNAKE_CASE for module-level constants. Error "
        "codes are short, uppercase, and defined once (NOT_FOUND, CONFLICT, "
        "UNAUTHORIZED, VALIDATION_ERROR, INTERNAL_ERROR).",
    )
    add_bullet(
        doc,
        "Defensive programming where it matters. Migrations in app/migrations.py "
        "never raise — they log and move on — so a partial schema on a stale "
        "SQLite file cannot prevent the app from starting. The password hashing "
        "module has a clearly-insecure dev fallback that prints a warning, so a "
        "missing SECRET_KEY fails loudly instead of silently using an empty key.",
    )
    add_bullet(
        doc,
        "Idempotent, one-shot bootstrap migrations instead of long ALTER chains. "
        "Each migration helper checks whether the column already exists before "
        "issuing an ALTER, and returns a bool so the caller can tell whether the "
        "schema was actually changed. This keeps the project usable with SQLite "
        "while Alembic is set up for PostgreSQL.",
    )
    add_bullet(
        doc,
        "Automated formatting and linting. Black (formatting), isort (import "
        "sorting), flake8 (linting), and mypy (type checking) all run in CI, and "
        "the same versions are pinned in requirements-dev.txt so local and CI "
        "results match. A pre-commit hook runs the same checks before each commit.",
    )
    add_bullet(
        doc,
        "Single source of truth for environment configuration. Every environment "
        "variable is documented in .env.example with a sensible default, and the "
        "production .env.production template uses placeholders that the deploy "
        "pipeline must replace, so no real secret ever lives in the repo.",
    )

    # ---- 3.5 API documentation -------------------------------------------
    add_heading(doc, "3.5 How did you use API documentation? What is its significance?", level=2)
    add_paragraph(
        doc,
        "FastAPI generates the API documentation automatically from the Pydantic "
        "schemas and the route signatures. The application exposes two "
        "documentation URLs out of the box:",
    )
    add_bullet(doc, "/docs — interactive Swagger UI, with a Try It Out button that can call the live API.")
    add_bullet(doc, "/redoc — ReDoc-style reference, cleaner for reading and printing.")
    add_paragraph(
        doc,
        "Each route in main.py is decorated with a clear summary, description, "
        "and response_model, so the generated documentation shows the expected "
        "request body, response shape, and HTTP status codes for every endpoint. "
        "Pagination parameters, sort parameters, and bulk-operation flags are all "
        "documented in the query string. Pydantic's own Field(..., description=...) "
        "metadata is used to make every field self-explanatory in the schema view.",
    )
    add_paragraph(
        doc,
        "The significance of this auto-generated documentation is hard to "
        "overstate. It means the API is documented in the same commit that adds "
        "or changes it, so the docs can never drift from the code. Front-end "
        "developers, QA, and external integrators can explore the API without "
        "having to read the Python source, and the OpenAPI JSON that FastAPI "
        "publishes at /openapi.json can be fed straight into client generators, "
        "Postman, or contract-testing tools. It also acts as a lightweight contract "
        "test: if the team changes a schema in a way that breaks the documented "
        "shape, the diff in code review is the same diff that would break a "
        "client.",
    )
    add_paragraph(
        doc,
        "The /health endpoint is documented with the same discipline and the "
        "response includes the database status, the application version, and the "
        "current environment, so the operations team can verify a deployment from "
        "the docs page alone.",
    )

    # ---- 3.6 Test coverage ----------------------------------------------
    add_heading(doc, "3.6 How did you generate and use test coverage reports?", level=2)
    add_paragraph(
        doc,
        "Test coverage is generated by pytest-cov, which wraps coverage.py. The "
        "CI workflow runs pytest with the flags --cov=app, --cov-report=xml, "
        "--cov-report=term-missing, and --cov-fail-under=60. The XML report is "
        "uploaded to Codecov (if the CODECOV_TOKEN secret is configured) so the "
        "team can see coverage trend over time, and the missing-lines summary is "
        "printed directly in the CI log so a developer can see at a glance which "
        "lines are not exercised by the test suite.",
    )
    add_paragraph(
        doc,
        "Locally, the same command is one keystroke away: pytest "
        "--cov=app --cov-report=term-missing, or simply make test-cov which adds "
        "the --cov-fail-under=60 gate. The Makefile exposes both a quick test "
        "target (make test) and a coverage-failing target (make test-cov) so it is "
        "easy to run only the checks you intend.",
    )
    add_paragraph(
        doc,
        "The pyproject.toml configures coverage.py to branch-track (so a missing "
        "else branch is reported, not just a missing line), to omit tests, "
        "migrations, and scripts folders, and to ignore boilerplate such as "
        "pragma: no cover markers and __main__ blocks. The configuration also "
        "adds show_missing = true so the report prints line numbers, which makes "
        "it easy to navigate from a coverage report to the exact line that needs "
        "a test.",
    )
    add_paragraph(
        doc,
        "The team uses the coverage report in three concrete ways. First, on "
        "every pull request the report is posted as a PR comment by Codecov, so "
        "the reviewer can see whether the new code added tests. Second, when a "
        "bug is reported, the team runs the failing case under coverage to find "
        "the nearest uncovered branch and turn that into a regression test. "
        "Third, the 60% floor in CI prevents the coverage number from quietly "
        "drifting downwards over time — a PR that drops coverage below the "
        "threshold fails the build.",
    )

    # ---- Items not yet implemented -------------------------------------
    add_heading(doc, "3.7 Items that are not yet implemented (and what is planned)", level=2)
    add_paragraph(
        doc,
        "Most of what the project set out to deliver is in place. The few areas "
        "that are still planned rather than fully implemented are listed below, "
        "along with the next step for each:",
    )
    add_bullet(
        doc,
        "Alembic is not yet wired in. The current project ships an in-process "
        "migration helper in app/migrations.py that handles the few ALTERs the "
        "schema needs (task assignee, user auth columns, inventory barcode). The "
        "Dockerfile and entrypoint already call alembic upgrade head if an "
        "alembic.ini is present, so switching to Alembic is a matter of generating "
        "the initial migration and committing alembic.ini and the migrations/ "
        "directory.",
    )
    add_bullet(
        doc,
        "The blue-green deploy path is fully scripted (scripts/deploy.sh and "
        "scripts/rollback.sh) and exercised in the GitHub Actions deploy "
        "workflow, but the production target itself has not been provisioned yet. "
        "Once the production environment is set up in GitHub and the deploy host "
        "and SSH key are added as secrets, the workflow will start producing real "
        "blue-green releases.",
    )
    add_bullet(
        doc,
        "Sentry integration is optional and only activates when SENTRY_DSN is set "
        "in the environment. The init code is in place, but no project has been "
        "provisioned in Sentry yet, so production error tracking is currently "
        "limited to structured JSON logs.",
    )
    add_bullet(
        doc,
        "Slack notifications on deploy success and failure are wired into the "
        "deploy workflow but require a SLACK_WEBHOOK_URL secret. Until that "
        "secret is added, the notification step is skipped.",
    )
    add_bullet(
        doc,
        "The Prometheus endpoint is implemented and gated by the "
        "PROMETHEUS_ENABLED environment variable, but no Grafana dashboard or "
        "alerting rule has been authored yet. The next step is to stand up a "
        "Grafana instance in the same network and import a basic dashboard "
        "based on the lab_manager_requests_total, lab_manager_request_duration_seconds, "
        "and lab_manager_db_query_duration_seconds metrics.",
    )
    add_bullet(
        doc,
        "Test coverage is currently enforced at 60%. The pytest suite covers the "
        "CRUD helpers and the import/export + barcode routes. Route handlers "
        "for the project, task, inventory, and sample CRUD endpoints are only "
        "partially covered. The next step is to lift the floor toward 80% by "
        "adding TestClient-based tests for each remaining route, and by adding "
        "property-based tests for the bulk-operation endpoints.",
    )

    # =======================================================================
    # 4. Conclusion
    # =======================================================================
    add_heading(doc, "4. Conclusion", level=1)
    add_paragraph(
        doc,
        "Over the course of this project the team went from a single "
        "lab_manager.db file to a properly engineered FastAPI service with a "
        "full CI/CD pipeline. Version control was used in the conventional "
        "Git-flow style: feature branches off develop, pull requests with CI "
        "checks, fast-forwards into main, and a commit history that tells the "
        "story of the project in order. The application is fully containerised "
        "with a multi-stage production Dockerfile, a docker-compose stack that "
        "brings up PostgreSQL, Redis, and nginx alongside the app, and a "
        "developer-friendly override that gives hot reload and seed data on a "
        "single docker compose up. Continuous Integration is implemented as a "
        "set of GitHub Actions workflows that run linting, tests, image build, "
        "and security scanning on every change, and a separate deploy workflow "
        "drives blue-green releases into development, staging, and production "
        "with required-reviewer approval gates for production. Clean coding "
        "practices — consistent response envelopes, a clear layer split, type "
        "hints, automated formatting and linting, idempotent migrations, and a "
        "single source of truth for environment configuration — are baked into "
        "both the code and the tooling. The API is self-documenting through "
        "FastAPI's automatic Swagger and ReDoc pages, and test coverage reports "
        "are generated on every CI run, enforced at a 60% floor, and uploaded to "
        "Codecov for trend analysis. A handful of items — Alembic, production "
        "target provisioning, Sentry, Slack, Grafana, and pushing coverage "
        "higher — remain as the next milestones, and each is small and "
        "well-defined. The end result is a codebase that a new contributor can "
        "clone, install, test, and run with a handful of commands, and that the "
        "team can deploy with confidence.",
    )

    return doc


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    doc = build_document()
    doc.save(str(OUTPUT))
    print(f"Report written to: {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
