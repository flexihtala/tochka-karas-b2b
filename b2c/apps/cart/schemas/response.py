from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.cart.enums import CartValidationIssueType, UnavailableReason


class ImageRefSchema(BaseModel):
    """Ссылка на изображение позиции (OpenAPI ImageRef).

    Берётся первое изображение SKU, иначе первое изображение товара.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    ordering: int


class CartItemResponseSchema(BaseModel):
    """Позиция корзины с обогащением из B2B (OpenAPI CartItem).

    Внутренние поля (id/created_at/updated_at) НЕ отдаются наружу — корзина хранит
    лишь ссылку на SKU, а цена/наличие/название обогащаются из B2B при каждом GET
    (см. Flow B2C-8). `unavailable_reason` и `is_available` ВЫЧИСЛЯЮТСЯ на лету и
    НЕ хранятся в БД.
    """

    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID
    product_id: UUID
    name: str = Field(description='Название "товар + SKU"')
    quantity: int
    unit_price: int = Field(description='Актуальная цена за единицу, копейки')
    line_total: int = Field(description='unit_price * quantity (0 для недоступных)')
    available_quantity: int
    is_available: bool

    sku_code: str | None = None
    unit_price_at_add: int | None = None
    image: ImageRefSchema | None = None
    unavailable_reason: UnavailableReason | None = None


class CartResponseSchema(BaseModel):
    """Корзина целиком: items + агрегаты (OpenAPI CartResponse).

    - items_count — сумма quantity по ВСЕМ строкам.
    - subtotal — сумма line_total ТОЛЬКО доступных позиций (копейки).
    - is_valid — True, если каждая позиция is_available И quantity <= available_quantity.
    """

    model_config = ConfigDict(from_attributes=True)

    items: list[CartItemResponseSchema] = Field(default_factory=list)
    items_count: int = 0
    subtotal: int = 0
    is_valid: bool = True

    id: UUID | None = None
    updated_at: datetime | None = None


class CartValidationIssueSchema(BaseModel):
    """Одна проблема валидации корзины (OpenAPI CartValidationIssue)."""

    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID
    type: CartValidationIssueType
    message: str
    old_value: str | int | None = None
    new_value: str | int | None = None


class CartValidationResponseSchema(BaseModel):
    """Результат POST /api/v1/cart/validate (OpenAPI CartValidationResponse)."""

    model_config = ConfigDict(from_attributes=True)

    is_valid: bool
    cart: CartResponseSchema
    issues: list[CartValidationIssueSchema] = Field(default_factory=list)
