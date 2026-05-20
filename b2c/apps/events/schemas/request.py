"""Схема входящего события от B2B (POST /api/v1/events/product).

См. canon: b2c-orders-flows.md Flow B2C-12. Запрос имеет единый формат
с полем `event` (enum) — для PRODUCT_BLOCKED / PRODUCT_DELETED / SKU_OUT_OF_STOCK.
Все события несут `product_id` и `sku_ids[]` — обработка по существу одинакова.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductEventType(StrEnum):
    """Поддерживаемые типы событий от B2B на канале /events/product.

    OUT_OF_STOCK не считается отдельным "single-sku" событием — payload идентичен
    BLOCKED/DELETED: указываются sku_ids[]. Это упрощает обработку: один путь
    "пометить эти SKU как недоступные".
    """

    PRODUCT_BLOCKED = 'PRODUCT_BLOCKED'
    PRODUCT_DELETED = 'PRODUCT_DELETED'
    SKU_OUT_OF_STOCK = 'SKU_OUT_OF_STOCK'


class ProductEventRequestSchema(BaseModel):
    """Тело POST /api/v1/events/product."""

    model_config = ConfigDict(extra='ignore')

    idempotency_key: UUID
    event: ProductEventType
    product_id: UUID
    sku_ids: list[UUID] = Field(default_factory=list)
    reason: str | None = None
    date: datetime
