from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TicketCreateSchema(BaseModel):
    """DB-layer create schema для Ticket."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    product_id: UUID
    seller_id: UUID
    status: str
    claimed_by: UUID | None = None
    claimed_at: datetime | None = None
    blocking_reason_id: UUID | None = None
    moderator_comment: str | None = None


class TicketReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    seller_id: UUID
    status: str
    claimed_by: UUID | None
    claimed_at: datetime | None
    blocking_reason_id: UUID | None
    moderator_comment: str | None
    created_at: datetime
    updated_at: datetime


class TicketUpdateSchema(BaseModel):
    """DB-layer update schema. id обязателен, остальные поля опциональны (partial update)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str | None = None
    claimed_by: UUID | None = None
    claimed_at: datetime | None = None
    blocking_reason_id: UUID | None = None
    moderator_comment: str | None = None
