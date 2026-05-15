import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, or_, select

from app.dto.common import SortOrder, TaskSortField
from app.models.domain import Project, Task, TaskPriority, TaskStatus
from app.repositories.base import BaseRepository

_TASK_SORT_COLUMNS = {
    TaskSortField.created_at: Task.created_at,
    TaskSortField.updated_at: Task.updated_at,
    TaskSortField.due_date: Task.due_date,
    TaskSortField.priority: Task.priority,
    TaskSortField.status: Task.status,
    TaskSortField.title: Task.title,
}


class TaskRepository(BaseRepository[Task]):
    model = Task

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 100
    ) -> Sequence[Task]:
        stmt = (
            select(Task)
            .where(
                Task.project_id == project_id,
                Task.is_deleted.is_(False),
            )
            .order_by(Task.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def filter_tasks(
        self,
        *,
        project_id: uuid.UUID | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assigned_user_id: uuid.UUID | None = None,
        visible_to_user_id: uuid.UUID | None = None,
        sort_by: TaskSortField = TaskSortField.created_at,
        order: SortOrder = SortOrder.desc,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Task]:
        """Dynamic-WHERE task search.

        Each filter parameter is only appended when explicitly provided.
        `visible_to_user_id`, when set, restricts results to tasks the user
        can see: tasks assigned to them OR tasks inside a project they own.
        """
        stmt = select(Task).where(Task.is_deleted.is_(False))

        if visible_to_user_id is not None:
            owned_projects_subq = (
                select(Project.id)
                .where(
                    Project.owner_id == visible_to_user_id,
                    Project.is_deleted.is_(False),
                )
                .scalar_subquery()
            )
            stmt = stmt.where(
                or_(
                    Task.assigned_user_id == visible_to_user_id,
                    Task.project_id.in_(owned_projects_subq),
                )
            )

        if project_id is not None:
            stmt = stmt.where(Task.project_id == project_id)
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)
        if assigned_user_id is not None:
            stmt = stmt.where(Task.assigned_user_id == assigned_user_id)

        sort_column = _TASK_SORT_COLUMNS[sort_by]
        sort_expr = sort_column.desc() if order == SortOrder.desc else sort_column.asc()
        stmt = stmt.order_by(sort_expr).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    def _scoped_to_owner(self, owner_id: uuid.UUID):
        """Tasks belonging to projects owned by `owner_id` and not deleted."""
        return (
            select(Task)
            .join(Project, Project.id == Task.project_id)
            .where(
                Task.is_deleted.is_(False),
                Project.is_deleted.is_(False),
                Project.owner_id == owner_id,
            )
        )

    async def count_for_owner(self, owner_id: uuid.UUID) -> int:
        base = self._scoped_to_owner(owner_id).subquery()
        stmt = select(func.count()).select_from(base)
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_by_status_for_owner(
        self, owner_id: uuid.UUID
    ) -> dict[TaskStatus, int]:
        stmt = (
            select(Task.status, func.count(Task.id))
            .join(Project, Project.id == Task.project_id)
            .where(
                Task.is_deleted.is_(False),
                Project.is_deleted.is_(False),
                Project.owner_id == owner_id,
            )
            .group_by(Task.status)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        counts: dict[TaskStatus, int] = {s: 0 for s in TaskStatus}
        for status_value, count in rows:
            counts[status_value] = int(count)
        return counts

    async def count_completed_since(
        self, owner_id: uuid.UUID, since: datetime
    ) -> int:
        stmt = (
            select(func.count(Task.id))
            .join(Project, Project.id == Task.project_id)
            .where(
                Task.is_deleted.is_(False),
                Project.is_deleted.is_(False),
                Project.owner_id == owner_id,
                Task.status == TaskStatus.completed,
                Task.updated_at >= since,
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def avg_completion_days_for_owner(
        self, owner_id: uuid.UUID
    ) -> float | None:
        """Mean days between Task.created_at and Task.updated_at for completed tasks."""
        seconds_expr = func.avg(
            func.extract("epoch", Task.updated_at - Task.created_at)
        )
        stmt = (
            select(seconds_expr)
            .join(Project, Project.id == Task.project_id)
            .where(
                Task.is_deleted.is_(False),
                Project.is_deleted.is_(False),
                Project.owner_id == owner_id,
                Task.status == TaskStatus.completed,
            )
        )
        result = await self.session.execute(stmt)
        seconds = result.scalar_one_or_none()
        if seconds is None:
            return None
        return round(float(seconds) / 86400.0, 2)

    async def count_overdue_for_owner(self, owner_id: uuid.UUID) -> int:
        now = datetime.now(timezone.utc)
        stmt = (
            select(func.count(Task.id))
            .join(Project, Project.id == Task.project_id)
            .where(
                Task.is_deleted.is_(False),
                Project.is_deleted.is_(False),
                Project.owner_id == owner_id,
                Task.due_date.is_not(None),
                Task.due_date < now,
                Task.status != TaskStatus.completed,
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)
