"""B2B-локальная модель processed_events (inbox).

Используется для идемпотентной обработки входящих service-to-service
запросов (X-Service-Key, например POST /inventory/reserve от B2C).

`ProcessedEventFieldsMixin` определяет общие колонки
(sender_service, idempotency_key, response_cached). UNIQUE-ограничение
по `(sender_service, idempotency_key)` гарантирует, что повторный
запрос с тем же ключом будет обнаружен и обработан как дубликат
(at-most-once semantics).
"""

from db import Base, IDMixin, TimestampMixin
from shared.inbox import ProcessedEventFieldsMixin
from shared.inbox.fields import make_sender_key_unique


class ProcessedEvent(IDMixin, TimestampMixin, ProcessedEventFieldsMixin, Base):
    __tablename__ = 'processed_events'
    __table_args__ = (make_sender_key_unique(),)
