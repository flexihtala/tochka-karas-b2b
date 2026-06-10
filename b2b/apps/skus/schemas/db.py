from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class SKUCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    name: str
    price: int
    cost_price: int | None = None
    discount: int = 0
    article: str | None = None
    active_quantity: int = 0
    reserved_quantity: int = 0


class SKUReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    name: str
    price: int
    cost_price: int | None
    discount: int
    article: str | None
    active_quantity: int
    reserved_quantity: int
    stock_quantity: int
    created_at: datetime
    updated_at: datetime


class SKUUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID | None = None
    name: str | None = None
    price: int | None = None
    cost_price: int | None = None
    discount: int | None = None
    article: str | None = None
    active_quantity: int | None = None
    reserved_quantity: int | None = None


class SKUImageCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID
    url: str
    ordering: int = 0


class SKUImageReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID
    url: str
    ordering: int
    created_at: datetime
    updated_at: datetime


class SKUImageUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID | None = None
    url: str | None = None
    ordering: int | None = None


class SKUCharacteristicValueCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID
    name: str
    value: str


class SKUCharacteristicValueReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID
    name: str
    value: str
    created_at: datetime
    updated_at: datetime


class SKUCharacteristicValueUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID | None = None
    name: str | None = None
    value: str | None = None
