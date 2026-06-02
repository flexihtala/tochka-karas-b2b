"""Public (B2C-facing) response schemas.

Принципиальное отличие от seller-схем (apps.products / apps.skus):
- НЕТ `cost_price` (себестоимость — внутренние данные продавца).
- НЕТ `reserved_quantity` (резервы — внутренние данные склада).
- НЕТ `deleted` / `blocking_reason_id` / `moderator_comment` (фильтрация и так
  гарантирует, что в выдаче только видимые товары).

См. спецификацию OpenAPI: ProductPublicShortResponse / ProductPublicResponse /
SKUPublicResponse / ProductPublicPaginatedResponse.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.products.enums import ProductStatus


class ProductImagePublicResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    ordering: int


class CharacteristicPublicResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    value: str


class SKUImagePublicResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    ordering: int


class SKUPublicResponseSchema(BaseModel):
    """Витринный SKU. НЕ содержит cost_price и reserved_quantity (только seller-view)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    name: str
    price: int
    discount: int
    stock_quantity: int = Field(description='Всего на складе (active + reserved)')
    active_quantity: int = Field(description='Доступно к продаже')
    article: str | None = None
    images: list[SKUImagePublicResponseSchema] = Field(default_factory=list)
    characteristics: list[CharacteristicPublicResponseSchema] = Field(default_factory=list)


class ProductPublicShortResponseSchema(BaseModel):
    """Короткая витринная карточка товара (для листинга и похожих товаров).

    min_price = минимальная цена среди видимых SKU (active_quantity > 0).
    cover_image = url первого изображения товара (по ordering) или None.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str
    status: ProductStatus
    category_id: UUID
    min_price: int = Field(description='Минимальная цена SKU в копейках')
    cover_image: str | None = None
    created_at: datetime


class ProductPublicResponseSchema(BaseModel):
    """Полная витринная карточка товара для B2C через X-Service-Key.

    НЕ содержит deleted, blocking_reason_id, moderator_comment.
    SKU в response — без cost_price/reserved_quantity.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str
    status: ProductStatus
    images: list[ProductImagePublicResponseSchema] = Field(default_factory=list)
    characteristics: list[CharacteristicPublicResponseSchema] = Field(default_factory=list)
    skus: list[SKUPublicResponseSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProductPublicPaginatedResponseSchema(BaseModel):
    """Пагинированный ответ витрины (короткие карточки)."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ProductPublicShortResponseSchema] = Field(default_factory=list)
    total_count: int
    limit: int
    offset: int
