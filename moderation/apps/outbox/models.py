"""Outbox model for the Moderation service.

Каждый сервис создаёт свою модель Outbox в собственной MetaData. Эта модель
живёт в одной MetaData с остальными моделями Moderation, поэтому alembic
autogenerate видит её и не конфликтует с outbox-моделями других сервисов.
"""

from shared.db import Base, IDMixin, TimestampMixin
from shared.outbox import OutboxFieldsMixin


class ModerationOutboxEvent(IDMixin, TimestampMixin, OutboxFieldsMixin, Base):
    """Исходящие события Moderation → b2b (MODERATED, BLOCKED).

    Каждое решение модератора enqueue'ит запись в outbox в той же транзакции,
    что и доменная мутация (UPDATE tickets). Воркер (M3) выгребает PENDING
    через `SELECT ... FOR UPDATE SKIP LOCKED` и шлёт b2b /api/v1/moderation/events.
    """

    __tablename__ = 'outbox'
