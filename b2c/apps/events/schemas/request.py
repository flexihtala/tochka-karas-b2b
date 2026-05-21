"""Схема входящего события от B2B.

Per spec (neomarket-protocols/b2c/openapi.yaml): POST /api/v1/b2b/events.
Используются спецификационные имена полей: `event_type`, `occurred_at`.
Внутренние имена `event`, `date` приняты как алиасы для обратной совместимости.

Spec types:
- PRODUCT_BLOCKED, PRODUCT_HARD_BLOCKED, PRODUCT_DELETED
- SKU_OUT_OF_STOCK, SKU_BACK_IN_STOCK, PRICE_CHANGED

Текущая реализация обрабатывает базовые BLOCKED/DELETED/OUT_OF_STOCK
(все ведут к пометке SKU/product недоступным). Прочие spec-types принимаются
схемой, но обрабатываются как no-op до отдельной задачи.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ProductEventType(StrEnum):
    """Поддерживаемые типы событий от B2B (per spec b2c openapi.yaml: B2BEvent.event_type)."""

    PRODUCT_BLOCKED = 'PRODUCT_BLOCKED'
    PRODUCT_HARD_BLOCKED = 'PRODUCT_HARD_BLOCKED'
    PRODUCT_DELETED = 'PRODUCT_DELETED'
    SKU_OUT_OF_STOCK = 'SKU_OUT_OF_STOCK'
    SKU_BACK_IN_STOCK = 'SKU_BACK_IN_STOCK'
    PRICE_CHANGED = 'PRICE_CHANGED'


class ProductEventRequestSchema(BaseModel):
    """Тело POST /api/v1/b2b/events.

    Spec (b2c openapi.yaml: B2BEvent): required=[event_type, idempotency_key,
    occurred_at, payload]. Внутри сервиса используем плоскую структуру —
    `event_type`/`occurred_at` — спецификационные имена; `event`/`date` —
    legacy-алиасы. `product_id`/`sku_ids` исторически на верхнем уровне.
    """

    model_config = ConfigDict(extra='ignore', populate_by_name=True)

    idempotency_key: UUID
    event: ProductEventType = Field(validation_alias=AliasChoices('event_type', 'event'))
    product_id: UUID
    sku_ids: list[UUID] = Field(default_factory=list)
    reason: str | None = None
    date: datetime = Field(validation_alias=AliasChoices('occurred_at', 'date'))
