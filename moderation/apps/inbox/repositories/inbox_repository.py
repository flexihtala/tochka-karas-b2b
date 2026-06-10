"""InboxRepository — журнал processed_events для идемпотентности канала b2b/events.

Moderation, в отличие от b2c, НЕ переигрывает cached-ответ на дубликат: по спеке
повторное событие с тем же idempotency_key — 409 Conflict. Поэтому вместо
shared.inbox.IdempotentHandler (replay-семантика, INSERT после handler) используется
прямой INSERT ключа ДО любых побочных эффектов: UNIQUE(sender_service, idempotency_key)
— арбитр гонки, конкурентный/повторный дубликат ловит IntegrityError.
"""

from uuid import UUID

from apps.inbox.models import ProcessedEvent
from shared.db import SessionManager
from shared.types import ServiceName


class InboxRepository:
    """Тонкая INSERT-only обёртка над processed_events.

    Не наследует DBCrudRepository — узкоспециализированный API. IntegrityError
    по UNIQUE(sender_service, idempotency_key) пробрасывается вызывающему:
    use-case конвертирует её в DuplicateEventError (409 DUPLICATE_EVENT).
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def insert(self, sender: ServiceName, idempotency_key: UUID) -> None:
        """INSERT (sender, key) в processed_events; коммитится до мутаций тикетов.

        Дубликат поднимает sqlalchemy.exc.IntegrityError (unique violation),
        транзакция откатывается контекст-менеджером session_manager.
        """
        async with self.session_manager.get_session() as session:
            session.add(ProcessedEvent(sender_service=sender.value, idempotency_key=idempotency_key))
            await session.flush()
