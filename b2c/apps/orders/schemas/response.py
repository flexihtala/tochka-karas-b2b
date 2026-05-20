from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrderItemResponseSchema(BaseModel):
    """Позиция заказа — снапшот product_title/sku_name/unit_price на момент покупки."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku_id: UUID
    product_id: UUID
    product_title: str
    sku_name: str
    quantity: int
    unit_price: int
    line_total: int


class OrderResponseSchema(BaseModel):
    """Детали заказа (POST /orders, GET /orders/{id}, POST /orders/{id}/cancel)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    items: list[OrderItemResponseSchema]
    total_amount: int
    delivery_address: str | None = None
    address_id: UUID | None = None
    payment_method_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class OrderListItemResponseSchema(BaseModel):
    """Краткое представление заказа в списке GET /orders (без раскрытия items)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    total_amount: int
    items_count: int
    created_at: datetime
    updated_at: datetime


class OrderListResponseSchema(BaseModel):
    """Пагинированный список заказов."""

    items: list[OrderListItemResponseSchema]
    total_count: int
    limit: int
    offset: int
