from uuid import UUID

from pydantic import ConfigDict

from apps.products.enums import ProductStatus
from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class ProductCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    seller_id: UUID
    title: str
    description: str
    status: ProductStatus
    deleted: bool = False
    blocked: bool = False
    category_id: UUID
    images: list[dict]
    characteristics: list[dict] = []


class ProductReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    seller_id: UUID
    title: str
    description: str
    status: ProductStatus
    deleted: bool
    blocked: bool
    category_id: UUID
    images: list[dict]
    characteristics: list[dict]


class ProductUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    title: str | None = None
    description: str | None = None
    status: ProductStatus | None = None
    deleted: bool | None = None
    blocked: bool | None = None
    category_id: UUID | None = None
    images: list[dict] | None = None
    characteristics: list[dict] | None = None
