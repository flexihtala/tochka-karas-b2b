from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.invoices.enums import InvoiceStatus


class InvoiceItemResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku_id: UUID
    quantity: int
    accepted_quantity: int


class InvoiceResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seller_id: UUID
    status: InvoiceStatus
    items: list[InvoiceItemResponseSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    accepted_at: datetime | None = None
    accepted_by: UUID | None = None
