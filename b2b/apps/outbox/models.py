"""B2B-локальная модель outbox.

`OutboxFieldsMixin` определяет общие колонки (idempotency_key, event_type,
target_service, payload, status, retry_count, next_retry_at, sent_at, last_error).
Здесь добавляются только `__tablename__` и наследование от локального `Base` /
`IDMixin` / `TimestampMixin`, чтобы alembic autogenerate b2b-сервиса видел таблицу.
"""

from db import Base, IDMixin, TimestampMixin
from shared.outbox import OutboxFieldsMixin


class OutboxEvent(IDMixin, TimestampMixin, OutboxFieldsMixin, Base):
    __tablename__ = 'outbox'
