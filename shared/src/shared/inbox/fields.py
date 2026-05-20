"""Колонки таблицы processed_events для idempotent обработки входящих событий."""

import uuid

from sqlalchemy import String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class ProcessedEventFieldsMixin:
    """Mixin с колонками processed_events.

    Каждый сервис создаёт свою модель:

        from shared.db import Base, IDMixin, TimestampMixin
        from shared.inbox.fields import ProcessedEventFieldsMixin

        class ProcessedEvent(Base, IDMixin, TimestampMixin, ProcessedEventFieldsMixin):
            __tablename__ = 'processed_events'
            __table_args__ = (UniqueConstraint('sender_service', 'idempotency_key', name='uq_inbox_sender_key'),)
    """

    sender_service: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    response_cached: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


# Удобный helper для __table_args__ — если сервис хочет создать UNIQUE-ограничение программно.
def make_sender_key_unique(name: str = 'uq_inbox_sender_key') -> UniqueConstraint:
    return UniqueConstraint('sender_service', 'idempotency_key', name=name)
