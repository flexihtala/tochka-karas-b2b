from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.inventory.enums import ReserveFailureReason


class ReserveItemResponseSchema(BaseModel):
    """Состояние SKU после успешного резервирования."""

    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID
    reserved_quantity: int
    remaining_stock: int


class ReserveResponseSchema(BaseModel):
    """Успешный ответ POST /inventory/reserve (200).

    Соответствует канону `b2b-flows.md#reserve-sku`.
    """

    reserved: bool = True
    items: list[ReserveItemResponseSchema] = Field(default_factory=list)


class ReserveFailedItemSchema(BaseModel):
    """Описание SKU, на котором сломалось all-or-nothing-резервирование."""

    sku_id: UUID
    requested: int
    available: int
    reason: ReserveFailureReason


class UnreserveResponseSchema(BaseModel):
    """Ответ POST /inventory/unreserve. Канон: `{ok: true}`."""

    ok: bool = True


class FulfillResponseSchema(BaseModel):
    """Ответ POST /inventory/fulfill (US-B2B-10).

    Соответствует InventoryOrderResponse в neomarket-protocols/b2b/openapi.yaml:
    required [order_id, status, processed_at], status='FULFILLED'.

    Повтор по тому же `order_id` — возвращаем кэшированный response.
    """

    model_config = ConfigDict(from_attributes=True)

    order_id: UUID
    status: str = 'FULFILLED'
    processed_at: datetime
