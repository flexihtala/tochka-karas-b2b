from uuid import UUID

from sqlalchemy import select

from apps.inbox.models import ProcessedEvent
from shared.db.session_manager import SessionManager
from shared.types import ServiceName


class InboxRepository:
    """Read-only обёртка над ProcessedEvent. Запись и idempotent-handling делает
    shared.inbox.IdempotentHandler через переданную AsyncSession; репозиторий нужен
    для lookup'ов (например, диагностика, GET /inbox/{key}). В M3 используется
    только в тестах — оставлен для расширения.
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def get(self, sender: ServiceName, idempotency_key: UUID) -> ProcessedEvent | None:
        query = (
            select(ProcessedEvent)
            .where(ProcessedEvent.sender_service == sender.value)
            .where(ProcessedEvent.idempotency_key == idempotency_key)
        )
        async with self.session_manager.get_session() as session:
            return (await session.execute(query)).scalar_one_or_none()
