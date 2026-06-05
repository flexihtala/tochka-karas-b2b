from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.cart.enums import UnavailableReason


class CartItemResponseSchema(BaseModel):
    """Позиция корзины с обогащением из B2B.

    unavailable_reason вычисляется на лету и НЕ хранится в БД (см. Flow B2C-8):
    - BLOCKED       — товар заблокирован модерацией
    - DELETED       — товар удалён продавцом (отсутствует в ответе B2B)
    - OUT_OF_STOCK  — available_quantity == 0

    Для available позиций unavailable_reason == None.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku_id: UUID
    quantity: int
    title: str | None = None
    unit_price: int | None = None
    available_quantity: int | None = None
    line_total: int = 0
    unavailable_reason: UnavailableReason | None = None
    created_at: datetime
    updated_at: datetime


class CartResponseSchema(BaseModel):
    """Корзина целиком: items + агрегаты.

    `total_amount` суммирует только available-позиции (unavailable_reason is None).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None = None
    session_id: str | None = None
    items: list[CartItemResponseSchema] = Field(default_factory=list)
    total_amount: int = 0
    items_count: int = 0
    updated_at: datetime
