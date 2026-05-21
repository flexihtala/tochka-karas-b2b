from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.products.enums import ProductStatus


class ProductImageResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    ordering: int


class CharacteristicResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    value: str


class SKUResponseSchema(BaseModel):
    """Stub schema для skus=[] в ответе. Полная SKUResponse будет добавлена в US-B2B-02."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID


class ProductResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str
    status: ProductStatus
    deleted: bool
    blocking_reason_id: UUID | None = None
    moderator_comment: str | None = None
    images: list[ProductImageResponseSchema] = Field(default_factory=list)
    characteristics: list[CharacteristicResponseSchema] = Field(default_factory=list)
    skus: list[SKUResponseSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProductListItemResponseSchema(BaseModel):
    """Краткое представление товара в списке seller cabinet (B2B-11).

    Соответствует ProductShortResponse в neomarket-protocols/b2b/openapi.yaml:
    required [id, title, slug, status, category_id, deleted, created_at];
    optional min_price (nullable), cover_image (nullable).

    Расширения (не входят в spec, дополнительные данные для UI кабинета продавца):
    - seller_id, images[], skus_count, total_active_quantity, updated_at.
    """

    model_config = ConfigDict(from_attributes=True)

    # Поля по спецификации
    id: UUID
    title: str
    slug: str
    status: ProductStatus
    category_id: UUID
    deleted: bool
    created_at: datetime
    min_price: int | None = Field(default=None, description='Минимальная цена SKU в копейках')
    cover_image: str | None = Field(default=None)

    # Расширения для seller UI
    seller_id: UUID
    images: list[ProductImageResponseSchema] = Field(default_factory=list)
    skus_count: int = 0
    total_active_quantity: int = 0
    updated_at: datetime


class ProductPaginatedResponseSchema(BaseModel):
    """ProductPaginatedResponse из protocols: {items, total_count, limit, offset}."""

    items: list[ProductListItemResponseSchema] = Field(default_factory=list)
    total_count: int
    limit: int
    offset: int
