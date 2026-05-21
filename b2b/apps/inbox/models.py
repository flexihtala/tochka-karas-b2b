"""B2B-локальная модель inbox.

`ProcessedEventFieldsMixin` определяет общие колонки (sender_service,
idempotency_key, response_cached). Здесь добавляются только `__tablename__` и
наследование от локального `Base` / `IDMixin` / `TimestampMixin`, чтобы alembic
autogenerate b2b-сервиса видел таблицу. Уникальное ограничение по
(sender_service, idempotency_key) обеспечивает idempotent-обработку входящих
событий от внешних сервисов.
"""

from db import Base, IDMixin, TimestampMixin
from shared.inbox import ProcessedEventFieldsMixin
from shared.inbox.fields import make_sender_key_unique


class ProcessedEvent(IDMixin, TimestampMixin, ProcessedEventFieldsMixin, Base):
    __tablename__ = 'processed_events'
    __table_args__ = (make_sender_key_unique('uq_processed_events_sender_key'),)
