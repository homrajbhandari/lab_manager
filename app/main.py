from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import Base, engine, get_db


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Research Laboratory Management System",
    description="API for managing research laboratory resources.",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "Welcome to Research Laboratory Management System",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


@app.post(
    "/projects/",
    response_model=schemas.ProjectResponse,
    status_code=201
)
def create_project(
    project: schemas.ProjectCreate,
    db: Session = Depends(get_db)
):

    return crud.create_project(db, project)


@app.get(
    "/projects/",
    response_model=list[schemas.ProjectResponse]
)
def get_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):

    return crud.get_projects(
        db,
        skip=skip,
        limit=limit
    )


@app.get(
    "/projects/{project_id}",
    response_model=schemas.ProjectResponse
)
def get_project(
    project_id: int,
    db: Session = Depends(get_db)
):

    project = crud.get_project(
        db,
        project_id
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return project


@app.put(
    "/projects/{project_id}",
    response_model=schemas.ProjectResponse
)
def update_project(
    project_id: int,
    project_data: schemas.ProjectUpdate,
    db: Session = Depends(get_db)
):

    project = crud.update_project(
        db,
        project_id,
        project_data
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return project


@app.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db)
):

    deleted = crud.delete_project(
        db,
        project_id
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return {
        "message": "Project deleted successfully"
    }


@app.post(
    "/tasks/",
    response_model=schemas.TaskResponse,
    status_code=201
)
def create_task(
    task: schemas.TaskCreate,
    db: Session = Depends(get_db)
):

    created_task = crud.create_task(db, task)

    if created_task is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return created_task


@app.get(
    "/tasks/",
    response_model=list[schemas.TaskResponse]
)
def get_tasks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):

    return crud.get_tasks(db, skip=skip, limit=limit)


@app.get(
    "/tasks/{task_id}",
    response_model=schemas.TaskResponse
)
def get_task(
    task_id: int,
    db: Session = Depends(get_db)
):

    task = crud.get_task(db, task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    return task


@app.put(
    "/tasks/{task_id}",
    response_model=schemas.TaskResponse
)
def update_task(
    task_id: int,
    task_data: schemas.TaskUpdate,
    db: Session = Depends(get_db)
):

    task = crud.update_task(db, task_id, task_data)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    return task


@app.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db)
):

    deleted = crud.delete_task(db, task_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    return {
        "message": "Task deleted successfully"
    }


@app.post(
    "/inventory/",
    response_model=schemas.InventoryResponse,
    status_code=201
)
def create_inventory_item(
    inventory_item: schemas.InventoryCreate,
    db: Session = Depends(get_db)
):

    return crud.create_inventory_item(db, inventory_item)


@app.get(
    "/inventory/",
    response_model=list[schemas.InventoryResponse]
)
def get_inventory(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):

    return crud.get_inventory(db, skip=skip, limit=limit)


@app.get(
    "/inventory/{inventory_id}",
    response_model=schemas.InventoryResponse
)
def get_inventory_item(
    inventory_id: int,
    db: Session = Depends(get_db)
):

    inventory_item = crud.get_inventory_item(db, inventory_id)

    if inventory_item is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory item not found"
        )

    return inventory_item


@app.put(
    "/inventory/{inventory_id}",
    response_model=schemas.InventoryResponse
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
        raise HTTPException(
            status_code=404,
            detail="Inventory item not found"
        )

    return inventory_item


@app.delete("/inventory/{inventory_id}")
def delete_inventory_item(
    inventory_id: int,
    db: Session = Depends(get_db)
):

    deleted = crud.delete_inventory_item(db, inventory_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Inventory item not found"
        )

    return {
        "message": "Inventory item deleted successfully"
    }


@app.post(
    "/samples/",
    response_model=schemas.SampleResponse,
    status_code=201
)
def create_sample(
    sample: schemas.SampleCreate,
    db: Session = Depends(get_db)
):

    created_sample = crud.create_sample(db, sample)

    if created_sample is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return created_sample


@app.get(
    "/samples/",
    response_model=list[schemas.SampleResponse]
)
def get_samples(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):

    return crud.get_samples(db, skip=skip, limit=limit)


@app.get(
    "/samples/{sample_id}",
    response_model=schemas.SampleResponse
)
def get_sample(
    sample_id: int,
    db: Session = Depends(get_db)
):

    sample = crud.get_sample(db, sample_id)

    if sample is None:
        raise HTTPException(
            status_code=404,
            detail="Sample not found"
        )

    return sample


@app.put(
    "/samples/{sample_id}",
    response_model=schemas.SampleResponse
)
def update_sample(
    sample_id: int,
    sample_data: schemas.SampleUpdate,
    db: Session = Depends(get_db)
):

    sample = crud.update_sample(db, sample_id, sample_data)

    if sample is None:
        raise HTTPException(
            status_code=404,
            detail="Sample not found"
        )

    return sample


@app.delete("/samples/{sample_id}")
def delete_sample(
    sample_id: int,
    db: Session = Depends(get_db)
):

    deleted = crud.delete_sample(db, sample_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Sample not found"
        )

    return {
        "message": "Sample deleted successfully"
    }