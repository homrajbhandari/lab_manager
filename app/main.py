from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import auth, crud, models, schemas
from app.database import Base, engine, get_db
from app.dependencies import PaginationParams
from app.migrations import (
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


app = FastAPI(
    title="Research Laboratory Management System",
    description="API for managing research laboratory resources.",
    version="1.0.0"
)


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
def health_check():
    return success_response(
        data={"status": "healthy"},
        message="Service is healthy",
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
            models.Inventory.supplier.contains(search)
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
