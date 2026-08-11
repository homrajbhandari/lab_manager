from typing import Optional

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import auth, crud, models, schemas
from app.database import Base, engine, get_db
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
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):

    items = crud.get_users(db, skip=skip, limit=limit)
    total = db.query(models.User).count()
    return success_response(
        data=[schemas.UserResponse.model_validate(u) for u in items],
        message="OK",
        total=total,
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
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):

    items, total = crud.get_projects_filtered(
        db, skip, limit, status, priority, search
    )
    return success_response(
        data=items,
        message="OK",
        total=total,
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
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):

    items = crud.get_tasks(db, skip=skip, limit=limit)
    total = db.query(models.Task).count()
    return success_response(
        data=items,
        message="OK",
        total=total,
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
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):

    items = crud.get_inventory(db, skip=skip, limit=limit)
    total = db.query(models.Inventory).count()
    return success_response(
        data=items,
        message="OK",
        total=total,
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
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):

    items = crud.get_samples(db, skip=skip, limit=limit)
    total = db.query(models.Sample).count()
    return success_response(
        data=items,
        message="OK",
        total=total,
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
