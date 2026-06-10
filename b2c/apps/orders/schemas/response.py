from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from apps.addresses.schemas.response import AddressResponseSchema
from apps.payment_methods.schemas.response import PaymentMethodResponseSchema


class OrderItemResponseSchema(BaseModel):
    """Позиция заказа — снапшот на момент покупки (spec OrderItem).

    `name` композируется как "{product_title} {sku_name}" (внутренние поля
    product_title/sku_name остаются в БД-модели, наружу отдаётся единое `name`).
    `sku_code`/`image_url` пока не хранятся → null.
    """

    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID
    product_id: UUID
    name: str
    sku_code: str | None = None
    quantity: int
    unit_price: int
    line_total: int
    image_url: str | None = None


class OrderResponseSchema(BaseModel):
    """Детали заказа (spec OrderResponse).

    required = [id, buyer_id, status, items, subtotal, total, address, created_at].
    `subtotal` = сумма line_total; `total` = subtotal + delivery_cost.
    `paid_at` = created_at, когда status == PAID. `address`/`payment_method`
    переиспользуют схемы соответствующих app'ов.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: str | None = None
    buyer_id: UUID
    status: str
    items: list[OrderItemResponseSchema]
    subtotal: int
    delivery_cost: int = 0
    total: int
    address: AddressResponseSchema
    payment_method: PaymentMethodResponseSchema | None = None
    comment: str | None = None
    cancel_reason: str | None = None
    created_at: datetime
    paid_at: datetime | None = None


class OrderListItemResponseSchema(BaseModel):
    """Краткое представление заказа в списке GET /orders (без раскрытия items)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    buyer_id: UUID
    status: str
    total: int
    items_count: int
    created_at: datetime


class OrderListResponseSchema(BaseModel):
    """Пагинированный список заказов (spec PaginatedOrders)."""

    items: list[OrderListItemResponseSchema]
    total_count: int
    limit: int
    offset: int
