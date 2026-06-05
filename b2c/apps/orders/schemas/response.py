from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


class OrderItemResponseSchema(BaseModel):
    """Позиция заказа — снапшот product_title/sku_name/unit_price на момент покупки.

    Spec (b2c openapi.yaml): OrderItem.required = [sku_id, product_id, name, quantity,
    unit_price, line_total]. Внутренние имена `product_title`/`sku_name` сериализуются
    под спецификационными именами `name`/`sku_code`.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    sku_id: UUID
    product_id: UUID
    product_title: str = Field(serialization_alias='name')
    sku_name: str | None = Field(default=None, serialization_alias='sku_code')
    quantity: int
    unit_price: int
    line_total: int


class OrderResponseSchema(BaseModel):
    """Детали заказа (POST /orders, GET /orders/{id}, POST /orders/{id}/cancel).

    Spec (b2c openapi.yaml) OrderResponse.required = [id, buyer_id, status, items,
    subtotal, total, address, created_at]. Внутренние имена сериализуются под
    спецификационными: `user_id`->`buyer_id`, `total_amount`->`total`. `subtotal`
    вычисляется как сумма `line_total` по items.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    user_id: UUID | None = Field(default=None, serialization_alias='buyer_id')
    status: str
    items: list[OrderItemResponseSchema]
    total_amount: int = Field(serialization_alias='total')
    delivery_cost: int = 0
    address_id: UUID | None = None
    payment_method_id: UUID | None = None
    delivery_address: str | None = None
    comment: str | None = None
    cancel_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def subtotal(self) -> int:
        return sum(it.line_total for it in self.items)


class OrderListItemResponseSchema(BaseModel):
    """Краткое представление заказа в списке GET /orders (без раскрытия items)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    user_id: UUID | None = Field(default=None, serialization_alias='buyer_id')
    status: str
    total_amount: int = Field(serialization_alias='total')
    items_count: int
    created_at: datetime
    updated_at: datetime


class OrderListResponseSchema(BaseModel):
    """Пагинированный список заказов."""

    items: list[OrderListItemResponseSchema]
    total_count: int
    limit: int
    offset: int
