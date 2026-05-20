from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from apps.products.enums import ProductStatus
from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class ProductCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str
    status: ProductStatus = ProductStatus.CREATED
    deleted: bool = False
    blocking_reason_id: UUID | None = None
    moderator_comment: str | None = None


class ProductReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str
    status: ProductStatus
    deleted: bool
    blocking_reason_id: UUID | None
    moderator_comment: str | None
    created_at: datetime
    updated_at: datetime


class ProductUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    seller_id: UUID | None = None
    category_id: UUID | None = None
    title: str | None = None
    slug: str | None = None
    description: str | None = None
    status: ProductStatus | None = None
    deleted: bool | None = None
    blocking_reason_id: UUID | None = None
    moderator_comment: str | None = None


class ProductImageCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    url: str
    ordering: int = 0


class ProductImageReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    url: str
    ordering: int
    created_at: datetime
    updated_at: datetime


class ProductImageUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID | None = None
    url: str | None = None
    ordering: int | None = None


class CharacteristicValueCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    name: str
    value: str


class CharacteristicValueReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    name: str
    value: str
    created_at: datetime
    updated_at: datetime


class CharacteristicValueUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID | None = None
    name: str | None = None
    value: str | None = None
