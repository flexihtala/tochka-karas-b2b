from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from apps.tickets.enums import TicketKind, TicketStatus


class TicketResponseSchema(BaseModel):
    """Спека: TicketResponse — соответствует neomarket-moderation.yaml.

    Обязательные поля: id, product_id, seller_id, kind, status, queue_priority, created_at.
    Поле `assigned_moderator_id` (по спеке) принимает значение из БД-колонки `claimed_by`
    через validation_alias — это позволяет ORM-привязке model_validate(orm_model) работать
    без изменения имени колонки в схеме.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    product_id: UUID
    seller_id: UUID
    category_id: UUID | None = None
    kind: TicketKind = TicketKind.CREATE
    status: TicketStatus
    queue_priority: int = Field(ge=1, le=4)
    assigned_moderator_id: UUID | None = Field(
        default=None,
        validation_alias=AliasChoices('assigned_moderator_id', 'claimed_by'),
    )
    claimed_at: datetime | None = None
    claim_expires_at: datetime | None = None
    decision_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class TicketListResponseSchema(BaseModel):
    items: list[TicketResponseSchema]
    total_count: int
    limit: int
    offset: int
