import uuid

from fastapi import APIRouter, BackgroundTasks, Query, status

from app.api.deps import CurrentUser, DbSession
from app.dto.common import ProjectSortField, SortOrder
from app.dto.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> ProjectRead:
    service = ProjectService(db)
    project = await service.create_project(
        payload, owner_id=current_user.id, background_tasks=background_tasks
    )
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
async def list_my_projects(
    db: DbSession,
    current_user: CurrentUser,
    sort_by: ProjectSortField = Query(ProjectSortField.created_at),
    order: SortOrder = Query(SortOrder.desc),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[ProjectRead]:
    service = ProjectService(db)
    projects = await service.list_projects_for_owner(
        current_user.id, sort_by=sort_by, order=order, skip=skip, limit=limit
    )
    return [ProjectRead.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectRead:
    service = ProjectService(db)
    project = await service.get_owned_project(project_id, current_user.id)
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> ProjectRead:
    service = ProjectService(db)
    project = await service.update_project(
        project_id, payload, current_user.id, background_tasks=background_tasks
    )
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> None:
    service = ProjectService(db)
    await service.delete_project(
        project_id, current_user.id, background_tasks=background_tasks
    )
