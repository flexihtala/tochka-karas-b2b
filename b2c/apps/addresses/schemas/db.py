from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class AddressCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    buyer_id: UUID
    country: str
    city: str
    street: str
    postal_code: str
    comment: str | None = None
    is_default: bool = False


class AddressReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    buyer_id: UUID
    country: str
    city: str
    street: str
    postal_code: str
    comment: str | None
    is_default: bool
    created_at: datetime
    updated_at: datetime


class AddressUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    buyer_id: UUID | None = None
    country: str | None = None
    city: str | None = None
    street: str | None = None
    postal_code: str | None = None
    comment: str | None = None
    is_default: bool | None = None
