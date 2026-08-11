from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.security import get_password_hash


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


def get_users_filtered(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    roles: Optional[list[str]] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
):

    from app.dependencies import apply_sort

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

    apply_sort(
        query,
        model=models.User,
        sort_by=sort_by,
        sort_order=sort_order,
        sortable={"id", "username", "email", "role", "created_at"},
    )

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return items, total


def create_user(
    db: Session,
    user: schemas.UserCreate
):

    db_user = models.User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=get_password_hash(user.password),
        role=user.role
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

    password = update_data.pop("password", None)

    for key, value in update_data.items():
        setattr(db_user, key, value)

    if password is not None:
        db_user.hashed_password = get_password_hash(password)

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


def get_projects_filtered(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    statuses: Optional[list[str]] = None,
    priorities: Optional[list[str]] = None,
    search: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    updated_from: Optional[datetime] = None,
    updated_to: Optional[datetime] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
):

    from app.dependencies import apply_sort

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

    apply_sort(
        query,
        model=models.Project,
        sort_by=sort_by,
        sort_order=sort_order,
        sortable={"id", "title", "created_at", "updated_at", "priority", "status"},
    )

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return items, total


def create_project(
    db: Session,
    project: schemas.ProjectCreate
):

    db_project = models.Project(
        title=project.title,
        description=project.description,
        status=project.status,
        priority=project.priority,
        owner_id=project.owner_id
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

    db_project.updated_at = datetime.now(timezone.utc)

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


def get_tasks_filtered(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    statuses: Optional[list[str]] = None,
    priorities: Optional[list[str]] = None,
    project_ids: Optional[list[int]] = None,
    assignee_ids: Optional[list[int]] = None,
    search: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    updated_from: Optional[datetime] = None,
    updated_to: Optional[datetime] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
):

    from app.dependencies import apply_sort

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

    apply_sort(
        query,
        model=models.Task,
        sort_by=sort_by,
        sort_order=sort_order,
        sortable={"id", "title", "created_at", "updated_at",
                 "priority", "status", "project_id", "assignee_id"},
    )

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return items, total


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

    db_task.updated_at = datetime.now(timezone.utc)

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


def get_inventory_filtered(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    categories: Optional[list[str]] = None,
    locations: Optional[list[str]] = None,
    suppliers: Optional[list[str]] = None,
    search: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    updated_from: Optional[datetime] = None,
    updated_to: Optional[datetime] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
):

    from app.dependencies import apply_sort

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

    apply_sort(
        query,
        model=models.Inventory,
        sort_by=sort_by,
        sort_order=sort_order,
        sortable={"id", "name", "quantity", "created_at",
                 "updated_at", "category", "location"},
    )

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return items, total


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

    db_inventory_item.updated_at = datetime.now(timezone.utc)

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


def get_samples_filtered(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    statuses: Optional[list[str]] = None,
    project_ids: Optional[list[int]] = None,
    sample_types: Optional[list[str]] = None,
    search: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    updated_from: Optional[datetime] = None,
    updated_to: Optional[datetime] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
):

    from app.dependencies import apply_sort

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

    apply_sort(
        query,
        model=models.Sample,
        sort_by=sort_by,
        sort_order=sort_order,
        sortable={"id", "name", "created_at", "updated_at",
                 "status", "sample_type", "project_id"},
    )

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return items, total


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

    db_sample.updated_at = datetime.now(timezone.utc)

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


# =============================================================================
# Bulk helpers — atomic (one commit per call; any failure rolls back the batch).
# On failure the caller receives ``None`` so the route layer can map to an
# APIError with the original exception's message/details attached.
# =============================================================================


def bulk_create_projects(
    db: Session,
    items: list[schemas.ProjectCreate],
):
    """Insert many projects in one transaction. Returns the list of created
    Project rows, or None on any failure."""

    for item in items:
        if item.owner_id is not None and get_user(db, item.owner_id) is None:
            return None

    db_projects = [
        models.Project(
            title=item.title,
            description=item.description,
            status=item.status,
            priority=item.priority,
            owner_id=item.owner_id,
        )
        for item in items
    ]

    db.add_all(db_projects)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None

    for p in db_projects:
        db.refresh(p)

    return db_projects


def bulk_update_projects(
    db: Session,
    items: list,  # list[BulkProjectUpdateItem]
):
    """Apply partial updates to many projects in one transaction. Returns the
    updated rows, or None on any failure (including missing id)."""

    missing: list[int] = []

    rows_by_id: dict[int, models.Project] = {}
    for item in items:
        row = get_project(db, item.id)
        if row is None:
            missing.append(item.id)
            continue
        rows_by_id[item.id] = row

    if missing:
        # Bail out before any mutations so the transaction stays clean.
        db.rollback()
        return {"missing_ids": missing}

    update_fields = {"title", "description", "status", "priority"}

    for item in items:
        row = rows_by_id[item.id]
        payload = item.model_dump(exclude={"id"}, exclude_unset=True)
        for key, value in payload.items():
            if key in update_fields:
                setattr(row, key, value)
        row.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None

    for row in rows_by_id.values():
        db.refresh(row)

    return list(rows_by_id.values())


def bulk_delete_projects(
    db: Session,
    project_ids: list[int],
):
    """Delete many projects atomically. Returns the list of deleted ids, or
    None on any failure (missing ids, FK-blocked)."""

    rows = (
        db.query(models.Project)
        .filter(models.Project.id.in_(project_ids))
        .all()
    )

    found_ids = {row.id for row in rows}
    missing = [pid for pid in project_ids if pid not in found_ids]
    if missing:
        db.rollback()
        return {"missing_ids": missing}

    blocked_tasks = (
        db.query(models.Task.project_id)
        .filter(models.Task.project_id.in_(project_ids))
        .distinct()
        .all()
    )
    blocked_samples = (
        db.query(models.Sample.project_id)
        .filter(models.Sample.project_id.in_(project_ids))
        .distinct()
        .all()
    )

    blocked_task_ids = {pid for (pid,) in blocked_tasks}
    blocked_sample_ids = {pid for (pid,) in blocked_samples}

    if blocked_task_ids or blocked_sample_ids:
        db.rollback()
        return {
            "blocked_by": {
                "tasks": sorted(blocked_task_ids),
                "samples": sorted(blocked_sample_ids),
            }
        }

    for row in rows:
        db.delete(row)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None

    return list(found_ids)


def bulk_assign_tasks(
    db: Session,
    task_ids: list[int],
    assignee_id: int,
):
    """Set ``assignee_id`` on many tasks in one statement. Returns a summary
    dict, or None on any failure."""

    assignee = get_user(db, assignee_id)
    if assignee is None or not assignee.is_active:
        return {"assignee_missing": True}

    rows = (
        db.query(models.Task)
        .filter(models.Task.id.in_(task_ids))
        .all()
    )
    found_ids = {row.id for row in rows}
    missing = [tid for tid in task_ids if tid not in found_ids]
    if missing:
        db.rollback()
        return {"missing_ids": missing}

    try:
        db.query(models.Task).filter(
            models.Task.id.in_(task_ids)
        ).update(
            {"assignee_id": assignee_id},
            synchronize_session="fetch",
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return None

    return {
        "assigned_to": assignee_id,
        "task_ids": task_ids,
        "count": len(task_ids),
    }


def bulk_update_inventory_quantities(
    db: Session,
    items: list,  # list[BulkInventoryQuantityItem]
):
    """Apply signed deltas to inventory quantities atomically. Returns the
    updated rows, or None on any failure (missing id, would-go-negative)."""

    ids = [item.id for item in items]
    rows = (
        db.query(models.Inventory)
        .filter(models.Inventory.id.in_(ids))
        .all()
    )
    found_ids = {row.id for row in rows}
    missing = [i for i in ids if i not in found_ids]
    if missing:
        db.rollback()
        return {"missing_ids": sorted(set(missing))}

    rows_by_id = {row.id: row for row in rows}

    for item in items:
        row = rows_by_id[item.id]
        if row.quantity + item.delta < 0:
            db.rollback()
            return {
                "would_go_negative": [
                    {"id": item.id, "current": row.quantity, "delta": item.delta}
                ]
            }
        row.quantity = row.quantity + item.delta
        row.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None

    for row in rows:
        db.refresh(row)

    return list(rows)


def bulk_register_samples(
    db: Session,
    items: list[schemas.SampleCreate],
):
    """Create many samples in one transaction. Returns the created rows, or
    None on any failure (missing project)."""

    for item in items:
        if get_project(db, item.project_id) is None:
            return {"missing_project_ids": [item.project_id]}

    db_samples = [
        models.Sample(
            name=item.name,
            description=item.description,
            sample_type=item.sample_type,
            status=item.status,
            storage_location=item.storage_location,
            project_id=item.project_id,
        )
        for item in items
    ]

    db.add_all(db_samples)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None

    for s in db_samples:
        db.refresh(s)

    return db_samples