"""Mixin с колонками таблицы outbox.

Каждый сервис создаёт свою модель Outbox в собственной MetaData:

    from shared.db import Base, IDMixin, TimestampMixin
    from shared.outbox.fields import OutboxFieldsMixin

    class OutboxEvent(Base, IDMixin, TimestampMixin, OutboxFieldsMixin):
        __tablename__ = 'outbox'

Это позволяет alembic autogenerate каждого сервиса видеть свою таблицу и не
конфликтовать с MetaData других сервисов.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.outbox.enums import OutboxStatus


class OutboxFieldsMixin:
    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_service: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=OutboxStatus.PENDING.value,
        server_default=OutboxStatus.PENDING.value,
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
