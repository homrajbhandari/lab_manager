from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
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