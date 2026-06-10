"""Fakes для тестов входящего канала b2b/events."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError

from shared.types import ServiceName


class FakeInboxRepository:
    """In-memory аналог InboxRepository.

    Имитирует UNIQUE(sender_service, idempotency_key): повторный insert с тем же
    (sender, key) поднимает IntegrityError — как реальный unique violation в PG.
    """

    def __init__(self):
        self.keys: set[tuple[str, UUID]] = set()

    async def insert(self, sender: ServiceName, idempotency_key: UUID) -> None:
        record = (sender.value, idempotency_key)
        if record in self.keys:
            raise IntegrityError(
                statement='INSERT INTO processed_events ...',
                params=None,
                orig=Exception('duplicate key value violates unique constraint "uq_processed_events_sender_key"'),
            )
        self.keys.add(record)
