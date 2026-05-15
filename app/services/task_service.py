import uuid
from typing import Sequence

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dto.common import SortOrder, TaskSortField
from app.dto.task import TaskCreate, TaskUpdate
from app.models.domain import Task, TaskPriority, TaskStatus
from app.integrations.quote_client import fetch_random_quote
from app.repositories.task_repository import TaskRepository
from app.services.activity_service import activity_service
from app.services.project_service import ProjectService

TARGET_ENTITY = "task"


async def _celebrate_task_completion(
    user_id: uuid.UUID, task_id: uuid.UUID
) -> None:
    """Background hook: fetch a quote and log it as an activity."""
    quote = await fetch_random_quote()
    await activity_service.log_activity(
        user_id=user_id,
        action="COMPLETED",
        target_entity=TARGET_ENTITY,
        target_id=task_id,
        details={"quote": quote["quote"], "author": quote["author"]},
    )


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TaskRepository(session)
        self.project_service = ProjectService(session)

    async def create_task(
        self,
        payload: TaskCreate,
        current_user_id: uuid.UUID,
        background_tasks: BackgroundTasks | None = None,
    ) -> Task:
        # Only the owner of the project may create tasks within it.
        await self.project_service.get_owned_project(
            payload.project_id, current_user_id
        )
        task = await self.repo.create(payload.model_dump())
        if background_tasks is not None:
            background_tasks.add_task(
                activity_service.log_activity,
                user_id=current_user_id,
                action="CREATE",
                target_entity=TARGET_ENTITY,
                target_id=task.id,
                details={
                    "project_id": str(task.project_id),
                    "title": task.title,
                },
            )
        return task

    async def get_task(self, task_id: uuid.UUID, current_user_id: uuid.UUID) -> Task:
        task = await self.repo.get(task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )
        await self._authorize_task_access(task, current_user_id)
        return task

    async def list_tasks(
        self,
        current_user_id: uuid.UUID,
        *,
        project_id: uuid.UUID | None = None,
        status_filter: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assigned_user_id: uuid.UUID | None = None,
        sort_by: TaskSortField = TaskSortField.created_at,
        order: SortOrder = SortOrder.desc,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Task]:
        # If the caller targets a specific project, they must own it.
        # Otherwise apply a visibility scope: tasks assigned to me OR in
        # projects I own. Explicit filters layer on top of either case.
        if project_id is not None:
            await self.project_service.get_owned_project(project_id, current_user_id)
            visible_to_user_id = None
        else:
            visible_to_user_id = current_user_id

        return await self.repo.filter_tasks(
            project_id=project_id,
            status=status_filter,
            priority=priority,
            assigned_user_id=assigned_user_id,
            visible_to_user_id=visible_to_user_id,
            sort_by=sort_by,
            order=order,
            skip=skip,
            limit=limit,
        )

    async def update_task(
        self,
        task_id: uuid.UUID,
        payload: TaskUpdate,
        current_user_id: uuid.UUID,
        background_tasks: BackgroundTasks | None = None,
    ) -> Task:
        task = await self.get_task(task_id, current_user_id)
        previous_status = task.status
        data = payload.model_dump(exclude_unset=True)
        updated = await self.repo.update(task, data)

        if background_tasks is not None:
            background_tasks.add_task(
                activity_service.log_activity,
                user_id=current_user_id,
                action="UPDATE",
                target_entity=TARGET_ENTITY,
                target_id=updated.id,
                details={"changed_fields": list(data.keys())},
            )

            # Celebrate a transition into the completed state.
            if (
                updated.status == TaskStatus.completed
                and previous_status != TaskStatus.completed
            ):
                background_tasks.add_task(
                    _celebrate_task_completion,
                    user_id=current_user_id,
                    task_id=updated.id,
                )

        return updated

    async def delete_task(
        self,
        task_id: uuid.UUID,
        current_user_id: uuid.UUID,
        background_tasks: BackgroundTasks | None = None,
    ) -> None:
        task = await self.repo.get(task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )
        # Only the project owner may delete tasks.
        await self.project_service.get_owned_project(task.project_id, current_user_id)
        await self.repo.soft_delete(task)
        if background_tasks is not None:
            background_tasks.add_task(
                activity_service.log_activity,
                user_id=current_user_id,
                action="DELETE",
                target_entity=TARGET_ENTITY,
                target_id=task.id,
                details={"project_id": str(task.project_id)},
            )

    async def _authorize_task_access(
        self, task: Task, current_user_id: uuid.UUID
    ) -> None:
        if task.assigned_user_id == current_user_id:
            return
        project = await self.project_service.get_project(task.project_id)
        if project.owner_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this task",
            )
