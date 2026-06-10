from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class BannerCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    title: str
    image_url: str
    link_url: str
    priority: int = 0
    is_active: bool = True
    schedule_start: datetime | None = None
    schedule_end: datetime | None = None


class BannerReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    title: str
    image_url: str
    link_url: str
    priority: int
    is_active: bool
    schedule_start: datetime | None
    schedule_end: datetime | None
    created_at: datetime
    updated_at: datetime


class BannerUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    title: str | None = None
    image_url: str | None = None
    link_url: str | None = None
    priority: int | None = None
    is_active: bool | None = None
    schedule_start: datetime | None = None
    schedule_end: datetime | None = None


class BannerClickCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    banner_id: UUID
    user_id: UUID | None = None


class BannerClickReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    banner_id: UUID
    user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class BannerClickUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    banner_id: UUID | None = None
    user_id: UUID | None = None


class CollectionCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    description: str | None = None
    position: int = 0
    is_active: bool = True


class CollectionReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    description: str | None
    position: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CollectionUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    slug: str | None = None
    title: str | None = None
    description: str | None = None
    position: int | None = None
    is_active: bool | None = None


class CollectionItemCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    collection_id: UUID
    product_id: UUID
    ordering: int = 0


class CollectionItemReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    collection_id: UUID
    product_id: UUID
    ordering: int
    created_at: datetime
    updated_at: datetime


class CollectionItemUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    collection_id: UUID | None = None
    product_id: UUID | None = None
    ordering: int | None = None
