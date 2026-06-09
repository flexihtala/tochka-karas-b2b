from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class ModerationEventType(StrEnum):
    """Типы событий от Moderation-сервиса (см. neomarket-b2b.yaml `ModerationEventType`)."""

    MODERATED = 'MODERATED'
    BLOCKED = 'BLOCKED'


class FieldReportSchema(BaseModel):
    """Замечание модератора по конкретному полю товара/SKU.

    См. `FieldReport` в neomarket-b2b.yaml: модератор может указать поле,
    к которому относится замечание (description, images[0], характеристика и т.д.)
    и опционально привязать sku_id.
    """

    field_name: str = Field(min_length=1, max_length=255)
    sku_id: UUID | None = None
    comment: str = Field(min_length=1, max_length=4096)


class ModerationEventRequestSchema(BaseModel):
    """Входящее событие от Moderation Service.

    `event_type` соответствует полю `event_type` из `ModerationEventRequest`
    в neomarket-b2b.yaml. При `BLOCKED` `blocking_reason_id` обязателен;
    `hard_block=true` переводит товар в терминальный статус HARD_BLOCKED.
    """

    idempotency_key: UUID
    product_id: UUID
    event_type: ModerationEventType
    moderator_id: UUID | None = None
    moderator_comment: str | None = Field(default=None, max_length=4096)
    blocking_reason_id: UUID | None = None
    hard_block: bool = False
    field_reports: list[FieldReportSchema] | None = None
    occurred_at: datetime
