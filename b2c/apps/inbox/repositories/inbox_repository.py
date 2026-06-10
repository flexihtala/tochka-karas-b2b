"""InboxRepository — обёртка для работы с processed_events.

Используется внутри idempotent-обработчиков событий. Все вставки/чтения
выполняются через одну session с явной транзакцией (см. shared.db.SessionManager),
поскольку IdempotentHandler хочет ловить IntegrityError на UNIQUE(sender, key).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.inbox.models import ProcessedEvent
from shared.db import SessionManager
from shared.types import ServiceName


class InboxRepository:
    """Тонкая обёртка с lookup/insert по (sender, idempotency_key).

    Не наследует DBCrudRepository — у нас узкоспециализированный API,
    основная логика инкапсулирована в shared.inbox.IdempotentHandler.
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def lookup(
        self,
        session: AsyncSession,
        sender: ServiceName,
        idempotency_key: UUID,
    ) -> ProcessedEvent | None:
        stmt = (
            select(ProcessedEvent)
            .where(ProcessedEvent.sender_service == sender.value)
            .where(ProcessedEvent.idempotency_key == idempotency_key)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def insert(
        self,
        session: AsyncSession,
        sender: ServiceName,
        idempotency_key: UUID,
        response_cached: dict | None = None,
    ) -> ProcessedEvent:
        record = ProcessedEvent(
            sender_service=sender.value,
            idempotency_key=idempotency_key,
            response_cached=response_cached,
        )
        session.add(record)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            raise
        return record
