from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class PaymentMethodCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    buyer_id: UUID
    brand: str
    last4: str
    exp_year: int
    exp_month: int
    is_default: bool = False


class PaymentMethodReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    buyer_id: UUID
    brand: str
    last4: str
    exp_year: int
    exp_month: int
    is_default: bool
    created_at: datetime
    updated_at: datetime


class PaymentMethodUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    buyer_id: UUID | None = None
    brand: str | None = None
    last4: str | None = None
    exp_year: int | None = None
    exp_month: int | None = None
    is_default: bool | None = None
