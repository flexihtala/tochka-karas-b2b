"""B2C-локальная модель outbox.

`OutboxFieldsMixin` (из shared.outbox) определяет общие колонки
(idempotency_key, event_type, target_service, payload, status, retry_count,
next_retry_at, sent_at, last_error). Здесь добавляются только `__tablename__`
и наследование от Base / IDMixin / TimestampMixin, чтобы alembic autogenerate
b2c-сервиса видел таблицу.
"""

from shared.db import Base, IDMixin, TimestampMixin
from shared.outbox import OutboxFieldsMixin


class OutboxEvent(IDMixin, TimestampMixin, OutboxFieldsMixin, Base):
    __tablename__ = 'outbox'
