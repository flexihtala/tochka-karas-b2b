"""InboxRepository — lookup и запись processed_events для идемпотентности.

Use-case вызывает оба метода в той же транзакции что и доменная мутация
(передавая `session: AsyncSession`). Это даёт атомарный idempotency-кеш:
либо записаны и мутация, и processed_event, либо ничего.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.inbox.models import ProcessedEvent
from shared.types import ServiceName


class InboxRepository:
    async def get_cached_response(
        self,
        session: AsyncSession,
        sender: ServiceName,
        idempotency_key: UUID,
    ) -> dict[str, Any] | None:
        """Вернуть `response_cached`, если запись (sender, key) уже есть.

        None — записи нет, нужно выполнить хэндлер.
        Пустой dict ({}) — запись есть, но без cached response (например,
        для 204 No Content). Use-case интерпретирует.
        """
        stmt = (
            select(ProcessedEvent)
            .where(ProcessedEvent.sender_service == sender.value)
            .where(ProcessedEvent.idempotency_key == idempotency_key)
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return row.response_cached or {}

    async def record(
        self,
        session: AsyncSession,
        sender: ServiceName,
        idempotency_key: UUID,
        cached_response: dict[str, Any],
    ) -> None:
        """INSERT в processed_events в текущей транзакции.

        Если в этот момент кто-то параллельно записал тот же ключ — UNIQUE
        constraint поднимет IntegrityError; вызывающий код пробросит ошибку,
        транзакция откатится.
        """
        record = ProcessedEvent(
            sender_service=sender.value,
            idempotency_key=idempotency_key,
            response_cached=cached_response,
        )
        session.add(record)
        await session.flush()
