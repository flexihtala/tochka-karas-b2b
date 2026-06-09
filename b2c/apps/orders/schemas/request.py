from uuid import UUID

from pydantic import BaseModel, Field


class OrderItemSnapshotSchema(BaseModel):
    """Одна позиция явного снапшота корзины (spec OrderCreateRequest.items_snapshot[]).

    Опциональная защита от гонок: фронт присылает то, что видел в корзине, а сервер
    сверяет с актуальной корзиной (sku set / quantity / unit_price). Расхождение → 422.
    """

    sku_id: UUID
    quantity: int = Field(ge=1)
    unit_price: int = Field(ge=0)


class OrderCreateRequestSchema(BaseModel):
    """Тело POST /api/v1/orders (checkout, spec OrderCreateRequest).

    Cart-based модель: items берутся из корзины пользователя, НЕ из тела. В теле —
    только адрес доставки, способ оплаты, комментарий и (опционально) items_snapshot.
    Idempotency-Key передаётся ЗАГОЛОВКОМ (не в теле).
    """

    address_id: UUID
    payment_method_id: UUID
    comment: str | None = Field(default=None, max_length=1000)
    items_snapshot: list[OrderItemSnapshotSchema] | None = None


class CancelRequestSchema(BaseModel):
    """Тело POST /api/v1/orders/{order_id}/cancel (опциональное, spec).

    Только причина отмены; всё остальное берётся из заказа. `reason` сохраняется
    в orders.cancel_reason и возвращается в OrderResponse.
    """

    reason: str | None = Field(default=None, max_length=500)
