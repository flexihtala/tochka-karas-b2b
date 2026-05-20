"""OutboxRepository — операции над таблицей outbox.

Generic — параметризуется типом модели сервиса (см. shared.outbox.fields.OutboxFieldsMixin).

Use-cases вызывают `enqueue()` в той же транзакции что и доменная мутация
(передавая `session: AsyncSession`). Воркер вызывает `claim_batch()` / `mark_*()`
в своей транзакции.
"""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.outbox.enums import OutboxStatus
from shared.outbox.fields import OutboxFieldsMixin
from shared.outbox.schemas import OutboxEnqueueSchema, OutboxEventReadSchema

OutboxModel = TypeVar('OutboxModel', bound=OutboxFieldsMixin)


class OutboxRepository(Generic[OutboxModel]):
    """Универсальный репозиторий outbox.

    Каждый сервис конкретизирует:
        class B2BOutboxRepository(OutboxRepository[OutboxEvent]):
            model_type = OutboxEvent
    """

    model_type: type[OutboxModel]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # model_type выставляется наследником вручную; валидация — на первом use

    async def enqueue(self, session: AsyncSession, data: OutboxEnqueueSchema) -> OutboxEventReadSchema:
        """INSERT в outbox в текущей транзакции.

        Использовать ВНУТРИ доменной транзакции:
            async with session_manager.get_session() as session:
                # ... доменная мутация ...
                await outbox_repository.enqueue(session, OutboxEnqueueSchema(...))

        Если idempotency_key уже существует — поднимет IntegrityError (UNIQUE-нарушение).
        Use-case должен это поймать и считать операцию повторной.
        """
        model = self.model_type(
            idempotency_key=data.idempotency_key,
            event_type=data.event_type,
            target_service=data.target_service.value,
            payload=data.payload,
            status=OutboxStatus.PENDING.value,
            retry_count=0,
        )
        session.add(model)
        await session.flush()
        return OutboxEventReadSchema.model_validate(model)

    async def claim_batch(self, session: AsyncSession, batch_size: int = 10) -> list[OutboxModel]:
        """Захватывает batch PENDING-событий, готовых к отправке (next_retry_at <= now или NULL).

        Использовать SELECT ... FOR UPDATE SKIP LOCKED, чтобы несколько воркеров не дрались.
        """
        now = datetime.now(UTC)
        stmt = (
            select(self.model_type)
            .where(self.model_type.status == OutboxStatus.PENDING.value)  # type: ignore[union-attr]
            .where((self.model_type.next_retry_at.is_(None)) | (self.model_type.next_retry_at <= now))  # type: ignore[union-attr]
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def mark_sent(self, session: AsyncSession, event_id: UUID) -> None:
        model = await session.get(self.model_type, event_id)
        if model is None:
            return
        model.status = OutboxStatus.SENT.value  # type: ignore[attr-defined]
        model.sent_at = datetime.now(UTC)  # type: ignore[attr-defined]
        await session.flush()

    async def mark_retry(self, session: AsyncSession, event_id: UUID, next_retry_at: datetime, error: str) -> None:
        """Запланировать повторную попытку. retry_count += 1."""
        model = await session.get(self.model_type, event_id)
        if model is None:
            return
        model.retry_count = (model.retry_count or 0) + 1  # type: ignore[attr-defined]
        model.next_retry_at = next_retry_at  # type: ignore[attr-defined]
        model.last_error = error[:2048]  # type: ignore[attr-defined]
        await session.flush()

    async def mark_failed(self, session: AsyncSession, event_id: UUID, error: str) -> None:
        """Перевести в FAILED — больше не пытаемся, нужна ручная разборка."""
        model = await session.get(self.model_type, event_id)
        if model is None:
            return
        model.status = OutboxStatus.FAILED.value  # type: ignore[attr-defined]
        model.last_error = error[:2048]  # type: ignore[attr-defined]
        await session.flush()
