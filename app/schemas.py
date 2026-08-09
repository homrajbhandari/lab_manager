from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    status: str = Field(default="active", min_length=1, max_length=50)
    priority: str = Field(default="medium", min_length=1, max_length=50)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(default=None, min_length=1, max_length=50)
    priority: Optional[str] = Field(default=None, min_length=1, max_length=50)


class ProjectResponse(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime
    owner_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    status: str = Field(default="pending", min_length=1, max_length=50)
    priority: str = Field(default="medium", min_length=1, max_length=50)
    project_id: int


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(default=None, min_length=1, max_length=50)
    priority: Optional[str] = Field(default=None, min_length=1, max_length=50)
    project_id: Optional[int] = None


class TaskResponse(TaskBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(default=0, ge=0)
    unit: str = Field(default="unit", min_length=1, max_length=50)
    location: str = Field(..., min_length=1, max_length=200)
    supplier: Optional[str] = None


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


class InventoryResponse(InventoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SampleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    sample_type: str = Field(..., min_length=1, max_length=100)
    status: str = Field(default="available", min_length=1, max_length=50)
    storage_location: str = Field(..., min_length=1, max_length=200)
    project_id: int


class SampleCreate(SampleBase):
    pass


class SampleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    sample_type: Optional[str] = Field(default=None, min_length=1, max_length=100)
    status: Optional[str] = Field(default=None, min_length=1, max_length=50)
    storage_location: Optional[str] = Field(default=None, min_length=1, max_length=200)
    project_id: Optional[int] = None


class SampleResponse(SampleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)