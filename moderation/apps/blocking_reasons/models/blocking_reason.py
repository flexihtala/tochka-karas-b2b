import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class BlockingReason(IDMixin, TimestampMixin, Base):
    """Справочник причин блокировки (`product_blocking_reasons` в каноне).

    По спеке `neomarket-moderation.yaml`:
    - code: стабильный машинный идентификатор (^[A-Z_]+$, например FORBIDDEN_GOODS)
    - title: человекочитаемое название
    - description: пояснение (опционально)
    - hard_block: тип блокировки (true → HARD_BLOCKED терминальный)

    is_active — soft-delete флаг для DELETE без потери ссылок из исторических тикетов.
    """

    __tablename__ = 'blocking_reasons'

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    hard_block: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default='true')

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        code: str,
        title: str,
        description: str | None = None,
        hard_block: bool = False,
        is_active: bool = True,
    ):
        if id is not None:
            self.id = id
        self.code = code
        self.title = title
        self.description = description
        self.hard_block = hard_block
        self.is_active = is_active
