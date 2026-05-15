import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.domain import TaskStatus


class UserProductivity(BaseModel):
    completion_rate: float = Field(..., ge=0.0, le=1.0)
    completed_last_7_days: int = Field(..., ge=0)
    average_completion_days: float | None = Field(None, ge=0.0)


class ActiveProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    recent_task_activity: int = Field(..., ge=0)


class AnalyticsResponse(BaseModel):
    total_tasks: int = Field(..., ge=0)
    completed_tasks: int = Field(..., ge=0)
    overdue_tasks: int = Field(..., ge=0)
    tasks_by_status: dict[TaskStatus, int]
    active_projects_count: int = Field(..., ge=0)
    user_productivity: UserProductivity
    most_active_projects: list[ActiveProjectRead]
