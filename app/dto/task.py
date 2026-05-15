import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.dto.common import SortOrder, TaskSortField
from app.models.domain import TaskPriority, TaskStatus


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus = TaskStatus.pending
    priority: TaskPriority = TaskPriority.medium
    due_date: datetime | None = None
    tags: list[Any] | None = None
    assigned_user_id: uuid.UUID | None = None


class TaskCreate(TaskBase):
    project_id: uuid.UUID


class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None
    tags: list[Any] | None = None
    assigned_user_id: uuid.UUID | None = None


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TaskFilter(BaseModel):
    """Query-parameter DTO for GET /api/tasks.

    FastAPI binds each field from the query string when this is consumed
    via `Depends(TaskFilter)`. Keeps the route signature compact and the
    filter contract reusable.
    """

    model_config = ConfigDict(populate_by_name=True)

    project_id: uuid.UUID | None = None
    status: TaskStatus | None = Field(None, description="Task status filter")
    priority: TaskPriority | None = None
    assigned_user_id: uuid.UUID | None = None
    sort_by: TaskSortField = TaskSortField.created_at
    order: SortOrder = SortOrder.desc
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=500)
