from uuid import UUID

from sqlalchemy import func, select

from apps.tickets.enums import TicketStatus
from apps.tickets.models import Ticket
from apps.tickets.schemas.db import TicketCreateSchema, TicketReadSchema, TicketUpdateSchema
from shared.db import DBCrudRepository


class TicketRepository(DBCrudRepository[Ticket, TicketCreateSchema, TicketReadSchema, TicketUpdateSchema]):
    """DB-операции над тикетами модерации.

    Использование в M3 — input-канал от B2B (events), а также агрегаты для статистики.
    """

    async def list_by_product(self, product_id: UUID) -> list[TicketReadSchema]:
        """Все тикеты по товару (любой статус)."""
        query = select(Ticket).where(Ticket.product_id == product_id)
        async with self.session_manager.get_session() as session:
            result = await session.execute(query)
            return [self.model_validate(m) for m in result.scalars().all()]

    async def get_active_for_product(self, product_id: UUID) -> TicketReadSchema | None:
        """Активный тикет (PENDING или IN_REVIEW) для product_id.

        В норме у товара одновременно не больше одного активного тикета —
        событие EDITED модифицирует существующий тикет, CREATED создаёт новый.
        """
        query = (
            select(Ticket)
            .where(Ticket.product_id == product_id)
            .where(Ticket.status.in_([TicketStatus.PENDING, TicketStatus.IN_REVIEW]))
            .order_by(Ticket.created_at.desc())
            .limit(1)
        )
        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()
        return self.model_validate(model) if model else None

    async def archive_for_product(self, product_id: UUID) -> int:
        """Перевести все НЕ ARCHIVED тикеты товара в ARCHIVED. Возвращает кол-во обновлённых."""
        from sqlalchemy import update

        query = (
            update(Ticket)
            .where(Ticket.product_id == product_id)
            .where(Ticket.status != TicketStatus.ARCHIVED)
            .values(status=TicketStatus.ARCHIVED)
        )
        async with self.session_manager.get_session() as session:
            result = await session.execute(query)
            return int(result.rowcount or 0)

    async def count_by_status(self) -> dict[str, int]:
        """Возвращает кол-во тикетов в разрезе статусов (полная история)."""
        query = select(Ticket.status, func.count()).group_by(Ticket.status)
        async with self.session_manager.get_session() as session:
            result = await session.execute(query)
            return {row[0]: int(row[1]) for row in result.all()}

    async def count_by_moderator(self) -> list[tuple[UUID, dict[str, int]]]:
        """Возвращает per-moderator аггрегаты:
        [(moderator_id, {status: count, ...}), ...].

        Включает только тикеты с claimed_by != NULL.
        """
        query = (
            select(Ticket.claimed_by, Ticket.status, func.count())
            .where(Ticket.claimed_by.is_not(None))
            .group_by(Ticket.claimed_by, Ticket.status)
        )
        async with self.session_manager.get_session() as session:
            result = await session.execute(query)
        per_mod: dict[UUID, dict[str, int]] = {}
        for moderator_id, status, count in result.all():
            assert moderator_id is not None
            per_mod.setdefault(moderator_id, {})[status] = int(count)
        return list(per_mod.items())

    async def total_count(self) -> int:
        """Все тикеты (любой статус)."""
        query = select(func.count()).select_from(Ticket)
        async with self.session_manager.get_session() as session:
            return int((await session.execute(query)).scalar_one())
