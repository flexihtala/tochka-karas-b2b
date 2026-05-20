from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from apps.tickets.enums import TicketStatus


class TicketResponseSchema(BaseModel):
    """Спека: TicketResponse. В M2 не отдаём json_before/json_after из списка
    (это TicketDetailResponse, deferred). M2 отдаёт компактную карточку.
    """

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
    created_at: datetime
    updated_at: datetime


class TicketListResponseSchema(BaseModel):
    items: list[TicketResponseSchema]
    total_count: int
    limit: int
    offset: int
