"""Репозиторий sku_unavailability — upsert по sku_id (PK)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.events.models import SkuUnavailability
from shared.db import SessionManager


class SkuUnavailabilityRepository:
    """Тонкий репозиторий: upsert/list, без дженерик-обвязки.

    Использует session-параметр (не контекст менеджера), чтобы вписаться в
    одну транзакцию с inbox-записью (см. HandleProductEventUseCase).
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def upsert_many(
        self,
        session: AsyncSession,
        *,
        sku_ids: list[UUID],
        reason: str,
        product_id: UUID,
        event_idempotency_key: UUID,
    ) -> None:
        if not sku_ids:
            return
        values = [
            {
                'sku_id': sku_id,
                'reason': reason,
                'product_id': product_id,
                'event_idempotency_key': event_idempotency_key,
            }
            for sku_id in sku_ids
        ]
        stmt = pg_insert(SkuUnavailability).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[SkuUnavailability.sku_id],
            set_={
                'reason': stmt.excluded.reason,
                'product_id': stmt.excluded.product_id,
                'event_idempotency_key': stmt.excluded.event_idempotency_key,
            },
        )
        await session.execute(stmt)

    async def list_by_skus(self, sku_ids: list[UUID]) -> list[SkuUnavailability]:
        if not sku_ids:
            return []
        async with self.session_manager.get_session() as session:
            stmt = select(SkuUnavailability).where(SkuUnavailability.sku_id.in_(sku_ids))
            result = await session.execute(stmt)
            return list(result.scalars().all())
