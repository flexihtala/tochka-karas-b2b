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
