import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import func, select

from app.dto.common import ProjectSortField, SortOrder
from app.models.domain import Project, Task
from app.repositories.base import BaseRepository

_PROJECT_SORT_COLUMNS = {
    ProjectSortField.created_at: Project.created_at,
    ProjectSortField.updated_at: Project.updated_at,
    ProjectSortField.name: Project.name,
}


class ProjectRepository(BaseRepository[Project]):
    model = Project

    async def list_by_owner(
        self,
        owner_id: uuid.UUID,
        *,
        sort_by: ProjectSortField = ProjectSortField.created_at,
        order: SortOrder = SortOrder.desc,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Project]:
        sort_column = _PROJECT_SORT_COLUMNS[sort_by]
        sort_expr = (
            sort_column.desc() if order == SortOrder.desc else sort_column.asc()
        )
        stmt = (
            select(Project)
            .where(
                Project.owner_id == owner_id,
                Project.is_deleted.is_(False),
            )
            .order_by(sort_expr)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_active_for_owner(self, owner_id: uuid.UUID) -> int:
        stmt = select(func.count(Project.id)).where(
            Project.owner_id == owner_id,
            Project.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def most_active_for_owner(
        self,
        owner_id: uuid.UUID,
        *,
        since: datetime,
        limit: int = 5,
    ) -> list[tuple[Project, int]]:
        """Top N projects for an owner ranked by recent task activity.

        Activity = count of non-deleted tasks whose updated_at >= `since`.
        Projects with zero activity are still included so the response is
        deterministic; ordering breaks ties by project creation time.
        """
        activity = (
            func.count(Task.id)
            .filter(Task.updated_at >= since, Task.is_deleted.is_(False))
            .label("activity")
        )
        stmt = (
            select(Project, activity)
            .outerjoin(Task, Task.project_id == Project.id)
            .where(
                Project.owner_id == owner_id,
                Project.is_deleted.is_(False),
            )
            .group_by(Project.id)
            .order_by(activity.desc(), Project.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(row[0], int(row[1] or 0)) for row in result.all()]
