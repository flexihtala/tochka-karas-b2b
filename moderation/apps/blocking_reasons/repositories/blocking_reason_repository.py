from sqlalchemy import select

from apps.blocking_reasons.models import BlockingReason
from apps.blocking_reasons.schemas.db import (
    BlockingReasonCreateSchema,
    BlockingReasonReadSchema,
    BlockingReasonUpdateSchema,
)
from shared.db import DBCrudRepository


class BlockingReasonRepository(
    DBCrudRepository[
        BlockingReason,
        BlockingReasonCreateSchema,
        BlockingReasonReadSchema,
        BlockingReasonUpdateSchema,
    ]
):
    async def get_by_name(self, name: str) -> BlockingReasonReadSchema | None:
        query = select(BlockingReason).where(BlockingReason.name == name)

        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()

        return self.model_validate(model) if model else None

    async def list_(
        self,
        *,
        hard_block: bool | None = None,
        is_active: bool | None = None,
    ) -> list[BlockingReasonReadSchema]:
        """Спека: справочник возвращается без пагинации (массив прямо в response)."""
        query = select(BlockingReason)

        if hard_block is not None:
            query = query.where(BlockingReason.hard_block == hard_block)
        if is_active is not None:
            query = query.where(BlockingReason.is_active == is_active)

        query = query.order_by(BlockingReason.name.asc())

        async with self.session_manager.get_session() as session:
            result = await session.execute(query)
            items = result.scalars().all()

        return [self.model_validate(m) for m in items]
