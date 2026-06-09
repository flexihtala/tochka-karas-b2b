from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class CartCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID | None = None
    session_id: str | None = None


class CartReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID | None
    session_id: str | None
    created_at: datetime
    updated_at: datetime


class CartUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID | None = None
    session_id: str | None = None


class CartItemCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    cart_id: UUID
    sku_id: UUID
    product_id: UUID | None = None
    quantity: int


class CartItemReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    cart_id: UUID
    sku_id: UUID
    product_id: UUID | None
    quantity: int
    created_at: datetime
    updated_at: datetime


class CartItemUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    cart_id: UUID | None = None
    sku_id: UUID | None = None
    product_id: UUID | None = None
    quantity: int | None = None
