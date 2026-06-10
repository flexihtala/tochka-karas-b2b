from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from apps.inventory.enums import ReserveFailureReason


class ReserveResponseSchema(BaseModel):
    """Успешный ответ POST /inventory/reserve (200).

    Соответствует ReserveResponse в neomarket-protocols/b2b/openapi.yaml:
    required [order_id, status, reserved_at], status='RESERVED'.
    """

    model_config = ConfigDict(from_attributes=True)

    order_id: UUID
    status: str = 'RESERVED'
    reserved_at: datetime


class ReserveFailedItemSchema(BaseModel):
    """Описание SKU, на котором сломалось all-or-nothing-резервирование (для 409 details)."""

    sku_id: UUID
    requested: int
    available: int
    reason: ReserveFailureReason


class UnreserveResponseSchema(BaseModel):
    """Ответ POST /inventory/unreserve.

    Соответствует InventoryOrderResponse в openapi.yaml:
    required [order_id, status, processed_at], status='UNRESERVED'.
    """

    model_config = ConfigDict(from_attributes=True)

    order_id: UUID
    status: str = 'UNRESERVED'
    processed_at: datetime


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
