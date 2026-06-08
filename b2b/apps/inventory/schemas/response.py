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
