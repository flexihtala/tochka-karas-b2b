from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class CategoryCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    name: str
    parent_id: UUID | None = None


class CategoryReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    name: str
    parent_id: UUID | None
    created_at: datetime
    updated_at: datetime


class CategoryUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    name: str | None = None
    parent_id: UUID | None = None
