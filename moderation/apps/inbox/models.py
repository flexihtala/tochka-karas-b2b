from shared.db import Base, IDMixin, TimestampMixin
from shared.inbox import ProcessedEventFieldsMixin
from shared.inbox.fields import make_sender_key_unique


class ProcessedEvent(IDMixin, TimestampMixin, ProcessedEventFieldsMixin, Base):
    """Локальная таблица processed_events для Moderation-сервиса.

    Используется shared.inbox.IdempotentHandler для at-most-once обработки
    входящих событий от других сервисов (B2B). Гарантируется UNIQUE(sender_service,
    idempotency_key) — повторный запрос вернёт кешированный ответ.
    """

    __tablename__ = 'processed_events'
    __table_args__ = (make_sender_key_unique('uq_processed_events_sender_key'),)
