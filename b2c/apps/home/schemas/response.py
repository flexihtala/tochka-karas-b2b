from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BannerResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    image_url: str
    link_url: str
    priority: int
    is_active: bool
    schedule_start: datetime | None
    schedule_end: datetime | None
    created_at: datetime
    updated_at: datetime


class CollectionMetaResponseSchema(BaseModel):
    """Возврат метаданных подборки (без товаров) для `GET /home/collections`."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    description: str | None
    position: int


class CollectionProductItemSchema(BaseModel):
    """Один товар, обогащённый из b2b."""

    id: UUID
    title: str
    slug: str
    price: float | None = None
    image_url: str | None = None


class CollectionProductsResponseSchema(BaseModel):
    """Ответ `GET /home/collections/{id}/products`.

    items — обогащённые продукты в порядке `CollectionItem.ordering`.
    unavailable_ids — uuid'ы, которые есть в b2c.collection_items, но b2b их
    не вернул (BLOCKED / удалён / просто не найден).
    """

    items: list[CollectionProductItemSchema]
    unavailable_ids: list[UUID]
