import uuid
from typing import Sequence

from sqlalchemy import select

from app.models.domain import Activity
from app.repositories.base import BaseRepository


class ActivityRepository(BaseRepository[Activity]):
    model = Activity

    async def list_by_user(
        self, user_id: uuid.UUID, *, skip: int = 0, limit: int = 100
    ) -> Sequence[Activity]:
        stmt = (
            select(Activity)
            .where(
                Activity.user_id == user_id,
                Activity.is_deleted.is_(False),
            )
            .order_by(Activity.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_target(
        self,
        target_entity: str,
        target_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Activity]:
        stmt = (
            select(Activity)
            .where(
                Activity.target_entity == target_entity,
                Activity.target_id == target_id,
                Activity.is_deleted.is_(False),
            )
            .order_by(Activity.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
