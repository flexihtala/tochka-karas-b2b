import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.tickets.enums import TicketKind, TicketStatus
from shared.db import Base, IDMixin, TimestampMixin


class Ticket(IDMixin, TimestampMixin, Base):
    """Тикет модерации — карточка товара, ждущая решения модератора.

    В каноне `product_moderation`. В M2 храним минимально необходимые поля для
    queue/claim/release/approve/block; json_before/json_after доедут позже,
    но колонки уже зарезервированы.

    Жизненный цикл: PENDING ←→ IN_REVIEW → (APPROVED | BLOCKED | HARD_BLOCKED).
    DELETED-событие от b2b переводит в ARCHIVED (deferred).
    """

    __tablename__ = 'tickets'
    __table_args__ = (CheckConstraint('queue_priority BETWEEN 1 AND 4', name='ck_tickets_queue_priority_range'),)

    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True, index=True)
    seller_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default=TicketKind.CREATE.value,
        server_default=TicketKind.CREATE.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TicketStatus.PENDING.value,
        server_default=TicketStatus.PENDING.value,
        index=True,
    )
    queue_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default='3')
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('moderators.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocking_reason_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('blocking_reasons.id', ondelete='RESTRICT'),
        nullable=True,
    )
    moderator_comment: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # Замечания по полям (канон product_moderation_field_report) — JSON-массив на тикете.
    # NOT NULL: «нет замечаний» — это [], не NULL (очищать тоже значением []).
    field_reports: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default='[]')
    json_before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    json_after: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default='{}')

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        product_id: uuid.UUID,
        seller_id: uuid.UUID,
        category_id: uuid.UUID | None = None,
        kind: TicketKind = TicketKind.CREATE,
        status: TicketStatus = TicketStatus.PENDING,
        queue_priority: int = 3,
        claimed_by: uuid.UUID | None = None,
        claimed_at: datetime | None = None,
        claim_expires_at: datetime | None = None,
        decision_at: datetime | None = None,
        blocking_reason_id: uuid.UUID | None = None,
        moderator_comment: str | None = None,
        field_reports: list[dict[str, Any]] | None = None,
        json_before: dict[str, Any] | None = None,
        json_after: dict[str, Any] | None = None,
    ):
        if id is not None:
            self.id = id
        self.product_id = product_id
        self.seller_id = seller_id
        self.category_id = category_id
        self.kind = kind.value if isinstance(kind, TicketKind) else kind
        self.status = status.value if isinstance(status, TicketStatus) else status
        self.queue_priority = queue_priority
        self.claimed_by = claimed_by
        self.claimed_at = claimed_at
        self.claim_expires_at = claim_expires_at
        self.decision_at = decision_at
        self.blocking_reason_id = blocking_reason_id
        self.moderator_comment = moderator_comment
        self.field_reports = field_reports if field_reports is not None else []
        self.json_before = json_before
        self.json_after = json_after if json_after is not None else {}
