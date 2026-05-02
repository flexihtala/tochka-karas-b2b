from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.products.enums import ProductStatus


class ProductImageResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    ordering: int


class ProductCharacteristicResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    value: str


class ProductSKUResponseSchema(BaseModel):
    id: UUID
    name: str
    price: int
    stock_quantity: int
    article: str


class ProductResponseSchema(BaseModel):
    id: UUID
    seller_id: UUID
    category_id: UUID
    title: str
    description: str
    status: ProductStatus
    images: list[ProductImageResponseSchema]
    characteristics: list[ProductCharacteristicResponseSchema]
    skus: list[ProductSKUResponseSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
