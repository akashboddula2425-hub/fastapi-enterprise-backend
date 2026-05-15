import uuid
from typing import Any

from app.core.database import AsyncSessionLocal
from app.repositories.activity_repository import ActivityRepository


class ActivityService:
    """Audit log writer.

    `log_activity` is intended to run inside FastAPI BackgroundTasks. The
    main request's session is already closed by the time background tasks
    execute, so this method opens and commits its own session.
    """

    async def log_activity(
        self,
        user_id: uuid.UUID,
        action: str,
        target_entity: str,
        target_id: uuid.UUID,
        details: dict[str, Any] | None = None,
    ) -> None:
        async with AsyncSessionLocal() as session:
            try:
                repo = ActivityRepository(session)
                await repo.create(
                    {
                        "user_id": user_id,
                        "action": action,
                        "target_entity": target_entity,
                        "target_id": target_id,
                        "details": details,
                    }
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise


activity_service = ActivityService()
