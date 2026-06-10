from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from apps.invoices.enums import InvoiceStatus
from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class InvoiceCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    seller_id: UUID
    status: InvoiceStatus = InvoiceStatus.CREATED


class InvoiceReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    seller_id: UUID
    status: InvoiceStatus
    created_at: datetime
    updated_at: datetime


class InvoiceUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    seller_id: UUID | None = None
    status: InvoiceStatus | None = None


class InvoiceItemCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: UUID
    sku_id: UUID
    quantity: int
    accepted_quantity: int = 0


class InvoiceItemReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: UUID
    sku_id: UUID
    quantity: int
    accepted_quantity: int
    created_at: datetime
    updated_at: datetime


class InvoiceItemUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: UUID | None = None
    sku_id: UUID | None = None
    quantity: int | None = None
    accepted_quantity: int | None = None
