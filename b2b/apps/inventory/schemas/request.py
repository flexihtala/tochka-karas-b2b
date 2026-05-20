from uuid import UUID

from pydantic import BaseModel, Field


class InventoryItemRequestSchema(BaseModel):
    """Один элемент резервирования/снятия: sku + количество (> 0)."""

    sku_id: UUID
    quantity: int = Field(ge=1)


class ReserveRequestSchema(BaseModel):
    """Тело POST /api/v1/inventory/reserve.

    `idempotency_key` обеспечивает at-most-once семантику: повтор запроса с тем же
    ключом не приводит к повторному списанию (см. apps/inbox/models.py
    UNIQUE(sender_service, idempotency_key)).
    """

    idempotency_key: UUID
    items: list[InventoryItemRequestSchema] = Field(min_length=1)


class UnreserveRequestSchema(BaseModel):
    """Тело POST /api/v1/inventory/unreserve.

    Идемпотентность реализована через `idempotency_key` (UUID). Канон допускает
    также order_id-based идемпотентность; здесь используем единую модель ключа
    через таблицу processed_events.
    """

    idempotency_key: UUID
    items: list[InventoryItemRequestSchema] = Field(min_length=1)


class FulfillRequestSchema(BaseModel):
    """Тело POST /api/v1/inventory/fulfill (US-B2B-10).

    Списание резерва при доставке. Идемпотентность — по `order_id` через таблицу
    `fulfilled_orders` (UNIQUE(order_id, sku_id)); повторный вызов с тем же
    order_id возвращает 200 без изменений (см. apps/inventory/use_cases/fulfill.py
    и ADR-0002).
    """

    order_id: UUID
    items: list[InventoryItemRequestSchema] = Field(min_length=1)
