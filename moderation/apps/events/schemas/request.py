"""Pydantic-схемы входящего канала POST /api/v1/b2b/events.

Канон: `neomarket-moderation.yaml` (IncomingB2BEvent, EventProductCreated, etc.) +
`moderation-flows.md` MOD-1.

Мы принимаем три типа событий: CREATED, EDITED, DELETED. Названия упрощены
относительно протокольных PRODUCT_CREATED/... — спека и canon на этот счёт расходятся,
здесь следуем формулировке таска (CREATED/EDITED/DELETED).
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class B2BEventTypeEnum(StrEnum):
    CREATED = 'CREATED'
    EDITED = 'EDITED'
    DELETED = 'DELETED'


class B2BEventPayloadSchema(BaseModel):
    """Полезная нагрузка события. Все поля опциональны — конкретные поля зависят от
    event_type, валидируем в use-case.
    """

    model_config = ConfigDict(extra='allow')

    product_id: UUID
    seller_id: UUID | None = None
    category_id: UUID | None = None
    queue_priority: int | None = None
    json_before: dict[str, Any] | None = None
    json_after: dict[str, Any] | None = None


class IncomingB2BEventSchema(BaseModel):
    """Входящее событие от B2B → Moderation.

    Идемпотентность гарантируется по (sender_service=b2b, idempotency_key).
    """

    event_type: B2BEventTypeEnum
    idempotency_key: UUID
    occurred_at: datetime
    payload: B2BEventPayloadSchema
