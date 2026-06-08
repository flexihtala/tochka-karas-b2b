import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class Ticket(IDMixin, TimestampMixin, Base):
    """Минимальная M3-версия модели тикета модерации.

    M2 (параллельный агент) расширит модель queue_priority, json_before/json_after,
    blocking_reasons, history и т.д. — в M3 храним только базовые поля, нужные
    для входящих B2B-событий и статистики.

    product_id намеренно НЕ UNIQUE — для одного товара может быть несколько
    закрытых (ARCHIVED) тикетов в истории; одновременно активным предполагается
    один PENDING/IN_REVIEW, но enforce-им это в use-case-логике, а не constraint'ом.
    """

    __tablename__ = 'tickets'

    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    seller_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocking_reason_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    moderator_comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        product_id: uuid.UUID,
        seller_id: uuid.UUID,
        status: str,
        claimed_by: uuid.UUID | None = None,
        claimed_at: datetime | None = None,
        blocking_reason_id: uuid.UUID | None = None,
        moderator_comment: str | None = None,
    ):
        if id is not None:
            self.id = id
        self.product_id = product_id
        self.seller_id = seller_id
        self.status = status
        self.claimed_by = claimed_by
        self.claimed_at = claimed_at
        self.blocking_reason_id = blocking_reason_id
        self.moderator_comment = moderator_comment
