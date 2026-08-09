from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models, schemas


def get_project(
    db: Session,
    project_id: int
) -> Optional[models.Project]:

    return (
        db.query(models.Project)
        .filter(models.Project.id == project_id)
        .first()
    )


def get_projects(
    db: Session,
    skip: int = 0,
    limit: int = 100
):

    return (
        db.query(models.Project)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_project(
    db: Session,
    project: schemas.ProjectCreate
):

    db_project = models.Project(
        title=project.title,
        description=project.description,
        priority=project.priority
    )

    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    return db_project


def update_project(
    db: Session,
    project_id: int,
    project_data: schemas.ProjectUpdate
):

    db_project = get_project(db, project_id)

    if db_project is None:
        return None

    update_data = project_data.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():
        setattr(db_project, key, value)

    db_project.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_project)

    return db_project


def delete_project(
    db: Session,
    project_id: int
):

    db_project = get_project(db, project_id)

    if db_project is None:
        return False

    db.delete(db_project)
    db.commit()

    return True