import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.dto.analytics import (
    ActiveProjectRead,
    AnalyticsResponse,
    UserProductivity,
)
from app.models.domain import TaskStatus
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository

RECENT_ACTIVITY_WINDOW_DAYS = 30
PRODUCTIVITY_WINDOW_DAYS = 7
MOST_ACTIVE_PROJECTS_LIMIT = 5


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.project_repo = ProjectRepository(session)
        self.task_repo = TaskRepository(session)

    async def get_overview(self, owner_id: uuid.UUID) -> AnalyticsResponse:
        now = datetime.now(timezone.utc)
        productivity_since = now - timedelta(days=PRODUCTIVITY_WINDOW_DAYS)
        activity_since = now - timedelta(days=RECENT_ACTIVITY_WINDOW_DAYS)

        tasks_by_status = await self.task_repo.count_by_status_for_owner(owner_id)
        total_tasks = sum(tasks_by_status.values())
        completed_tasks = tasks_by_status.get(TaskStatus.completed, 0)
        overdue_tasks = await self.task_repo.count_overdue_for_owner(owner_id)
        active_projects_count = await self.project_repo.count_active_for_owner(
            owner_id
        )

        completed_last_7 = await self.task_repo.count_completed_since(
            owner_id, productivity_since
        )
        avg_completion_days = await self.task_repo.avg_completion_days_for_owner(
            owner_id
        )
        completion_rate = (
            completed_tasks / total_tasks if total_tasks > 0 else 0.0
        )

        active_rows = await self.project_repo.most_active_for_owner(
            owner_id,
            since=activity_since,
            limit=MOST_ACTIVE_PROJECTS_LIMIT,
        )

        return AnalyticsResponse(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            overdue_tasks=overdue_tasks,
            tasks_by_status=tasks_by_status,
            active_projects_count=active_projects_count,
            user_productivity=UserProductivity(
                completion_rate=round(completion_rate, 4),
                completed_last_7_days=completed_last_7,
                average_completion_days=avg_completion_days,
            ),
            most_active_projects=[
                ActiveProjectRead(
                    id=project.id,
                    name=project.name,
                    recent_task_activity=count,
                )
                for project, count in active_rows
            ],
        )
