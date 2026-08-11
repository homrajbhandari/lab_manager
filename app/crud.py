from datetime import datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas


def get_user(
    db: Session,
    user_id: int
) -> Optional[models.User]:

    return (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .first()
    )


def get_user_by_username(
    db: Session,
    username: str
) -> Optional[models.User]:

    return (
        db.query(models.User)
        .filter(models.User.username == username)
        .first()
    )


def get_user_by_email(
    db: Session,
    email: str
) -> Optional[models.User]:

    return (
        db.query(models.User)
        .filter(models.User.email == email)
        .first()
    )


def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 100
):

    return (
        db.query(models.User)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_user(
    db: Session,
    user: schemas.UserCreate
):

    db_user = models.User(
        username=user.username,
        email=user.email,
        full_name=user.full_name
    )

    db.add(db_user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None

    db.refresh(db_user)

    return db_user


def update_user(
    db: Session,
    user_id: int,
    user_data: schemas.UserUpdate
):

    db_user = get_user(db, user_id)

    if db_user is None:
        return None

    update_data = user_data.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():
        setattr(db_user, key, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None

    db.refresh(db_user)

    return db_user


def delete_user(
    db: Session,
    user_id: int
):

    db_user = get_user(db, user_id)

    if db_user is None:
        return False

    db.delete(db_user)
    db.commit()

    return True


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
        status=project.status,
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


def get_task(
    db: Session,
    task_id: int
) -> Optional[models.Task]:

    return (
        db.query(models.Task)
        .filter(models.Task.id == task_id)
        .first()
    )


def get_tasks(
    db: Session,
    skip: int = 0,
    limit: int = 100
):

    return (
        db.query(models.Task)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_task(
    db: Session,
    task: schemas.TaskCreate
):

    project = get_project(db, task.project_id)

    if project is None:
        return None

    db_task = models.Task(
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        project_id=task.project_id
    )

    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return db_task


def update_task(
    db: Session,
    task_id: int,
    task_data: schemas.TaskUpdate
):

    db_task = get_task(db, task_id)

    if db_task is None:
        return None

    if task_data.project_id is not None:
        project = get_project(db, task_data.project_id)

        if project is None:
            return None

    update_data = task_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_task, key, value)

    db_task.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_task)

    return db_task


def delete_task(
    db: Session,
    task_id: int
):

    db_task = get_task(db, task_id)

    if db_task is None:
        return False

    db.delete(db_task)
    db.commit()

    return True


def get_inventory_item(
    db: Session,
    inventory_id: int
) -> Optional[models.Inventory]:

    return (
        db.query(models.Inventory)
        .filter(models.Inventory.id == inventory_id)
        .first()
    )


def get_inventory(
    db: Session,
    skip: int = 0,
    limit: int = 100
):

    return (
        db.query(models.Inventory)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_inventory_item(
    db: Session,
    inventory_item: schemas.InventoryCreate
):

    db_inventory_item = models.Inventory(
        name=inventory_item.name,
        description=inventory_item.description,
        category=inventory_item.category,
        quantity=inventory_item.quantity,
        unit=inventory_item.unit,
        location=inventory_item.location,
        supplier=inventory_item.supplier
    )

    db.add(db_inventory_item)
    db.commit()
    db.refresh(db_inventory_item)

    return db_inventory_item


def update_inventory_item(
    db: Session,
    inventory_id: int,
    inventory_data: schemas.InventoryUpdate
):

    db_inventory_item = get_inventory_item(db, inventory_id)

    if db_inventory_item is None:
        return None

    update_data = inventory_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_inventory_item, key, value)

    db_inventory_item.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_inventory_item)

    return db_inventory_item


def delete_inventory_item(
    db: Session,
    inventory_id: int
):

    db_inventory_item = get_inventory_item(db, inventory_id)

    if db_inventory_item is None:
        return False

    db.delete(db_inventory_item)
    db.commit()

    return True


def get_sample(
    db: Session,
    sample_id: int
) -> Optional[models.Sample]:

    return (
        db.query(models.Sample)
        .filter(models.Sample.id == sample_id)
        .first()
    )


def get_samples(
    db: Session,
    skip: int = 0,
    limit: int = 100
):

    return (
        db.query(models.Sample)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_sample(
    db: Session,
    sample: schemas.SampleCreate
):

    project = get_project(db, sample.project_id)

    if project is None:
        return None

    db_sample = models.Sample(
        name=sample.name,
        description=sample.description,
        sample_type=sample.sample_type,
        status=sample.status,
        storage_location=sample.storage_location,
        project_id=sample.project_id
    )

    db.add(db_sample)
    db.commit()
    db.refresh(db_sample)

    return db_sample


def update_sample(
    db: Session,
    sample_id: int,
    sample_data: schemas.SampleUpdate
):

    db_sample = get_sample(db, sample_id)

    if db_sample is None:
        return None

    if sample_data.project_id is not None:
        project = get_project(db, sample_data.project_id)

        if project is None:
            return None

    update_data = sample_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_sample, key, value)

    db_sample.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_sample)

    return db_sample


def delete_sample(
    db: Session,
    sample_id: int
):

    db_sample = get_sample(db, sample_id)

    if db_sample is None:
        return False

    db.delete(db_sample)
    db.commit()

    return True