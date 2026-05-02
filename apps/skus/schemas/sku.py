from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class SKUImageSchema(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    ordering: int = Field(ge=0)


class SKUCharacteristicSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    value: str = Field(min_length=1, max_length=255)


class SKUImageCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID
    url: str
    ordering: int


class SKUImageReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID
    url: str
    ordering: int


class SKUImageUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID | None = None
    url: str | None = None
    ordering: int | None = None


class SKUCharacteristicCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID
    name: str
    value: str


class SKUCharacteristicReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID
    name: str
    value: str


class SKUCharacteristicUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    sku_id: UUID | None = None
    name: str | None = None
    value: str | None = None


class SKUCreateRequestSchema(BaseModel):
    product_id: UUID
    name: str = Field(min_length=1, max_length=255)
    price: int = Field(ge=0)
    stock_quantity: int = Field(ge=0)
    article: str = Field(min_length=1, max_length=255)
    cost_price: int | None = Field(default=None, ge=0)
    discount: int | None = Field(default=None, ge=0)
    images: list[SKUImageSchema] = Field(default_factory=list)
    characteristics: list[SKUCharacteristicSchema] = Field(default_factory=list)


class SKUCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    name: str
    price: int
    stock_quantity: int
    article: str
    cost_price: int | None = None
    discount: int | None = None


class SKUReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    name: str
    price: int
    stock_quantity: int
    article: str
    cost_price: int | None
    discount: int | None
    created_at: datetime
    updated_at: datetime


class SKUUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID | None = None
    name: str | None = None
    price: int | None = None
    stock_quantity: int | None = None
    article: str | None = None
    cost_price: int | None = None
    discount: int | None = None


class SKUImageResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    ordering: int


class SKUCharacteristicResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    value: str


class SKUResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    name: str
    price: int
    stock_quantity: int
    article: str
    cost_price: int | None = None
    discount: int | None = None
    images: list[SKUImageResponseSchema]
    characteristics: list[SKUCharacteristicResponseSchema]
    created_at: datetime
    updated_at: datetime
