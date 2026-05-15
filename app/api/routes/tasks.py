import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.api.deps import CurrentUser, DbSession
from app.dto.task import TaskCreate, TaskFilter, TaskRead, TaskUpdate
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> TaskRead:
    service = TaskService(db)
    task = await service.create_task(
        payload, current_user_id=current_user.id, background_tasks=background_tasks
    )
    return TaskRead.model_validate(task)


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    db: DbSession,
    current_user: CurrentUser,
    filters: TaskFilter = Depends(),
) -> list[TaskRead]:
    service = TaskService(db)
    tasks = await service.list_tasks(
        current_user_id=current_user.id,
        project_id=filters.project_id,
        status_filter=filters.status,
        priority=filters.priority,
        assigned_user_id=filters.assigned_user_id,
        sort_by=filters.sort_by,
        order=filters.order,
        skip=filters.skip,
        limit=filters.limit,
    )
    return [TaskRead.model_validate(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> TaskRead:
    service = TaskService(db)
    task = await service.get_task(task_id, current_user.id)
    return TaskRead.model_validate(task)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> TaskRead:
    service = TaskService(db)
    task = await service.update_task(
        task_id, payload, current_user.id, background_tasks=background_tasks
    )
    return TaskRead.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> None:
    service = TaskService(db)
    await service.delete_task(
        task_id, current_user.id, background_tasks=background_tasks
    )
