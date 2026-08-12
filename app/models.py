from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )

    email = Column(
        String(200),
        unique=True,
        nullable=False,
        index=True
    )

    full_name = Column(String(200), nullable=True)

    hashed_password = Column(String(200), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    role = Column(String(50), default="researcher", nullable=False)

    created_at = Column(
        DateTime,
        default=_utcnow
    )

    projects = relationship(
        "Project",
        back_populates="owner",
        cascade="all, delete-orphan"
    )

    tasks_assigned = relationship(
        "Task",
        back_populates="assignee"
    )


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(
        String(200),
        nullable=False
    )

    description = Column(Text, nullable=True)

    status = Column(
        String(50),
        default="active"
    )

    priority = Column(
        String(50),
        default="medium"
    )

    created_at = Column(
        DateTime,
        default=_utcnow
    )

    updated_at = Column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow
    )

    owner_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    owner = relationship(
        "User",
        back_populates="projects"
    )

    tasks = relationship(
        "Task",
        back_populates="project",
        cascade="all, delete-orphan"
    )

    samples = relationship(
        "Sample",
        back_populates="project",
        cascade="all, delete-orphan"
    )

    attachments = relationship(
        "ProjectAttachment",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    priority = Column(String(50), default="medium")

    created_at = Column(
        DateTime,
        default=_utcnow
    )

    updated_at = Column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow
    )

    project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=False
    )

    project = relationship("Project", back_populates="tasks")

    assignee_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    assignee = relationship(
        "User",
        back_populates="tasks_assigned"
    )


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    unit = Column(String(50), nullable=False, default="unit")
    location = Column(String(200), nullable=False)
    supplier = Column(String(200), nullable=True)
    barcode = Column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=_utcnow
    )

    updated_at = Column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow
    )


class Sample(Base):
    __tablename__ = "samples"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    sample_type = Column(String(100), nullable=False)
    status = Column(String(50), default="available")
    storage_location = Column(String(200), nullable=False)

    created_at = Column(
        DateTime,
        default=_utcnow
    )

    updated_at = Column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow
    )

    project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=False
    )

    project = relationship("Project", back_populates="samples")

    attachments = relationship(
        "SampleAttachment",
        back_populates="sample",
        cascade="all, delete-orphan",
    )


class ProjectAttachment(Base):
    """File metadata for a document attached to a project.

    The bytes live on disk under ``UPLOAD_ROOT/projects/<project_id>/``;
    only the path, size, and original filename are stored here so the DB
    row stays small and portable.
    """

    __tablename__ = "project_attachments"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )
    filename = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(BigInteger, nullable=False, default=0)
    uploaded_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
    uploaded_at = Column(DateTime, default=_utcnow)

    project = relationship("Project", back_populates="attachments")


class SampleAttachment(Base):
    """File metadata for an image / dataset attached to a sample.

    Mirrors :class:`ProjectAttachment`; one sample can have many attachments
    (e.g. multiple images from different angles plus a dataset CSV).
    """

    __tablename__ = "sample_attachments"

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(
        Integer,
        ForeignKey("samples.id"),
        nullable=False,
        index=True,
    )
    filename = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(BigInteger, nullable=False, default=0)
    kind = Column(
        String(20),
        nullable=False,
        default="image",
    )  # "image" | "dataset" | "other"
    uploaded_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
    uploaded_at = Column(DateTime, default=_utcnow)

    sample = relationship("Sample", back_populates="attachments")