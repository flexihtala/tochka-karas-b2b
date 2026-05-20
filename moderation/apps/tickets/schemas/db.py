from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from apps.tickets.enums import TicketStatus


class TicketCreateSchema(BaseModel):
    """DB-layer create schema (используется в seed/тестах и в M3 — обработке b2b-событий)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    product_id: UUID
    seller_id: UUID
    status: TicketStatus = TicketStatus.PENDING
    queue_priority: int = 3
    claimed_by: UUID | None = None
    claimed_at: datetime | None = None
    decision_at: datetime | None = None
    blocking_reason_id: UUID | None = None
    moderator_comment: str | None = None
    json_before: dict[str, Any] | None = None
    json_after: dict[str, Any] | None = None


class TicketReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    seller_id: UUID
    status: TicketStatus
    queue_priority: int
    claimed_by: UUID | None
    claimed_at: datetime | None
    decision_at: datetime | None
    blocking_reason_id: UUID | None
    moderator_comment: str | None
    json_before: dict[str, Any] | None
    json_after: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TicketUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: TicketStatus | None = None
    claimed_by: UUID | None = None
    claimed_at: datetime | None = None
    decision_at: datetime | None = None
    blocking_reason_id: UUID | None = None
    moderator_comment: str | None = None
