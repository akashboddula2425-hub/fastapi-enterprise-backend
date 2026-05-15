import uuid
from typing import Sequence

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dto.common import ProjectSortField, SortOrder
from app.dto.project import ProjectCreate, ProjectUpdate
from app.models.domain import Project
from app.repositories.project_repository import ProjectRepository
from app.services.activity_service import activity_service

TARGET_ENTITY = "project"


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProjectRepository(session)

    async def create_project(
        self,
        payload: ProjectCreate,
        owner_id: uuid.UUID,
        background_tasks: BackgroundTasks | None = None,
    ) -> Project:
        project = await self.repo.create(
            {**payload.model_dump(), "owner_id": owner_id}
        )
        if background_tasks is not None:
            background_tasks.add_task(
                activity_service.log_activity,
                user_id=owner_id,
                action="CREATE",
                target_entity=TARGET_ENTITY,
                target_id=project.id,
                details={"name": project.name},
            )
        return project

    async def get_project(self, project_id: uuid.UUID) -> Project:
        project = await self.repo.get(project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        return project

    async def get_owned_project(
        self, project_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Project:
        project = await self.get_project(project_id)
        if project.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not own this project",
            )
        return project

    async def list_projects_for_owner(
        self,
        owner_id: uuid.UUID,
        *,
        sort_by: ProjectSortField = ProjectSortField.created_at,
        order: SortOrder = SortOrder.desc,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Project]:
        return await self.repo.list_by_owner(
            owner_id, sort_by=sort_by, order=order, skip=skip, limit=limit
        )

    async def update_project(
        self,
        project_id: uuid.UUID,
        payload: ProjectUpdate,
        owner_id: uuid.UUID,
        background_tasks: BackgroundTasks | None = None,
    ) -> Project:
        project = await self.get_owned_project(project_id, owner_id)
        data = payload.model_dump(exclude_unset=True)
        updated = await self.repo.update(project, data)
        if background_tasks is not None:
            background_tasks.add_task(
                activity_service.log_activity,
                user_id=owner_id,
                action="UPDATE",
                target_entity=TARGET_ENTITY,
                target_id=updated.id,
                details={"changed_fields": list(data.keys())},
            )
        return updated

    async def delete_project(
        self,
        project_id: uuid.UUID,
        owner_id: uuid.UUID,
        background_tasks: BackgroundTasks | None = None,
    ) -> None:
        project = await self.get_owned_project(project_id, owner_id)
        await self.repo.soft_delete(project)
        if background_tasks is not None:
            background_tasks.add_task(
                activity_service.log_activity,
                user_id=owner_id,
                action="DELETE",
                target_entity=TARGET_ENTITY,
                target_id=project.id,
            )
