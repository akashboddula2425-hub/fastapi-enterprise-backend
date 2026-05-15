import uuid
from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async CRUD repository for SQLAlchemy 2.0 models."""

    model: Type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        stmt = select(self.model).where(
            self.model.id == entity_id,
            self.model.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, *, skip: int = 0, limit: int = 100) -> Sequence[ModelT]:
        stmt = (
            select(self.model)
            .where(self.model.is_deleted.is_(False))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, data: dict[str, Any]) -> ModelT:
        entity = self.model(**data)
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity: ModelT, data: dict[str, Any]) -> ModelT:
        for field, value in data.items():
            setattr(entity, field, value)
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def soft_delete(self, entity: ModelT) -> None:
        entity.is_deleted = True
        self.session.add(entity)
        await self.session.flush()
