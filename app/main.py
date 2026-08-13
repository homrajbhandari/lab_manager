import csv
import io
import logging
import mimetypes
import os
import re
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Query, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from openpyxl import Workbook, load_workbook
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import auth, crud, models, schemas
from app.database import Base, engine, get_db
from app.dependencies import PaginationParams
from app.logging_config import (
    configure_logging,
    request_id_var,
    trace_id_var,
)
from app.metrics import (
    MetricsMiddleware,
    is_enabled as metrics_enabled,
    metrics_endpoint,
    setup_metrics,
)
from app.migrations import (
    run_inventory_barcode_migration,
    run_task_assignee_migration,
    run_user_auth_columns_migration,
)
from app.utils import (
    APIError,
    CONFLICT,
    INTERNAL_ERROR,
    NOT_FOUND,
    UNAUTHORIZED,
    VALIDATION_ERROR,
    error_response,
    success_response,
)


Base.metadata.create_all(bind=engine)
run_task_assignee_migration(engine)
run_user_auth_columns_migration(engine)
run_inventory_barcode_migration(engine)


# Configure structured logging before anything that might log.
configure_logging()
logger = logging.getLogger("app.main")


app = FastAPI(
    title="Research Laboratory Management System",
    description="API for managing research laboratory resources.",
    version="1.0.0"
)


# --- CORS ----------------------------------------------------------------
_cors_origins_raw = os.getenv("CORS_ORIGINS", "*")
_cors_origins = (
    ["*"] if _cors_origins_raw.strip() == "*"
    else [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() in {"1", "true", "yes"},
    allow_methods=os.getenv("CORS_ALLOW_METHODS", "GET,POST,PUT,PATCH,DELETE,OPTIONS").split(","),
    allow_headers=os.getenv("CORS_ALLOW_HEADERS", "Authorization,Content-Type,Accept,X-Request-ID").split(","),
    expose_headers=["X-Request-ID"],
)

# --- Trusted hosts (only enforced in production) -------------------------
if os.getenv("APP_ENV", "development").lower() == "production":
    _allowed_hosts = [
        h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()
    ]
    if _allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)

# --- Metrics -------------------------------------------------------------
if metrics_enabled():
    setup_metrics()
    app.add_middleware(MetricsMiddleware)


# --- Security headers ----------------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Inject per-request id propagation and a small set of defensive
    response headers. Cheap to run on every request.
    """
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    trace_id   = request.headers.get("x-trace-id")   or request_id
    rid_token  = request_id_var.set(request_id)
    tid_token  = trace_id_var.set(trace_id)
    started    = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        request_id_var.reset(rid_token)
        trace_id_var.reset(tid_token)
        logger.info(
            "%s %s -> %s in %dms",
            request.method, request.url.path, "-", elapsed_ms,
            extra={"event": "request", "duration_ms": elapsed_ms},
        )
    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
    )
    return response


_UPLOAD_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_SKIP_IMPORT_FIELDS = {"id", "created_at", "updated_at", "assignee_id"}
_INTEGER_IMPORT_FIELDS = {"owner_id", "project_id", "quantity"}


RESOURCE_CONFIG: dict[str, dict[str, Any]] = {
    "projects": {
        "model": models.Project,
        "schema": schemas.ProjectCreate,
        "create": crud.create_project,
        "fields": [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "owner_id",
            "created_at",
            "updated_at",
        ],
    },
    "tasks": {
        "model": models.Task,
        "schema": schemas.TaskCreate,
        "create": crud.create_task,
        "fields": [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "project_id",
            "assignee_id",
            "created_at",
            "updated_at",
        ],
    },
    "inventory": {
        "model": models.Inventory,
        "schema": schemas.InventoryCreate,
        "create": crud.create_inventory_item,
        "fields": [
            "id",
            "name",
            "description",
            "category",
            "quantity",
            "unit",
            "location",
            "supplier",
            "barcode",
            "created_at",
            "updated_at",
        ],
    },
    "samples": {
        "model": models.Sample,
        "schema": schemas.SampleCreate,
        "create": crud.create_sample,
        "fields": [
            "id",
            "name",
            "description",
            "sample_type",
            "status",
            "storage_location",
            "project_id",
            "created_at",
            "updated_at",
        ],
    },
}


def _safe_filename(filename: str) -> str:
    base = Path(filename or "upload.bin").name
    safe = _UPLOAD_NAME_RE.sub("_", base).strip("._")

    if not safe:
        return "upload.bin"

    return safe[:200]


def _upload_root() -> Path:
    return Path(os.getenv("UPLOAD_ROOT", "uploads")).resolve()


def _save_upload(upload: UploadFile, *path_parts: str) -> tuple[str, str, str, int]:
    filename = _safe_filename(upload.filename or "upload.bin")
    folder = _upload_root().joinpath(*path_parts)
    folder.mkdir(parents=True, exist_ok=True)

    stored_path = folder / f"{uuid4().hex}_{filename}"

    with stored_path.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)

    size_bytes = stored_path.stat().st_size
    if size_bytes == 0:
        stored_path.unlink(missing_ok=True)
        raise APIError(
            status_code=422,
            message="Uploaded file is empty",
            code=VALIDATION_ERROR,
        )

    content_type = (
        upload.content_type
        or mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )

    return filename, str(stored_path), content_type, size_bytes


def _delete_stored_file(stored_path: Optional[str]) -> None:
    if stored_path is None:
        return

    try:
        Path(stored_path).unlink(missing_ok=True)
    except OSError:
        pass


def _attachment_file_response(
    attachment,
    missing_message: str,
) -> FileResponse:
    path = Path(attachment.stored_path)

    if not path.is_file():
        raise APIError(
            status_code=404,
            message=missing_message,
            code=NOT_FOUND,
        )

    media_type = (
        attachment.content_type
        or mimetypes.guess_type(attachment.filename)[0]
        or "application/octet-stream"
    )

    return FileResponse(
        path,
        media_type=media_type,
        filename=attachment.filename,
    )


def _project_attachment_payload(attachment) -> dict:
    payload = schemas.ProjectAttachmentResponse.model_validate(
        attachment
    ).model_dump()
    payload["download_url"] = (
        f"/projects/{attachment.project_id}/attachments/{attachment.id}/download"
    )
    return payload


def _sample_attachment_payload(attachment) -> dict:
    payload = schemas.SampleAttachmentResponse.model_validate(
        attachment
    ).model_dump()
    payload["download_url"] = (
        f"/samples/{attachment.sample_id}/attachments/{attachment.id}/download"
    )
    return payload


def _serialize_export_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ""
    return value


def _export_rows(resource: str, db: Session) -> tuple[list[str], list[dict]]:
    config = RESOURCE_CONFIG[resource]
    fields = config["fields"]
    model = config["model"]
    rows = db.query(model).order_by(model.id.asc()).all()

    return fields, [
        {
            field: _serialize_export_value(getattr(row, field, None))
            for field in fields
        }
        for row in rows
    ]


def _detect_import_format(
    upload: UploadFile,
    requested_format: Optional[str],
) -> str:
    if requested_format is not None:
        return requested_format

    suffix = Path(upload.filename or "").suffix.lower()

    if suffix == ".csv":
        return "csv"
    if suffix == ".xlsx":
        return "xlsx"

    content_type = (upload.content_type or "").lower()

    if "csv" in content_type:
        return "csv"
    if "spreadsheet" in content_type or "excel" in content_type:
        return "xlsx"

    raise APIError(
        status_code=422,
        message="Could not determine import format; use .csv, .xlsx, or file_format",
        code=VALIDATION_ERROR,
    )


def _parse_csv_rows(contents: bytes) -> list[dict]:
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise APIError(
            status_code=422,
            message="CSV file must be UTF-8 encoded",
            code=VALIDATION_ERROR,
        ) from exc

    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        raise APIError(
            status_code=422,
            message="Import file must include a header row",
            code=VALIDATION_ERROR,
        )

    return [
        row for row in reader
        if any(value not in (None, "") for value in row.values())
    ]


def _parse_xlsx_rows(contents: bytes) -> list[dict]:
    try:
        workbook = load_workbook(
            io.BytesIO(contents),
            read_only=True,
            data_only=True,
        )
    except Exception as exc:
        raise APIError(
            status_code=422,
            message="Excel import must be a valid .xlsx workbook",
            code=VALIDATION_ERROR,
            details=str(exc),
        ) from exc

    worksheet = workbook.active
    rows = worksheet.iter_rows(values_only=True)

    try:
        headers = next(rows)
    except StopIteration as exc:
        raise APIError(
            status_code=422,
            message="Import file must include a header row",
            code=VALIDATION_ERROR,
        ) from exc

    fieldnames = [
        str(value).strip() if value is not None else ""
        for value in headers
    ]

    if not any(fieldnames):
        raise APIError(
            status_code=422,
            message="Import file must include a header row",
            code=VALIDATION_ERROR,
        )

    parsed_rows = []
    for values in rows:
        if not any(value not in (None, "") for value in values):
            continue
        parsed_rows.append(dict(zip(fieldnames, values)))

    workbook.close()
    return parsed_rows


def _parse_tabular_upload(upload: UploadFile, file_format: Optional[str]) -> list[dict]:
    contents = upload.file.read()

    if not contents:
        raise APIError(
            status_code=422,
            message="Import file is empty",
            code=VALIDATION_ERROR,
        )

    detected = _detect_import_format(upload, file_format)

    if detected == "csv":
        return _parse_csv_rows(contents)

    return _parse_xlsx_rows(contents)


def _normalize_import_row(row: dict, allowed_fields: list[str]) -> dict:
    field_set = set(allowed_fields)
    normalized = {}

    for raw_key, raw_value in row.items():
        if raw_key is None:
            continue

        key = str(raw_key).strip()

        if key not in field_set or key in _SKIP_IMPORT_FIELDS:
            continue

        value = raw_value.strip() if isinstance(raw_value, str) else raw_value

        if value in (None, ""):
            continue

        if (
            key in _INTEGER_IMPORT_FIELDS
            and isinstance(value, float)
            and value.is_integer()
        ):
            value = int(value)

        normalized[key] = value

    return normalized


@app.exception_handler(APIError)
async def api_error_handler(_: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            message=exc.message,
            code=exc.code,
            details=exc.details,
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=error_response(
            message="Validation error",
            code=VALIDATION_ERROR,
            details=exc.errors(),
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=error_response(
            message="Internal server error",
            code=INTERNAL_ERROR,
            details=str(exc),
        ),
    )


@app.get("/")
def root():
    return success_response(
        data={"docs": "/docs"},
        message="Welcome to Research Laboratory Management System",
    )


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Liveness + readiness probe.

    Returns ``status="healthy"`` only when the database engine is reachable.
    A failing DB is reported as ``status="degraded"`` so an external
    orchestrator can decide whether to mark the instance unhealthy.
    """
    db_ok = True
    db_detail: Optional[str] = None
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - report any failure
        db_ok = False
        db_detail = str(exc)
        logger.warning("healthcheck: database ping failed: %s", exc)

    return success_response(
        data={
            "status":      "healthy" if db_ok else "degraded",
            "db":          "ok" if db_ok else "error",
            "db_detail":   db_detail,
            "version":     app.version,
            "environment": os.getenv("APP_ENV", "development"),
        },
        message="Service is healthy" if db_ok else "Service is degraded",
    )


# /metrics is only mounted when Prometheus scraping is enabled, so
# unauthenticated callers (which only exist inside the cluster) can pull
# the exposition format without authenticating.
if metrics_enabled():
    @app.get(os.getenv("METRICS_PATH", "/metrics"), include_in_schema=False)
    async def _prometheus_metrics():  # noqa: WPS430 - nested by design
        return await metrics_endpoint()


@app.get(
    "/export/{resource}",
    response_model=None
)
def export_resource_data(
    resource: schemas.ImportExportResource,
    file_format: schemas.ImportExportFormat = Query("csv"),
    db: Session = Depends(get_db),
):

    fields, rows = _export_rows(resource, db)
    filename = f"{resource}.{file_format}"

    if file_format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = resource[:31]
    worksheet.append(fields)

    for row in rows:
        worksheet.append([row[field] for field in fields])

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@app.post(
    "/import/{resource}",
    response_model=None,
    status_code=201
)
def import_resource_data(
    resource: schemas.ImportExportResource,
    file: UploadFile = File(...),
    file_format: Optional[schemas.ImportExportFormat] = Query(None),
    db: Session = Depends(get_db),
):

    config = RESOURCE_CONFIG[resource]
    rows = _parse_tabular_upload(file, file_format)
    created_ids = []
    row_errors = []

    for row_number, row in enumerate(rows, start=2):
        normalized = _normalize_import_row(row, config["fields"])

        try:
            item = config["schema"].model_validate(normalized)
        except ValidationError as exc:
            row_errors.append(
                {
                    "row": row_number,
                    "errors": exc.errors(),
                }
            )
            continue

        try:
            created = config["create"](db, item)
        except Exception as exc:
            db.rollback()
            row_errors.append(
                {
                    "row": row_number,
                    "errors": [str(exc)],
                }
            )
            continue

        if created is None:
            row_errors.append(
                {
                    "row": row_number,
                    "errors": [
                        "Referenced record missing or unique value already exists"
                    ],
                }
            )
            continue

        created_ids.append(created.id)

    failed = len(row_errors)
    imported = len(created_ids)

    return success_response(
        data={
            "resource": resource,
            "imported": imported,
            "failed": failed,
            "total_rows": len(rows),
            "created_ids": created_ids,
            "errors": row_errors,
        },
        message=f"Imported {imported} {resource} rows",
    )


@app.post(
    "/users/",
    response_model=None,
    status_code=201
)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):

    created = crud.create_user(db, user)

    if created is None:
        raise APIError(
            status_code=409,
            message="Username or email already exists",
            code=CONFLICT,
        )

    return success_response(
        data=schemas.UserResponse.model_validate(created),
        message="User created",
    )


@app.post(
    "/token",
    response_model=None
)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    user = auth.authenticate_user(
        db, form_data.username, form_data.password
    )

    if user is None:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Invalid username or password",
            code=UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Inactive user",
            code=UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth.create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role},
    )

    return success_response(
        data={
            "access_token": access_token,
            "token_type": "bearer"
        },
        message="Login successful",
    )


@app.get(
    "/users/me",
    response_model=None
)
def read_users_me(
    current_user: models.User = Depends(auth.get_current_user)
):

    return success_response(
        data=schemas.UserResponse.model_validate(current_user),
        message="OK",
    )


@app.get(
    "/users/",
    response_model=None
)
def get_users(
    pagination: PaginationParams = Depends(),
    roles: Optional[list[str]] = Query(None),
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    db: Session = Depends(get_db)
):

    query = db.query(models.User)

    if roles:
        query = query.filter(models.User.role.in_(roles))
    if is_active is not None:
        query = query.filter(models.User.is_active == is_active)
    if search:
        query = query.filter(
            models.User.username.contains(search) |
            models.User.email.contains(search) |
            models.User.full_name.contains(search)
        )
    if created_from:
        query = query.filter(models.User.created_at >= created_from)
    if created_to:
        query = query.filter(models.User.created_at <= created_to)

    items, total, page, pages, per_page = pagination.paginate(
        query, sortable_columns={"id", "username", "email", "role", "created_at"}
    )

    return success_response(
        data=[schemas.UserResponse.model_validate(u) for u in items],
        message="OK",
        total=total,
        pagination=pagination.pagination_block(total, page, pages, per_page),
    )


@app.get(
    "/users/{user_id}",
    response_model=None
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db)
):

    user = crud.get_user(db, user_id)

    if user is None:
        raise APIError(
            status_code=404,
            message="User not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=schemas.UserResponse.model_validate(user),
        message="OK",
    )


@app.put(
    "/users/{user_id}",
    response_model=None
)
def update_user(
    user_id: int,
    user_data: schemas.UserUpdate,
    db: Session = Depends(get_db)
):

    user = crud.update_user(db, user_id, user_data)

    if user is None:
        raise APIError(
            status_code=404,
            message="User not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=schemas.UserResponse.model_validate(user),
        message="User updated",
    )


@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db)
):

    deleted = crud.delete_user(db, user_id)

    if not deleted:
        raise APIError(
            status_code=404,
            message="User not found",
            code=NOT_FOUND,
        )

    return success_response(
        data={"id": user_id},
        message="User deleted successfully",
    )


@app.post(
    "/projects/",
    response_model=None,
    status_code=201
)
def create_project(
    project: schemas.ProjectCreate,
    db: Session = Depends(get_db)
):

    created = crud.create_project(db, project)
    return success_response(
        data=created,
        message="Project created",
    )


@app.get(
    "/projects/",
    response_model=None
)
def get_projects(
    pagination: PaginationParams = Depends(),
    statuses: Optional[list[str]] = Query(None),
    priorities: Optional[list[str]] = Query(None),
    search: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    updated_from: Optional[datetime] = None,
    updated_to: Optional[datetime] = None,
    db: Session = Depends(get_db)
):

    query = db.query(models.Project)

    if statuses:
        query = query.filter(models.Project.status.in_(statuses))
    if priorities:
        query = query.filter(models.Project.priority.in_(priorities))
    if search:
        query = query.filter(
            models.Project.title.contains(search) |
            models.Project.description.contains(search)
        )
    if created_from:
        query = query.filter(models.Project.created_at >= created_from)
    if created_to:
        query = query.filter(models.Project.created_at <= created_to)
    if updated_from:
        query = query.filter(models.Project.updated_at >= updated_from)
    if updated_to:
        query = query.filter(models.Project.updated_at <= updated_to)

    items, total, page, pages, per_page = pagination.paginate(
        query,
        sortable_columns={"id", "title", "created_at", "updated_at",
                          "priority", "status"},
    )

    return success_response(
        data=items,
        message="OK",
        total=total,
        pagination=pagination.pagination_block(total, page, pages, per_page),
    )


@app.get(
    "/projects/{project_id}",
    response_model=None
)
def get_project(
    project_id: int,
    db: Session = Depends(get_db)
):

    project = crud.get_project(db, project_id)

    if project is None:
        raise APIError(
            status_code=404,
            message="Project not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=project,
        message="OK",
    )


@app.put(
    "/projects/{project_id}",
    response_model=None
)
def update_project(
    project_id: int,
    project_data: schemas.ProjectUpdate,
    db: Session = Depends(get_db)
):

    project = crud.update_project(db, project_id, project_data)

    if project is None:
        raise APIError(
            status_code=404,
            message="Project not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=project,
        message="Project updated",
    )


@app.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db)
):

    deleted = crud.delete_project(db, project_id)

    if not deleted:
        raise APIError(
            status_code=404,
            message="Project not found",
            code=NOT_FOUND,
        )

    return success_response(
        data={"id": project_id},
        message="Project deleted successfully",
    )


@app.post(
    "/projects/{project_id}/attachments/",
    response_model=None,
    status_code=201
)
def upload_project_attachment(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    filename, stored_path, content_type, size_bytes = _save_upload(
        file,
        "projects",
        str(project_id),
    )

    attachment = crud.create_project_attachment(
        db,
        project_id=project_id,
        filename=filename,
        stored_path=stored_path,
        content_type=content_type,
        size_bytes=size_bytes,
    )

    if attachment is None:
        _delete_stored_file(stored_path)
        raise APIError(
            status_code=404,
            message="Project not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=_project_attachment_payload(attachment),
        message="Project attachment uploaded",
    )


@app.get(
    "/projects/{project_id}/attachments/",
    response_model=None
)
def list_project_attachments(
    project_id: int,
    db: Session = Depends(get_db),
):

    attachments = crud.list_project_attachments(db, project_id)

    if attachments is None:
        raise APIError(
            status_code=404,
            message="Project not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=[_project_attachment_payload(item) for item in attachments],
        message="OK",
        total=len(attachments),
    )


@app.get(
    "/projects/{project_id}/attachments/{attachment_id}",
    response_model=None
)
def get_project_attachment(
    project_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
):

    attachment = crud.get_project_attachment(db, project_id, attachment_id)

    if attachment is None:
        raise APIError(
            status_code=404,
            message="Project attachment not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=_project_attachment_payload(attachment),
        message="OK",
    )


@app.get(
    "/projects/{project_id}/attachments/{attachment_id}/download",
    response_model=None
)
def download_project_attachment(
    project_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
):

    attachment = crud.get_project_attachment(db, project_id, attachment_id)

    if attachment is None:
        raise APIError(
            status_code=404,
            message="Project attachment not found",
            code=NOT_FOUND,
        )

    return _attachment_file_response(
        attachment,
        "Project attachment file not found",
    )


@app.delete(
    "/projects/{project_id}/attachments/{attachment_id}",
    response_model=None
)
def delete_project_attachment(
    project_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
):

    deleted = crud.delete_project_attachment(db, project_id, attachment_id)

    if deleted is None:
        raise APIError(
            status_code=404,
            message="Project attachment not found",
            code=NOT_FOUND,
        )

    _delete_stored_file(deleted["stored_path"])

    return success_response(
        data={"id": attachment_id, "project_id": project_id},
        message="Project attachment deleted successfully",
    )


@app.post(
    "/tasks/",
    response_model=None,
    status_code=201
)
def create_task(
    task: schemas.TaskCreate,
    db: Session = Depends(get_db)
):

    created_task = crud.create_task(db, task)

    if created_task is None:
        raise APIError(
            status_code=404,
            message="Project not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=created_task,
        message="Task created",
    )


@app.get(
    "/tasks/",
    response_model=None
)
def get_tasks(
    pagination: PaginationParams = Depends(),
    statuses: Optional[list[str]] = Query(None),
    priorities: Optional[list[str]] = Query(None),
    project_ids: Optional[list[int]] = Query(None),
    assignee_ids: Optional[list[int]] = Query(None),
    search: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    updated_from: Optional[datetime] = None,
    updated_to: Optional[datetime] = None,
    db: Session = Depends(get_db)
):

    query = db.query(models.Task)

    if statuses:
        query = query.filter(models.Task.status.in_(statuses))
    if priorities:
        query = query.filter(models.Task.priority.in_(priorities))
    if project_ids:
        query = query.filter(models.Task.project_id.in_(project_ids))
    if assignee_ids:
        query = query.filter(models.Task.assignee_id.in_(assignee_ids))
    if search:
        query = query.filter(
            models.Task.title.contains(search) |
            models.Task.description.contains(search)
        )
    if created_from:
        query = query.filter(models.Task.created_at >= created_from)
    if created_to:
        query = query.filter(models.Task.created_at <= created_to)
    if updated_from:
        query = query.filter(models.Task.updated_at >= updated_from)
    if updated_to:
        query = query.filter(models.Task.updated_at <= updated_to)

    items, total, page, pages, per_page = pagination.paginate(
        query,
        sortable_columns={"id", "title", "created_at", "updated_at",
                          "priority", "status", "project_id", "assignee_id"},
    )

    return success_response(
        data=items,
        message="OK",
        total=total,
        pagination=pagination.pagination_block(total, page, pages, per_page),
    )


@app.get(
    "/tasks/{task_id}",
    response_model=None
)
def get_task(
    task_id: int,
    db: Session = Depends(get_db)
):

    task = crud.get_task(db, task_id)

    if task is None:
        raise APIError(
            status_code=404,
            message="Task not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=task,
        message="OK",
    )


@app.put(
    "/tasks/{task_id}",
    response_model=None
)
def update_task(
    task_id: int,
    task_data: schemas.TaskUpdate,
    db: Session = Depends(get_db)
):

    task = crud.update_task(db, task_id, task_data)

    if task is None:
        raise APIError(
            status_code=404,
            message="Task not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=task,
        message="Task updated",
    )


@app.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db)
):

    deleted = crud.delete_task(db, task_id)

    if not deleted:
        raise APIError(
            status_code=404,
            message="Task not found",
            code=NOT_FOUND,
        )

    return success_response(
        data={"id": task_id},
        message="Task deleted successfully",
    )


@app.post(
    "/inventory/",
    response_model=None,
    status_code=201
)
def create_inventory_item(
    inventory_item: schemas.InventoryCreate,
    db: Session = Depends(get_db)
):

    created = crud.create_inventory_item(db, inventory_item)

    if created is None:
        raise APIError(
            status_code=409,
            message="Inventory barcode already exists",
            code=CONFLICT,
        )

    return success_response(
        data=created,
        message="Inventory item created",
    )


@app.get(
    "/inventory/",
    response_model=None
)
def get_inventory(
    pagination: PaginationParams = Depends(),
    categories: Optional[list[str]] = Query(None),
    locations: Optional[list[str]] = Query(None),
    suppliers: Optional[list[str]] = Query(None),
    search: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    updated_from: Optional[datetime] = None,
    updated_to: Optional[datetime] = None,
    db: Session = Depends(get_db)
):

    query = db.query(models.Inventory)

    if categories:
        query = query.filter(models.Inventory.category.in_(categories))
    if locations:
        query = query.filter(models.Inventory.location.in_(locations))
    if suppliers:
        query = query.filter(models.Inventory.supplier.in_(suppliers))
    if search:
        query = query.filter(
            models.Inventory.name.contains(search) |
            models.Inventory.description.contains(search) |
            models.Inventory.supplier.contains(search) |
            models.Inventory.barcode.contains(search)
        )
    if created_from:
        query = query.filter(models.Inventory.created_at >= created_from)
    if created_to:
        query = query.filter(models.Inventory.created_at <= created_to)
    if updated_from:
        query = query.filter(models.Inventory.updated_at >= updated_from)
    if updated_to:
        query = query.filter(models.Inventory.updated_at <= updated_to)

    items, total, page, pages, per_page = pagination.paginate(
        query,
        sortable_columns={"id", "name", "quantity", "created_at",
                          "updated_at", "category", "location"},
    )

    return success_response(
        data=items,
        message="OK",
        total=total,
        pagination=pagination.pagination_block(total, page, pages, per_page),
    )


@app.post(
    "/inventory/scan",
    response_model=None
)
def scan_inventory_barcode(
    payload: schemas.BarcodeScanRequest,
    db: Session = Depends(get_db),
):

    inventory_item = crud.get_inventory_item_by_barcode(db, payload.barcode)

    if inventory_item is None:
        raise APIError(
            status_code=404,
            message="Inventory item not found for barcode",
            code=NOT_FOUND,
            details={"barcode": payload.barcode},
        )

    return success_response(
        data=schemas.InventoryResponse.model_validate(inventory_item),
        message="Inventory item scanned",
    )


@app.post(
    "/inventory/scan/quantity",
    response_model=None
)
def adjust_inventory_quantity_by_barcode(
    payload: schemas.InventoryBarcodeQuantityAdjustment,
    db: Session = Depends(get_db),
):

    inventory_item = crud.get_inventory_item_by_barcode(db, payload.barcode)

    if inventory_item is None:
        raise APIError(
            status_code=404,
            message="Inventory item not found for barcode",
            code=NOT_FOUND,
            details={"barcode": payload.barcode},
        )

    next_quantity = inventory_item.quantity + payload.delta

    if next_quantity < 0:
        raise APIError(
            status_code=422,
            message="Quantity adjustment would result in negative stock",
            code=VALIDATION_ERROR,
            details={
                "barcode": payload.barcode,
                "current": inventory_item.quantity,
                "delta": payload.delta,
            },
        )

    updated = crud.update_inventory_item(
        db,
        inventory_item.id,
        schemas.InventoryUpdate(quantity=next_quantity),
    )

    return success_response(
        data=schemas.InventoryResponse.model_validate(updated),
        message="Inventory quantity adjusted",
    )


@app.get(
    "/inventory/barcode/{barcode}",
    response_model=None
)
def get_inventory_item_by_barcode(
    barcode: str,
    db: Session = Depends(get_db),
):

    inventory_item = crud.get_inventory_item_by_barcode(db, barcode)

    if inventory_item is None:
        raise APIError(
            status_code=404,
            message="Inventory item not found for barcode",
            code=NOT_FOUND,
            details={"barcode": barcode},
        )

    return success_response(
        data=schemas.InventoryResponse.model_validate(inventory_item),
        message="OK",
    )


@app.get(
    "/inventory/{inventory_id}",
    response_model=None
)
def get_inventory_item(
    inventory_id: int,
    db: Session = Depends(get_db)
):

    inventory_item = crud.get_inventory_item(db, inventory_id)

    if inventory_item is None:
        raise APIError(
            status_code=404,
            message="Inventory item not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=inventory_item,
        message="OK",
    )


@app.put(
    "/inventory/{inventory_id}",
    response_model=None
)
def update_inventory_item(
    inventory_id: int,
    inventory_data: schemas.InventoryUpdate,
    db: Session = Depends(get_db)
):

    inventory_item = crud.update_inventory_item(
        db,
        inventory_id,
        inventory_data
    )

    if isinstance(inventory_item, dict) and inventory_item.get("barcode_conflict"):
        raise APIError(
            status_code=409,
            message="Inventory barcode already exists",
            code=CONFLICT,
        )

    if inventory_item is None:
        raise APIError(
            status_code=404,
            message="Inventory item not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=inventory_item,
        message="Inventory item updated",
    )


@app.delete("/inventory/{inventory_id}")
def delete_inventory_item(
    inventory_id: int,
    db: Session = Depends(get_db)
):

    deleted = crud.delete_inventory_item(db, inventory_id)

    if not deleted:
        raise APIError(
            status_code=404,
            message="Inventory item not found",
            code=NOT_FOUND,
        )

    return success_response(
        data={"id": inventory_id},
        message="Inventory item deleted successfully",
    )


@app.post(
    "/samples/",
    response_model=None,
    status_code=201
)
def create_sample(
    sample: schemas.SampleCreate,
    db: Session = Depends(get_db)
):

    created_sample = crud.create_sample(db, sample)

    if created_sample is None:
        raise APIError(
            status_code=404,
            message="Project not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=created_sample,
        message="Sample created",
    )


@app.get(
    "/samples/",
    response_model=None
)
def get_samples(
    pagination: PaginationParams = Depends(),
    statuses: Optional[list[str]] = Query(None),
    project_ids: Optional[list[int]] = Query(None),
    sample_types: Optional[list[str]] = Query(None),
    search: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    updated_from: Optional[datetime] = None,
    updated_to: Optional[datetime] = None,
    db: Session = Depends(get_db)
):

    query = db.query(models.Sample)

    if statuses:
        query = query.filter(models.Sample.status.in_(statuses))
    if project_ids:
        query = query.filter(models.Sample.project_id.in_(project_ids))
    if sample_types:
        query = query.filter(models.Sample.sample_type.in_(sample_types))
    if search:
        query = query.filter(
            models.Sample.name.contains(search) |
            models.Sample.description.contains(search)
        )
    if created_from:
        query = query.filter(models.Sample.created_at >= created_from)
    if created_to:
        query = query.filter(models.Sample.created_at <= created_to)
    if updated_from:
        query = query.filter(models.Sample.updated_at >= updated_from)
    if updated_to:
        query = query.filter(models.Sample.updated_at <= updated_to)

    items, total, page, pages, per_page = pagination.paginate(
        query,
        sortable_columns={"id", "name", "created_at", "updated_at",
                          "status", "sample_type", "project_id"},
    )

    return success_response(
        data=items,
        message="OK",
        total=total,
        pagination=pagination.pagination_block(total, page, pages, per_page),
    )


@app.get(
    "/samples/{sample_id}",
    response_model=None
)
def get_sample(
    sample_id: int,
    db: Session = Depends(get_db)
):

    sample = crud.get_sample(db, sample_id)

    if sample is None:
        raise APIError(
            status_code=404,
            message="Sample not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=sample,
        message="OK",
    )


@app.put(
    "/samples/{sample_id}",
    response_model=None
)
def update_sample(
    sample_id: int,
    sample_data: schemas.SampleUpdate,
    db: Session = Depends(get_db)
):

    sample = crud.update_sample(db, sample_id, sample_data)

    if sample is None:
        raise APIError(
            status_code=404,
            message="Sample not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=sample,
        message="Sample updated",
    )


@app.delete("/samples/{sample_id}")
def delete_sample(
    sample_id: int,
    db: Session = Depends(get_db)
):

    deleted = crud.delete_sample(db, sample_id)

    if not deleted:
        raise APIError(
            status_code=404,
            message="Sample not found",
            code=NOT_FOUND,
        )

    return success_response(
        data={"id": sample_id},
        message="Sample deleted successfully",
    )


@app.post(
    "/samples/{sample_id}/attachments/",
    response_model=None,
    status_code=201
)
def upload_sample_attachment(
    sample_id: int,
    kind: schemas.AttachmentKind = Form("image"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    filename, stored_path, content_type, size_bytes = _save_upload(
        file,
        "samples",
        str(sample_id),
    )

    attachment = crud.create_sample_attachment(
        db,
        sample_id=sample_id,
        filename=filename,
        stored_path=stored_path,
        content_type=content_type,
        size_bytes=size_bytes,
        kind=kind,
    )

    if attachment is None:
        _delete_stored_file(stored_path)
        raise APIError(
            status_code=404,
            message="Sample not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=_sample_attachment_payload(attachment),
        message="Sample attachment uploaded",
    )


@app.get(
    "/samples/{sample_id}/attachments/",
    response_model=None
)
def list_sample_attachments(
    sample_id: int,
    db: Session = Depends(get_db),
):

    attachments = crud.list_sample_attachments(db, sample_id)

    if attachments is None:
        raise APIError(
            status_code=404,
            message="Sample not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=[_sample_attachment_payload(item) for item in attachments],
        message="OK",
        total=len(attachments),
    )


@app.get(
    "/samples/{sample_id}/attachments/{attachment_id}",
    response_model=None
)
def get_sample_attachment(
    sample_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
):

    attachment = crud.get_sample_attachment(db, sample_id, attachment_id)

    if attachment is None:
        raise APIError(
            status_code=404,
            message="Sample attachment not found",
            code=NOT_FOUND,
        )

    return success_response(
        data=_sample_attachment_payload(attachment),
        message="OK",
    )


@app.get(
    "/samples/{sample_id}/attachments/{attachment_id}/download",
    response_model=None
)
def download_sample_attachment(
    sample_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
):

    attachment = crud.get_sample_attachment(db, sample_id, attachment_id)

    if attachment is None:
        raise APIError(
            status_code=404,
            message="Sample attachment not found",
            code=NOT_FOUND,
        )

    return _attachment_file_response(
        attachment,
        "Sample attachment file not found",
    )


@app.delete(
    "/samples/{sample_id}/attachments/{attachment_id}",
    response_model=None
)
def delete_sample_attachment(
    sample_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
):

    deleted = crud.delete_sample_attachment(db, sample_id, attachment_id)

    if deleted is None:
        raise APIError(
            status_code=404,
            message="Sample attachment not found",
            code=NOT_FOUND,
        )

    _delete_stored_file(deleted["stored_path"])

    return success_response(
        data={"id": attachment_id, "sample_id": sample_id},
        message="Sample attachment deleted successfully",
    )


# =============================================================================
# Bulk endpoints — atomic (single commit per call). All require auth; role
# policies vary per endpoint.
# =============================================================================


def _bulk_failed(status_code: int, message: str, code: str, details: dict):
    """Helper to raise a uniform APIError from a bulk CRUD failure."""
    raise APIError(
        status_code=status_code,
        message=message,
        code=code,
        details=details,
    )


@app.post(
    "/bulk/projects",
    response_model=None,
    status_code=201
)
def bulk_create_projects(
    payload: schemas.BulkProjectsCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("admin", "researcher")),
):

    created = crud.bulk_create_projects(db, payload.items)

    if created is None:
        _bulk_failed(409, "Bulk project create failed", CONFLICT, {})

    return success_response(
        data={
            "created": [p.id for p in created],
            "count": len(created),
        },
        message=f"{len(created)} projects created",
    )


@app.put(
    "/bulk/projects",
    response_model=None
)
def bulk_update_projects(
    payload: schemas.BulkProjectsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("admin", "researcher")),
):

    result = crud.bulk_update_projects(db, payload.items)

    if result is None:
        _bulk_failed(409, "Bulk project update failed", CONFLICT, {})
    if isinstance(result, dict) and "missing_ids" in result:
        _bulk_failed(
            404,
            "Some projects not found",
            NOT_FOUND,
            result,
        )

    return success_response(
        data={
            "updated": [p.id for p in result],
            "count": len(result),
        },
        message=f"{len(result)} projects updated",
    )


@app.delete(
    "/bulk/projects",
    response_model=None
)
def bulk_delete_projects(
    payload: schemas.BulkProjectsDelete,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("admin")),
):

    result = crud.bulk_delete_projects(db, payload.project_ids)

    if isinstance(result, dict) and "missing_ids" in result:
        _bulk_failed(
            404,
            "Some projects not found",
            NOT_FOUND,
            result,
        )
    if isinstance(result, dict) and "blocked_by" in result:
        _bulk_failed(
            409,
            "Projects blocked by existing tasks or samples",
            CONFLICT,
            result,
        )
    if result is None:
        _bulk_failed(409, "Bulk project delete failed", CONFLICT, {})

    return success_response(
        data={"deleted": result, "count": len(result)},
        message=f"{len(result)} projects deleted",
    )


@app.post(
    "/bulk/tasks/assign",
    response_model=None
)
def bulk_assign_tasks(
    payload: schemas.BulkTaskAssign,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("admin", "researcher")),
):

    result = crud.bulk_assign_tasks(db, payload.task_ids, payload.assignee_id)

    if isinstance(result, dict) and result.get("assignee_missing"):
        _bulk_failed(
            404,
            "Assignee not found or inactive",
            NOT_FOUND,
            {"assignee_id": payload.assignee_id},
        )
    if isinstance(result, dict) and "missing_ids" in result:
        _bulk_failed(
            404,
            "Some tasks not found",
            NOT_FOUND,
            result,
        )
    if result is None:
        _bulk_failed(409, "Bulk task assign failed", CONFLICT, {})

    return success_response(
        data=result,
        message=f"Assigned {result['count']} tasks",
    )


@app.post(
    "/bulk/inventory/quantities",
    response_model=None
)
def bulk_update_inventory_quantities(
    payload: schemas.BulkInventoryQuantities,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        auth.require_role("admin", "researcher", "technician")
    ),
):

    result = crud.bulk_update_inventory_quantities(db, payload.items)

    if isinstance(result, dict) and "missing_ids" in result:
        _bulk_failed(
            404,
            "Some inventory items not found",
            NOT_FOUND,
            result,
        )
    if isinstance(result, dict) and "would_go_negative" in result:
        _bulk_failed(
            422,
            "Some deltas would result in negative quantity",
            VALIDATION_ERROR,
            result,
        )
    if result is None:
        _bulk_failed(409, "Bulk inventory update failed", CONFLICT, {})

    return success_response(
        data={
            "updated": [row.id for row in result],
            "count": len(result),
        },
        message=f"{len(result)} inventory rows updated",
    )


@app.post(
    "/bulk/samples",
    response_model=None,
    status_code=201
)
def bulk_register_samples(
    payload: schemas.BulkSamplesCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("admin", "researcher")),
):

    result = crud.bulk_register_samples(db, payload.samples)

    if isinstance(result, dict) and "missing_project_ids" in result:
        _bulk_failed(
            404,
            "Some samples reference missing projects",
            NOT_FOUND,
            result,
        )
    if result is None:
        _bulk_failed(409, "Bulk sample create failed", CONFLICT, {})

    return success_response(
        data={
            "created": [s.id for s in result],
            "count": len(result),
        },
        message=f"{len(result)} samples registered",
    )
