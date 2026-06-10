"""Pydantic-схемы входящего канала POST /api/v1/b2b/events.

Канон: `neomarket-moderation.yaml` (IncomingB2BEvent, EventProductCreated, etc.).
event_type принимает протокольные значения PRODUCT_CREATED / PRODUCT_EDITED /
PRODUCT_DELETED — соответствуют спеке.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class B2BEventTypeEnum(StrEnum):
    PRODUCT_CREATED = 'PRODUCT_CREATED'
    PRODUCT_EDITED = 'PRODUCT_EDITED'
    PRODUCT_DELETED = 'PRODUCT_DELETED'


class B2BEventPayloadSchema(BaseModel):
    """Полезная нагрузка события. Все поля кроме product_id опциональны — конкретные
    обязательные поля зависят от event_type (валидация в use-case):

    - PRODUCT_CREATED требует seller_id + json_after
    - PRODUCT_EDITED  требует seller_id + json_before + json_after
    - PRODUCT_DELETED требует только product_id
    """

    model_config = ConfigDict(extra='allow')

    product_id: UUID
    seller_id: UUID | None = None
    category_id: UUID | None = None
    queue_priority: int | None = Field(default=None, ge=1, le=4)
    json_before: dict[str, Any] | None = None
    json_after: dict[str, Any] | None = None


class IncomingB2BEventSchema(BaseModel):
    """Входящее событие от B2B → Moderation.

    Идемпотентность: idempotency_key фиксируется в processed_events до мутаций
    тикетов; повтор с тем же ключом → 409 DUPLICATE_EVENT (см. HandleB2BEventUseCase).
    """

    event_type: B2BEventTypeEnum
    idempotency_key: UUID
    occurred_at: datetime
    payload: B2BEventPayloadSchema
