"""Конкретизация generic-репозитория `shared.outbox.OutboxRepository` под b2b-модель."""

from apps.outbox.models import OutboxEvent
from db import SessionManager
from shared.outbox import OutboxEnqueueSchema, OutboxEventReadSchema, OutboxRepository


class B2BOutboxRepository(OutboxRepository[OutboxEvent]):
    """Outbox-репозиторий b2b-сервиса.

    Базовый `OutboxRepository.enqueue` принимает `AsyncSession` извне — это нужно
    для use-cases, которые хотят выполнить INSERT outbox в той же транзакции
    с доменной мутацией.

    Для use-cases, которые работают с собственной сессией в каждом `.create()`,
    мы предоставляем удобный метод `enqueue_in_new_transaction()` — он открывает
    собственную транзакцию. Это слегка ослабляет транзакционную гарантию
    (теоретически возможен момент, когда доменная мутация закоммитилась,
    а outbox-событие — нет), но согласуется с текущей архитектурой `b2b`,
    где каждый репозиторий уже работает в своей транзакции.
    """

    model_type = OutboxEvent

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def enqueue_in_new_transaction(self, data: OutboxEnqueueSchema) -> OutboxEventReadSchema:
        """Открывает новую транзакцию и вставляет outbox-событие. Удобно, если
        вызывающий код не оперирует явной сессией."""
        async with self.session_manager.get_session() as session:
            return await self.enqueue(session, data)
