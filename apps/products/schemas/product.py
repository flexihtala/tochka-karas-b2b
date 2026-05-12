from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from apps.products.enums import ProductStatus
from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class ProductImageCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    url: str
    ordering: int


class ProductImageReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    url: str
    ordering: int


class ProductCharacteristicCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    name: str
    value: str


class ProductCharacteristicReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    name: str
    value: str


class ProductCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    seller_id: UUID
    title: str
    description: str
    status: ProductStatus
    deleted: bool = False
    blocked: bool = False
    category_id: UUID


class ProductReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    seller_id: UUID
    title: str
    description: str
    status: ProductStatus
    deleted: bool
    blocked: bool
    category_id: UUID
    created_at: datetime
    updated_at: datetime


class ProductUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    title: str | None = None
    description: str | None = None
    status: ProductStatus | None = None
    deleted: bool | None = None
    blocked: bool | None = None
    category_id: UUID | None = None


class ProductImageUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID | None = None
    url: str | None = None
    ordering: int | None = None


class ProductCharacteristicUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID | None = None
    name: str | None = None
    value: str | None = None
