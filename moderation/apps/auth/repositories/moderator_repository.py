from sqlalchemy import func, select

from apps.auth.models import Moderator
from apps.auth.schemas.moderator import ModeratorCreateSchema, ModeratorReadSchema, ModeratorUpdateSchema
from shared.db import DBCrudRepository


class ModeratorRepository(
    DBCrudRepository[Moderator, ModeratorCreateSchema, ModeratorReadSchema, ModeratorUpdateSchema]
):
    async def get_by_email(self, email: str) -> ModeratorReadSchema | None:
        query = select(Moderator).where(Moderator.email == email)

        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()

        return self.model_validate(model) if model else None

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        is_active: bool | None = None,
    ) -> tuple[list[ModeratorReadSchema], int]:
        """Возвращает страницу модераторов + total_count (без учёта пагинации)."""
        query = select(Moderator)
        count_query = select(func.count()).select_from(Moderator)

        if is_active is not None:
            query = query.where(Moderator.is_active == is_active)
            count_query = count_query.where(Moderator.is_active == is_active)

        query = query.order_by(Moderator.created_at.desc()).limit(limit).offset(offset)

        async with self.session_manager.get_session() as session:
            items_result = await session.execute(query)
            count_result = await session.execute(count_query)
            items = items_result.scalars().all()
            total_count = count_result.scalar_one()

        return [self.model_validate(m) for m in items], total_count
