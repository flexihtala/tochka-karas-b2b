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
