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

    Отличается от ProductResponseSchema:
    - нет description/characteristics/skus (только агрегаты skus_count и total_active_quantity);
    - images приходят как минимальный набор для превью карточки.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    status: ProductStatus
    deleted: bool
    images: list[ProductImageResponseSchema] = Field(default_factory=list)
    skus_count: int = 0
    total_active_quantity: int = 0
    created_at: datetime
    updated_at: datetime


class ProductPaginatedResponseSchema(BaseModel):
    """ProductPaginatedResponse из protocols: {items, total_count, limit, offset}."""

    items: list[ProductListItemResponseSchema] = Field(default_factory=list)
    total_count: int
    limit: int
    offset: int
