"""B2COutboxRepository — конкретизация shared.outbox.OutboxRepository под b2c.

Аналогично b2b/apps/outbox/repositories/outbox_repository.py: используем
generic OutboxRepository[OutboxModel] с указанием конкретной модели.

`enqueue()` принимает session — нужно для размещения INSERT outbox в той же
транзакции, что и доменная мутация (например, перевод Order.status =
CANCEL_PENDING вместе с enqueue UNRESERVE_ORDER). Для случаев, когда нужно
просто положить событие без активной транзакции — есть
`enqueue_in_new_transaction()`.
"""

from apps.outbox.models import OutboxEvent
from shared.db import SessionManager
from shared.outbox import OutboxEnqueueSchema, OutboxEventReadSchema, OutboxRepository


class B2COutboxRepository(OutboxRepository[OutboxEvent]):
    model_type = OutboxEvent

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def enqueue_in_new_transaction(self, data: OutboxEnqueueSchema) -> OutboxEventReadSchema:
        async with self.session_manager.get_session() as session:
            return await self.enqueue(session, data)
