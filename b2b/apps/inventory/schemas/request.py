from uuid import UUID

from pydantic import BaseModel, Field


class InventoryItemRequestSchema(BaseModel):
    """Один элемент резервирования/снятия: sku + количество (> 0).

    Соответствует InventoryItem в neomarket-protocols/b2b/openapi.yaml.
    """

    sku_id: UUID
    quantity: int = Field(ge=1)


class ReserveRequestSchema(BaseModel):
    """Тело POST /api/v1/inventory/reserve.

    Соответствует ReserveRequest в openapi.yaml: required [idempotency_key, order_id, items].

    `idempotency_key` обеспечивает at-most-once семантику: повтор запроса с тем же
    ключом не приводит к повторному списанию (см. apps/inbox/models.py
    UNIQUE(sender_service, idempotency_key)).
    """

    idempotency_key: UUID
    order_id: UUID
    items: list[InventoryItemRequestSchema] = Field(min_length=1)


class UnreserveRequestSchema(BaseModel):
    """Тело POST /api/v1/inventory/unreserve.

    Соответствует InventoryOrderRequest в openapi.yaml: required [order_id, items].
    Идемпотентность реализована по order_id (канон допускает; для transport-level
    клиент может также передать заголовок Idempotency-Key, который маппится на
    idempotency_key в processed_events).
    """

    order_id: UUID
    items: list[InventoryItemRequestSchema] = Field(min_length=1)
