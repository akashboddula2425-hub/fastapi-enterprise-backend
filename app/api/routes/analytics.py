from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.dto.analytics import AnalyticsResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("", response_model=AnalyticsResponse)
async def get_analytics_overview(
    db: DbSession,
    current_user: CurrentUser,
) -> AnalyticsResponse:
    service = AnalyticsService(db)
    return await service.get_overview(owner_id=current_user.id)
