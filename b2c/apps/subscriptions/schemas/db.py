from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class SubscriptionCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    product_id: UUID
    notify_on: list[str]


class SubscriptionReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    product_id: UUID
    notify_on: list[str]
    created_at: datetime
    updated_at: datetime


class SubscriptionUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    notify_on: list[str] | None = None
