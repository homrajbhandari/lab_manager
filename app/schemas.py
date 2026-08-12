from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Vocabularies -------------------------------------------------------------

# Roles used by the auth layer. Kept as a Literal so pydantic rejects
# anything else before it reaches the DB.
UserRole = Literal["admin", "researcher", "technician"]

# Status and priority vocabularies. Applied ONLY on *Create / *Update schemas
# so existing rows with non-conforming values continue to serialize cleanly
# through the loose *Response schemas.
ProjectStatus = Literal["active", "completed", "archived", "on_hold"]
TaskStatus = Literal["pending", "in_progress", "completed", "blocked"]
Priority = Literal["low", "medium", "high", "critical"]
SampleStatus = Literal["available", "reserved", "consumed", "disposed"]
AttachmentKind = Literal["image", "dataset", "other"]
ImportExportResource = Literal["projects", "tasks", "inventory", "samples"]
ImportExportFormat = Literal["csv", "xlsx"]


# --- User schemas -------------------------------------------------------------


class UserBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    full_name: Optional[str] = Field(default=None, max_length=200)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=200)
    role: UserRole = "researcher"


class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=200)
    password: Optional[str] = Field(default=None, min_length=8, max_length=200)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    role: UserRole
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Project schemas ----------------------------------------------------------


class ProjectBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    # Status / priority are typed loosely here so ProjectResponse (which
    # inherits from ProjectBase) keeps accepting any string previously stored.
    status: str = Field(default="active", min_length=1, max_length=50)
    priority: str = Field(default="medium", min_length=1, max_length=50)


class ProjectCreate(ProjectBase):
    # Override the loose Base fields with strict Literal types for input
    # validation only. Defaults stay valid Literal members.
    status: ProjectStatus = "active"
    priority: Priority = "medium"
    owner_id: Optional[int] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[Priority] = None


class ProjectResponse(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime
    owner_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# --- Task schemas -------------------------------------------------------------


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    status: str = Field(default="pending", min_length=1, max_length=50)
    priority: str = Field(default="medium", min_length=1, max_length=50)
    project_id: int


class TaskCreate(TaskBase):
    status: TaskStatus = "pending"
    priority: Priority = "medium"


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[Priority] = None
    project_id: Optional[int] = None


class TaskResponse(TaskBase):
    id: int
    assignee_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Inventory schemas --------------------------------------------------------


class InventoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(default=0, ge=0)
    unit: str = Field(default="unit", min_length=1, max_length=50)
    location: str = Field(..., min_length=1, max_length=200)
    supplier: Optional[str] = None
    barcode: Optional[str] = Field(default=None, min_length=1, max_length=100)


class InventoryCreate(InventoryBase):
    pass


class InventoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    quantity: Optional[int] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, min_length=1, max_length=50)
    location: Optional[str] = Field(default=None, min_length=1, max_length=200)
    supplier: Optional[str] = None
    barcode: Optional[str] = Field(default=None, min_length=1, max_length=100)


class InventoryResponse(InventoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Sample schemas -----------------------------------------------------------


class SampleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    sample_type: str = Field(..., min_length=1, max_length=100)
    status: str = Field(default="available", min_length=1, max_length=50)
    storage_location: str = Field(..., min_length=1, max_length=200)
    project_id: int


class SampleCreate(SampleBase):
    status: SampleStatus = "available"


class SampleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    sample_type: Optional[str] = Field(default=None, min_length=1, max_length=100)
    status: Optional[SampleStatus] = None
    storage_location: Optional[str] = Field(default=None, min_length=1, max_length=200)
    project_id: Optional[int] = None


class SampleResponse(SampleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Attachment schemas ------------------------------------------------------


class ProjectAttachmentResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    content_type: Optional[str] = None
    size_bytes: int
    uploaded_by: Optional[int] = None
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SampleAttachmentResponse(BaseModel):
    id: int
    sample_id: int
    filename: str
    content_type: Optional[str] = None
    size_bytes: int
    kind: AttachmentKind
    uploaded_by: Optional[int] = None
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Barcode schemas ---------------------------------------------------------


class BarcodeScanRequest(BaseModel):
    barcode: str = Field(..., min_length=1, max_length=100)


class InventoryQuantityAdjustment(BaseModel):
    delta: int


class InventoryBarcodeQuantityAdjustment(BarcodeScanRequest):
    delta: int


# --- Bulk input schemas -------------------------------------------------------
# All bulk inputs use extra="forbid" so client typos are loud. Lists cap at
# 100 items to keep response size and DB load bounded.

BULK_MAX = 100


class BulkProjectsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ProjectCreate] = Field(..., min_length=1, max_length=BULK_MAX)


class BulkProjectUpdateItem(BaseModel):
    """One item in a bulk-update request: must include id plus any subset of
    ProjectUpdate fields."""

    model_config = ConfigDict(extra="forbid")
    id: int
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[Priority] = None


class BulkProjectsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[BulkProjectUpdateItem] = Field(
        ..., min_length=1, max_length=BULK_MAX
    )


class BulkProjectsDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_ids: list[int] = Field(..., min_length=1, max_length=BULK_MAX)


class BulkTaskAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_ids: list[int] = Field(..., min_length=1, max_length=BULK_MAX)
    assignee_id: int


class BulkInventoryQuantityItem(BaseModel):
    """Per-row quantity delta. ``delta`` is signed: positive to add stock,
    negative to consume."""

    model_config = ConfigDict(extra="forbid")
    id: int
    delta: int


class BulkInventoryQuantities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[BulkInventoryQuantityItem] = Field(
        ..., min_length=1, max_length=BULK_MAX
    )


class BulkSamplesCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    samples: list[SampleCreate] = Field(
        ..., min_length=1, max_length=BULK_MAX
    )
