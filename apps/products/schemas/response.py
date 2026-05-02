from uuid import UUID

from pydantic import BaseModel, Field

from apps.products.enums import ProductStatus


class ProductCategoryResponseSchema(BaseModel):
    id: UUID
    name: str


class ProductImageResponseSchema(BaseModel):
    url: str
    ordering: int


class ProductCharacteristicResponseSchema(BaseModel):
    name: str
    value: str


class ProductResponseSchema(BaseModel):
    id: UUID
    title: str
    description: str
    status: ProductStatus
    deleted: bool
    blocked: bool
    category: ProductCategoryResponseSchema
    images: list[ProductImageResponseSchema]
    characteristics: list[ProductCharacteristicResponseSchema]
    skus: list[dict] = Field(default_factory=list)
