from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.products.enums import ProductStatus
from apps.skus.schemas.response import SKUResponseSchema as SKUResponseSchema


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


class BlockingReasonSchema(BaseModel):
    """Причина блокировки товара (openapi BlockingReason: {id, title, comment})."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    comment: str


class FieldReportSchema(BaseModel):
    """Замечание модератора по конкретному полю (openapi FieldReport)."""

    model_config = ConfigDict(from_attributes=True)

    field_name: str
    sku_id: UUID | None = None
    comment: str


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


class ProductDetailResponseSchema(BaseModel):
    """Seller-view карточки товара (openapi ProductDetailResponse).

    Отличается от ProductResponseSchema детализацией блокировки: вместо плоских
    legacy-полей ``blocking_reason_id`` / ``moderator_comment`` отдаёт объект
    ``blocking_reason`` ({id, title, comment}), флаг ``blocked`` и массив
    ``field_reports``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str
    status: ProductStatus
    deleted: bool
    images: list[ProductImageResponseSchema] = Field(default_factory=list)
    characteristics: list[CharacteristicResponseSchema] = Field(default_factory=list)
    skus: list[SKUResponseSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    blocked: bool
    blocking_reason: BlockingReasonSchema | None = None
    field_reports: list[FieldReportSchema] = Field(default_factory=list)


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
