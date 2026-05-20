"""IdempotentHandler — обёртка для idempotent-обработки входящих событий.

Использование внутри router:

    @router.post('/events/moderation')
    async def receive_moderation_event(payload: ModerationEventSchema):
        async with session_manager.get_session() as session:
            return await idempotent_handler.handle(
                session=session,
                sender=ServiceName.MODERATION,
                key=payload.idempotency_key,
                handler=lambda: apply_moderation_use_case.execute(payload),
            )
"""

from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.inbox.fields import ProcessedEventFieldsMixin
from shared.types import ServiceName

InboxModel = TypeVar('InboxModel', bound=ProcessedEventFieldsMixin)
ResultT = TypeVar('ResultT')


class IdempotentHandler(Generic[InboxModel]):
    """Обеспечивает at-most-once семантику обработки внешних событий.

    Каждый сервис создаёт экземпляр со своим типом модели:
        handler = IdempotentHandler(ProcessedEvent)
    """

    def __init__(self, model_type: type[InboxModel]):
        self.model_type = model_type

    async def handle(
        self,
        session: AsyncSession,
        sender: ServiceName,
        key: UUID,
        handler: Callable[[], Awaitable[ResultT]],
        result_to_payload: Callable[[ResultT], dict[str, Any]] | None = None,
    ) -> ResultT | dict[str, Any]:
        """Обрабатывает событие идемпотентно.

        Сценарии:
        - Первый вызов с этим (sender, key): выполняет handler(), сохраняет ProcessedEvent,
          возвращает результат handler.
        - Повторный вызов: возвращает cached response_cached без выполнения handler.

        Race: если два запроса одновременно — один INSERT-нет успешно, второй ловит
        IntegrityError → читает cached, возвращает его.
        """
        # 1. Lookup
        cached = await self._lookup(session, sender, key)
        if cached is not None:
            return cached.response_cached or {}  # type: ignore[return-value]

        # 2. Выполнить handler
        result = await handler()

        # 3. Записать processed_event
        payload = result_to_payload(result) if result_to_payload else None
        record = self.model_type(
            sender_service=sender.value,
            idempotency_key=key,
            response_cached=payload,
        )
        session.add(record)
        try:
            await session.flush()
        except IntegrityError:
            # Кто-то параллельно записал — читаем cached, возвращаем его
            await session.rollback()
            cached2 = await self._lookup(session, sender, key)
            if cached2 is not None:
                return cached2.response_cached or {}  # type: ignore[return-value]
            raise  # маловероятно — IntegrityError по другой причине

        return result

    async def _lookup(self, session: AsyncSession, sender: ServiceName, key: UUID) -> InboxModel | None:
        stmt = (
            select(self.model_type)
            .where(self.model_type.sender_service == sender.value)  # type: ignore[union-attr]
            .where(self.model_type.idempotency_key == key)  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
