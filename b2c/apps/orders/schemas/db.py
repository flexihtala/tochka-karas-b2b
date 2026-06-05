from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class OrderCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    status: str
    total_amount: int
    idempotency_key: UUID
    delivery_address: str | None = None
    address_id: UUID | None = None
    payment_method_id: UUID | None = None
    comment: str | None = None
    cancel_reason: str | None = None


class OrderReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    status: str
    total_amount: int
    idempotency_key: UUID
    delivery_address: str | None
    address_id: UUID | None
    payment_method_id: UUID | None
    comment: str | None
    cancel_reason: str | None
    created_at: datetime
    updated_at: datetime


class OrderUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    status: str | None = None
    total_amount: int | None = None
    delivery_address: str | None = None
    address_id: UUID | None = None
    payment_method_id: UUID | None = None
    comment: str | None = None
    cancel_reason: str | None = None


class OrderItemCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    order_id: UUID
    sku_id: UUID
    product_id: UUID
    product_title: str
    sku_name: str
    quantity: int
    unit_price: int
    line_total: int


class OrderItemReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    order_id: UUID
    sku_id: UUID
    product_id: UUID
    product_title: str
    sku_name: str
    quantity: int
    unit_price: int
    line_total: int
    created_at: datetime
    updated_at: datetime


class OrderItemUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    quantity: int | None = None
    unit_price: int | None = None
    line_total: int | None = None
