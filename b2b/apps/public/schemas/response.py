"""Public (B2C-facing) response schemas.

Принципиальное отличие от seller-схем (apps.products / apps.skus):
- НЕТ `cost_price` (себестоимость — внутренние данные продавца).
- НЕТ `reserved_quantity` (резервы — внутренние данные склада).
- НЕТ `deleted` / `blocking_reason_id` / `moderator_comment` (фильтрация и так
  гарантирует, что в выдаче только видимые товары).

См. спецификацию OpenAPI: ProductPublicResponse / SKUPublicResponse.
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
    active_quantity: int = Field(description='Доступно к продаже')
    article: str | None = None
    images: list[SKUImagePublicResponseSchema] = Field(default_factory=list)
    characteristics: list[CharacteristicPublicResponseSchema] = Field(default_factory=list)


class ProductPublicResponseSchema(BaseModel):
    """Витринная карточка товара для B2C через X-Service-Key.

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
    """Пагинированный ответ витрины."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ProductPublicResponseSchema] = Field(default_factory=list)
    total_count: int
    limit: int
    offset: int
