from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProjectBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    owner_id: Optional[int]

    class Config:
        from_attributes = True