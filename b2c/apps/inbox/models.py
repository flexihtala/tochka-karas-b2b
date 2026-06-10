"""ProcessedEvent — таблица inbox для idempotent-обработки входящих событий.

Использование (см. shared.inbox.IdempotentHandler):
    PRIMARY KEY: id (UUID)
    UNIQUE (sender_service, idempotency_key) — основной ключ идемпотентности.

Поля наследуются из shared.inbox.fields.ProcessedEventFieldsMixin:
    sender_service: str
    idempotency_key: UUID
    response_cached: JSONB | None
"""

from shared.db import Base, IDMixin, TimestampMixin
from shared.inbox.fields import ProcessedEventFieldsMixin, make_sender_key_unique


class ProcessedEvent(IDMixin, TimestampMixin, ProcessedEventFieldsMixin, Base):
    """Журнал обработанных входящих событий — at-most-once семантика."""

    __tablename__ = 'processed_events'
    __table_args__ = (make_sender_key_unique('uq_processed_events_sender_key'),)
