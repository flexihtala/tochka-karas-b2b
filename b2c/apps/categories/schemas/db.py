from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class CategoryCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    parent_id: UUID | None = None
    ordering: int = 0


class CategoryReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    parent_id: UUID | None
    ordering: int
    created_at: datetime
    updated_at: datetime


class CategoryUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    name: str | None = None
    slug: str | None = None
    parent_id: UUID | None = None
    ordering: int | None = None
