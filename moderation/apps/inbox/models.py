"""ProcessedEvent — таблица inbox для идемпотентной обработки входящих событий B2B.

Использование (см. apps.events.use_cases.handle_b2b_event):
    PRIMARY KEY: id (UUID)
    UNIQUE (sender_service, idempotency_key) — основной ключ идемпотентности,
    арбитр гонки при конкурентных/повторных доставках.

Поля наследуются из shared.inbox.fields.ProcessedEventFieldsMixin:
    sender_service: str
    idempotency_key: UUID
    response_cached: JSONB | None (moderation не переигрывает ответ — дубликат → 409)

created_at (TimestampMixin) играет роль received_at; TTL-очистка 24h —
DELETE WHERE created_at < now() - interval '24 hours' (scheduled job, вне scope).
"""

from shared.db import Base, IDMixin, TimestampMixin
from shared.inbox.fields import ProcessedEventFieldsMixin, make_sender_key_unique


class ProcessedEvent(IDMixin, TimestampMixin, ProcessedEventFieldsMixin, Base):
    """Журнал обработанных входящих событий — at-most-once семантика."""

    __tablename__ = 'processed_events'
    __table_args__ = (make_sender_key_unique('uq_processed_events_sender_key'),)
