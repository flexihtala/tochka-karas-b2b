from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.tickets.enums import TicketStatus
from apps.tickets.models import Ticket
from apps.tickets.schemas.db import TicketCreateSchema, TicketReadSchema, TicketUpdateSchema
from shared.db import DBCrudRepository


class TicketRepository(
    DBCrudRepository[Ticket, TicketCreateSchema, TicketReadSchema, TicketUpdateSchema],
):
    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        status: TicketStatus | None = None,
        queue_priority: int | None = None,
        category_id: UUID | None = None,
        seller_id: UUID | None = None,
    ) -> tuple[list[TicketReadSchema], int]:
        query = select(Ticket)
        count_query = select(func.count()).select_from(Ticket)

        if status is not None:
            query = query.where(Ticket.status == status.value)
            count_query = count_query.where(Ticket.status == status.value)
        if queue_priority is not None:
            query = query.where(Ticket.queue_priority == queue_priority)
            count_query = count_query.where(Ticket.queue_priority == queue_priority)
        if category_id is not None and hasattr(Ticket, 'category_id'):
            query = query.where(Ticket.category_id == category_id)
            count_query = count_query.where(Ticket.category_id == category_id)
        if seller_id is not None:
            query = query.where(Ticket.seller_id == seller_id)
            count_query = count_query.where(Ticket.seller_id == seller_id)

        query = query.order_by(Ticket.queue_priority.asc(), Ticket.created_at.asc()).limit(limit).offset(offset)

        async with self.session_manager.get_session() as session:
            items_result = await session.execute(query)
            count_result = await session.execute(count_query)
            items = items_result.scalars().all()
            total_count = count_result.scalar_one()

        return [self.model_validate(m) for m in items], total_count

    async def claim_next(self, moderator_id: UUID) -> TicketReadSchema | None:
        """Атомарно захватить следующий PENDING-тикет.

        Используется `SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`: если строка уже
        заблокирована другой транзакцией, она пропускается, и мы возвращаем
        следующую — гарантия, что два модератора не получат один тикет.

        Сортировка: queue_priority ASC, created_at ASC (FIFO внутри приоритета).
        """
        async with self.session_manager.get_session() as session:
            stmt = (
                select(Ticket)
                .where(Ticket.status == TicketStatus.PENDING.value)
                .order_by(Ticket.queue_priority.asc(), Ticket.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            result = await session.execute(stmt)
            ticket = result.scalar_one_or_none()
            if ticket is None:
                return None

            ticket.status = TicketStatus.IN_REVIEW.value
            ticket.claimed_by = moderator_id
            ticket.claimed_at = datetime.now(UTC)
            await session.flush()
            return self.model_validate(ticket)

    async def update_in_session(
        self,
        session: AsyncSession,
        data: TicketUpdateSchema,
    ) -> TicketReadSchema | None:
        """UPDATE в переданной транзакции (для use-cases, enqueue'ящих outbox в той же tx).

        Базовый CRUD `update()` открывает свой session — это сломало бы атомарность
        «UPDATE ticket + INSERT outbox». Поэтому approve/block идут через этот метод.
        """
        values = data.model_dump(exclude_unset=True, exclude={'id'})
        if not values:
            return await self._get_in_session(session, data.id)
        # Нормализация enum-полей: status в БД — строка.
        if 'status' in values and isinstance(values['status'], TicketStatus):
            values['status'] = values['status'].value

        stmt = update(Ticket).where(Ticket.id == data.id).values(**values).returning(Ticket)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        return self.model_validate(model) if model else None

    async def _get_in_session(self, session: AsyncSession, ticket_id: UUID) -> TicketReadSchema | None:
        stmt = select(Ticket).where(Ticket.id == ticket_id)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()
        return self.model_validate(model) if model else None

    async def get_active_for_product(self, product_id: UUID) -> TicketReadSchema | None:
        """Активный (не ARCHIVED) тикет для товара — для обработки PRODUCT_EDITED от B2B.

        product_id уникален в таблице tickets, поэтому активная запись не больше одной.
        HARD_BLOCKED здесь считается активной (терминальной) — вызывающий use-case сам
        решает игнорировать её (EDITED над HARD_BLOCKED — no-op).
        """
        stmt = (
            select(Ticket)
            .where(Ticket.product_id == product_id)
            .where(Ticket.status != TicketStatus.ARCHIVED.value)
            .order_by(Ticket.created_at.desc())
            .limit(1)
        )
        async with self.session_manager.get_session() as session:
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
        return self.model_validate(model) if model else None

    async def archive_for_product(self, product_id: UUID) -> int:
        """ARCHIVE все НЕ ARCHIVED тикеты товара — для обработки PRODUCT_DELETED от B2B.

        Идемпотентно: повторный DELETE по уже архивированным тикетам обновит 0 строк.
        HARD_BLOCKED тикеты тоже архивируются (запись модерации закрывается; в B2B товар
        остаётся заблокированным). Возвращает число затронутых строк.
        """
        stmt = (
            update(Ticket)
            .where(Ticket.product_id == product_id)
            .where(Ticket.status != TicketStatus.ARCHIVED.value)
            .values(status=TicketStatus.ARCHIVED.value)
        )
        async with self.session_manager.get_session() as session:
            result = await session.execute(stmt)
        return result.rowcount
