from uuid import UUID

from pydantic import BaseModel, Field


class CheckoutItemRequestSchema(BaseModel):
    """Один SKU в запросе checkout."""

    sku_id: UUID
    quantity: int = Field(ge=1)


class CheckoutRequestSchema(BaseModel):
    """Тело POST /api/v1/orders (checkout).

    `idempotency_key` — UUID, генерируется фронтом. На повторе с тем же ключом
    возвращается уже созданный заказ (200). Защита от двойного клика.
    """

    idempotency_key: UUID
    items: list[CheckoutItemRequestSchema] = Field(min_length=1)
    address_id: UUID | None = None
    payment_method_id: UUID | None = None


class CancelOrderRequestSchema(BaseModel):
    """Тело POST /api/v1/orders/{order_id}/cancel.

    Per spec (b2c openapi.yaml): optional body with `reason` (maxLength 500).
    """

    reason: str | None = Field(default=None, max_length=500)
