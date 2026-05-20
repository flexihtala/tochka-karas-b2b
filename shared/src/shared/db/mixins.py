import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column


class IDMixin:
    """UUID id-колонка с PG `gen_random_uuid()` (через pgcrypto) + Python-default."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4,
        server_default=text('gen_random_uuid()'),
    )


class TimestampMixin:
    """created_at/updated_at с timezone, server_default=now()."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
