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
