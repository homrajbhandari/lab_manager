# Task Status for Research Laboratory Management System

## Overview
This file documents what has been completed and what remains to be done later. It is intended to help you continue working on the project with a clear breakdown of tasks.

The project went through Step 2 (initial CRUD for Projects / Tasks / Inventory / Samples) and then a multi-feature enhancement round documented in `C:\Users\Sushil\.claude\plans\rustling-munching-sunrise.md` — filtered lists, enum validation, pagination, bulk endpoints, and the `Task.assignee_id` migration. Both rounds are recorded below.

---

## Completed Tasks

### Round 1 — Step 2 (initial CRUD foundation)

#### 1. Project CRUD
- Implemented `Project` SQLAlchemy model in `app/models.py` with fields:
  - `id`
  - `title`
  - `description`
  - `status`
  - `priority`
  - `created_at`
  - `updated_at`
  - `owner_id`
- Preserved `owner_id` as nullable to keep authentication out of scope.
- Added Pydantic schemas in `app/schemas.py`:
  - `ProjectBase`
  - `ProjectCreate`
  - `ProjectUpdate`
  - `ProjectResponse`
- Implemented CRUD helper functions in `app/crud.py`:
  - `get_project`
  - `get_projects`
  - `create_project`
  - `update_project`
  - `delete_project`
- Added API routes in `app/main.py`:
  - `POST /projects/`
  - `GET /projects/`
  - `GET /projects/{project_id}`
  - `PUT /projects/{project_id}`
  - `DELETE /projects/{project_id}`
- Added pagination support using `skip` and `limit` for list endpoints.
- Added proper 404 handling for missing projects.

#### 2. Task CRUD
- Implemented `Task` SQLAlchemy model in `app/models.py` with fields:
  - `id`
  - `title`
  - `description`
  - `status`
  - `priority`
  - `created_at`
  - `updated_at`
  - `project_id`
- Added relationship `Task.project` and `Project.tasks` to enforce `project_id` linkage.
- Added Pydantic schemas in `app/schemas.py`:
  - `TaskBase`
  - `TaskCreate`
  - `TaskUpdate`
  - `TaskResponse`
- Implemented `Task` CRUD helpers in `app/crud.py`:
  - `get_task`
  - `get_tasks`
  - `create_task`
  - `update_task`
  - `delete_task`
- Added API routes in `app/main.py`:
  - `POST /tasks/`
  - `GET /tasks/`
  - `GET /tasks/{task_id}`
  - `PUT /tasks/{task_id}`
  - `DELETE /tasks/{task_id}`
- Validated that `project_id` exists when creating or updating a task.
- Added 404 responses for missing task or invalid project references.
- Ensured deleting a project cascades tasks via SQLAlchemy relationship.

#### 3. Inventory CRUD
- Implemented `Inventory` SQLAlchemy model in `app/models.py` with fields:
  - `id`
  - `name`
  - `description`
  - `category`
  - `quantity`
  - `unit`
  - `location`
  - `supplier`
  - `created_at`
  - `updated_at`
- Added Pydantic schemas in `app/schemas.py`:
  - `InventoryBase`
  - `InventoryCreate`
  - `InventoryUpdate`
  - `InventoryResponse`
- Implemented `Inventory` CRUD helpers in `app/crud.py`:
  - `get_inventory_item`
  - `get_inventory`
  - `create_inventory_item`
  - `update_inventory_item`
  - `delete_inventory_item`
- Added API routes in `app/main.py`:
  - `POST /inventory/`
  - `GET /inventory/`
  - `GET /inventory/{inventory_id}`
  - `PUT /inventory/{inventory_id}`
  - `DELETE /inventory/{inventory_id}`
- Added validation for `quantity` not being negative.
- Added 404 responses for missing inventory items.

#### 4. Sample CRUD
- Implemented `Sample` SQLAlchemy model in `app/models.py` with fields:
  - `id`
  - `name`
  - `description`
  - `sample_type`
  - `status`
  - `storage_location`
  - `project_id`
  - `created_at`
  - `updated_at`
- Added relationship `Sample.project` and `Project.samples`.
- Added Pydantic schemas in `app/schemas.py`:
  - `SampleBase`
  - `SampleCreate`
  - `SampleUpdate`
  - `SampleResponse`
- Implemented `Sample` CRUD helpers in `app/crud.py`:
  - `get_sample`
  - `get_samples`
  - `create_sample`
  - `update_sample`
  - `delete_sample`
- Added API routes in `app/main.py`:
  - `POST /samples/`
  - `GET /samples/`
  - `GET /samples/{sample_id}`
  - `PUT /samples/{sample_id}`
  - `DELETE /samples/{sample_id}`
- Validated that `project_id` exists for samples.
- Added 404 responses for missing sample or invalid project references.

#### 5. Database and Startup
- Kept the existing SQLAlchemy database configuration in `app/database.py`.
- Retained `Base.metadata.create_all(bind=engine)` in `app/main.py`.
- Verified the app startup and live routes via Uvicorn.
- Confirmed `/docs` is available for interactive API exploration.

---

### Round 2 — Filtered lists, enums, pagination, bulk endpoints, auth bootstrap

#### 1. Pagination dependency
- **`app/dependencies.py`** — `PaginationParams` with `skip` / `limit` / `sort_by` / `sort_order`. `paginate(query, sortable_columns)` returns `(items, total, page, pages, per_page)`. `apply_sort(...)` helper raises a 422 with the valid sort_by list on invalid input.

#### 2. Envelope extension
- **`app/utils.py`** — `success_response` gained an optional `pagination=` kwarg. The block is placed alongside the existing `total` so old clients still parse cleanly.

#### 3. Schema validation
- **`app/schemas.py`** — module-level `Literal` sets:
  - `ProjectStatus = Literal["active", "completed", "archived", "on_hold"]`
  - `TaskStatus = Literal["pending", "in_progress", "completed", "blocked"]`
  - `Priority = Literal["low", "medium", "high", "critical"]`
  - `SampleStatus = Literal["available", "reserved", "consumed", "disposed"]`
- Redeclared on `*Create` / `*Update` schemas; `*Response` schemas stay loose `str` so existing rows with non-conforming values still serialize. Defaults (`"active"`, `"medium"`, `"available"`) are valid `Literal` members.
- **Bulk input schemas** (all `extra="forbid"`, `Field(max_length=100)`, `BULK_MAX = 100`):
  - `BulkProjectsCreate`, `BulkProjectUpdateItem`, `BulkProjectsUpdate`
  - `BulkProjectsDelete` — `project_ids: list[int] = Field(min_length=1, max_length=100)`
  - `BulkTaskAssign` — `task_ids`, `assignee_id: int`
  - `BulkInventoryQuantityItem`, `BulkInventoryQuantities` — `id`, `delta: int` (signed)
  - `BulkSamplesCreate`

#### 4. Models
- **`app/models.py`** —
  - `User.hashed_password` (VARCHAR(200)), `is_active` (Boolean, default True), `role` (VARCHAR(50), default "researcher"), `tasks_assigned` relationship.
  - `Task.assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)` + `assignee` relationship. No cascade — leaving a task unassigned must not delete the user.
- All models use a `_utcnow()` helper instead of `datetime.utcnow()` (deprecation fix).

#### 5. Database & migrations
- **`app/database.py`** — `PRAGMA foreign_keys=ON` registered via `@event.listens_for(engine, "connect")` so per-connection FK enforcement actually fires (SQLite ignores FKs without this).
- **`app/migrations.py`** — new module:
  - `run_task_assignee_migration(engine)` — idempotent `ALTER TABLE tasks ADD COLUMN assignee_id ...` after `PRAGMA table_info(tasks)` check.
  - `run_user_auth_columns_migration(engine)` — added during verification because the dev sqlite was missing `users.hashed_password / is_active / role`. Also idempotent.
  - Both helpers never raise; they log and move on so app startup cannot be blocked.

#### 6. CRUD
- **`app/crud.py`** —
  - **Filtered list helpers**: `get_projects_filtered` (now also accepts statuses[], priorities[], date ranges, sort), `get_tasks_filtered`, `get_samples_filtered`, `get_inventory_filtered`, `get_users_filtered`. Inventory deliberately has no project filter (no FK).
  - **Atomic bulk helpers** (single commit per call, `IntegrityError` rolls back the whole batch):
    - `bulk_create_projects` — pre-validates `owner_id`, `db.add_all(...)`, one commit.
    - `bulk_update_projects` — looks up by id, raises `NOT_FOUND` with missing ids, mutates ORM objects, one commit.
    - `bulk_delete_projects` — FK pre-check via `db.query(Task.project_id).filter(Task.project_id.in_(ids)).distinct()` (and same for samples); raises `CONFLICT` with `{"blocked_by": {"tasks": [...], "samples": [...]}}` before deleting. Belt-and-suspenders because ORM cascade could otherwise silently cascade.
    - `bulk_assign_tasks` — verifies assignee exists + active; `query(Task).filter(Task.id.in_(ids)).update({"assignee_id": assignee}, synchronize_session="fetch")`; single commit.
    - `bulk_update_inventory_quantities` — loads referenced rows in one query, validates `quantity + delta >= 0` server-side, raises 422 with `{"would_go_negative": [...]}` if any item would go negative.
    - `bulk_register_samples` — verifies `project_id` per item; `db.add_all(...)`; one commit.

#### 7. Routes (`app/main.py`)
- All five list endpoints (`GET /projects/`, `/tasks/`, `/inventory/`, `/samples/`, `/users/`) use `Depends(PaginationParams)` and the matching filtered helper. Each returns `success_response(data=items, message="OK", total=total, pagination={...})`.
- Six bulk endpoints under `/bulk/*`, each with `current_user: models.User = Depends(auth.require_role(*allowed))`:

| Method | Path | Allowed roles |
|---|---|---|
| POST | `/bulk/projects` | admin, researcher |
| PUT | `/bulk/projects` | admin, researcher |
| DELETE | `/bulk/projects` | admin (NOT researcher) |
| POST | `/bulk/tasks/assign` | admin, researcher |
| POST | `/bulk/inventory/quantities` | admin, researcher, technician |
| POST | `/bulk/samples` | admin, researcher |

- Failure shapes (`missing_ids`, `blocked_by`, `would_go_negative`, `missing_project_ids`, `assignee_missing`) each map to a clear `APIError` with the right code (`NOT_FOUND` / `CONFLICT` / `VALIDATION_ERROR`).
- `Base.metadata.create_all(bind=engine)` followed by both migration helpers at startup.

#### 8. Verification done
- **Smoke import** — `python -c "from app import main"` succeeds; 39 routes registered.
- **Bulk route registration** — all four `/bulk/*` paths present (`/bulk/inventory/quantities`, `/bulk/projects`, `/bulk/samples`, `/bulk/tasks/assign`).
- **Migration idempotency** — running `run_task_assignee_migration` twice returns `False` both times; `assignee_id` confirmed on `tasks` table.
- **End-to-end TestClient exercise** —
  - Login → 200 + token
  - `POST /bulk/projects` (2 items) → 201, "2 projects created"
  - `PUT /bulk/projects` with one valid id + one bogus id → 404 (NOT_FOUND with missing_ids)
  - `PUT /bulk/projects` with one valid id → 200
  - Anonymous bulk call → 401
  - `DELETE /bulk/projects` → 200

#### 9. Cleanup of Round 1 follow-ups
- ✅ Wrapped all API responses in a consistent `{success, message, data, total}` envelope with `{success, message, error}` for errors — see `app/utils.py` and `app/main.py`.
- ✅ Added `README.md` with install / run / testing instructions.
- ✅ Removed temporary files like `test_api_smoke.py`.
- ✅ `.gitignore` already covers `venv/`, `__pycache__/`, `*.db`, `.pytest_cache/`.

---

## Remaining Tasks

### A. Per-role project visibility ("admin sees all, researcher sees own")
- Flagged in the plan agent's critique as out of scope. Decision still open: simple `owner_id == current_user.id` filter vs join-based membership. Implementation would live in the filtered list helper, not a separate endpoint.

### B. Add `inventory.project_id` to link inventory items to projects
- Plan kept Inventory flat as a deliberate decision (no FK existed at the time). If the requirement lands, add `project_id` (nullable) + a migration + a project_id filter on `GET /inventory/`. Same atomic bulk pattern as the other resources.

### C. Set `SECRET_KEY` in environment and silence the dev-fallback warning
- Every `app` import currently logs `RuntimeWarning: SECRET_KEY is not set; using insecure dev fallback`. Add `SECRET_KEY=...` to a `.env` (already gitignored) and document it in `README.md`. Once set, the warning can be tightened to warn-once or removed for non-dev profiles.

### D. Add unit/integration tests
- `tests/` is still empty. The plan explicitly flagged this as a follow-up. Should cover: filtered list helpers (statuses[], priorities[], date ranges, search, sort_by/sort_order), pagination block math (`page = skip // limit + 1`, `pages = ceil(total / limit)`), enum `Literal` validation on `*Create` / `*Update`, bulk happy paths, bulk rollback on partial failure, bulk-delete FK pre-check, `Task.assignee_id` set via `bulk_assign_tasks`. Use `TestClient` + a tmp sqlite or in-memory engine.

### E. Migrate from bootstrap migrations to Alembic
- `app/migrations.py` documents itself as a temporary bootstrap. The proper successor is Alembic: `alembic init`, an initial migration matching current models, and a workflow for generating follow-up migrations on schema changes. Retiring the bootstrap removes the only place we still touch the schema outside `metadata.create_all`.

### F. Git workflow and repo cleanup (Step 2 follow-up)
- Confirm the branch containing the completed work is the correct feature branch.
- Commit the Round 2 changes with a descriptive message.
- Push the branch to GitHub and verify the remote tracking branch.

---

## Suggested next steps for you

1. Address #C (`SECRET_KEY` in `.env`) — two-minute fix, stops the noisy warning on every import.
2. Address #D (tests) — the new bulk endpoints, filters, and sort logic have zero coverage. A focused `tests/test_bulk.py` + `tests/test_filters.py` would catch regressions during the next schema change.
3. Address #E (Alembic) — needed before the next column change so we don't keep growing the bootstrap module.
4. Address #A (per-role visibility) — needs a product decision on the ownership model before any code.
5. Address #B (`inventory.project_id`) — revisit only if it becomes a real requirement.
6. Address #F (commit + push) — Round 2 work has not been committed yet.

Earlier-step actions still valid:
- Open the browser at `http://127.0.0.1:8000/docs`.
- Use `/projects/`, `/tasks/`, `/inventory/`, `/samples/`, `/users/`, plus the new `/bulk/*` endpoints.
