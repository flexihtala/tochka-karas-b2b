from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class BannerResponseSchema(BaseModel):
    """Баннер главной по unified B2C OpenAPI spec: `GET /catalog/banners`.

    Wire-форма строго по спеке: {id, title?, image_url, link, ordering?, active_from?, active_to?}.
    DB-колонки называются link_url/priority/schedule_start/schedule_end — отдаём
    spec-имена через validation_alias, без миграции.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    title: str | None = None
    image_url: str
    link: str = Field(validation_alias=AliasChoices('link', 'link_url'))
    ordering: int = Field(default=0, validation_alias=AliasChoices('ordering', 'priority'))
    active_from: datetime | None = Field(default=None, validation_alias=AliasChoices('active_from', 'schedule_start'))
    active_to: datetime | None = Field(default=None, validation_alias=AliasChoices('active_to', 'schedule_end'))


class CollectionMetaResponseSchema(BaseModel):
    """Метаданные подборки (без товаров) для `GET /catalog/collections` (US-CART-05).

    Per openapi spec, Collection requires {id, name}. The DB column is `title`;
    `name` is exposed via validation_alias so wire format matches the spec.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    name: str = Field(validation_alias=AliasChoices('name', 'title'))
    description: str | None = None
    slug: str | None = None
    position: int = 0


class CollectionProductItemSchema(BaseModel):
    """Один товар, обогащённый из b2b."""

    id: UUID
    title: str
    slug: str
    price: int | None = None
    image_url: str | None = None


class CollectionProductsResponseSchema(BaseModel):
    """Ответ `GET /catalog/collections/{id}/products` (канон B2C-15).

    items — обогащённые продукты в порядке `CollectionItem.ordering`.
    unavailable_ids — uuid'ы, которые есть в b2c.collection_items, но b2b их
    не вернул (BLOCKED / удалён / просто не найден).
    """

    items: list[CollectionProductItemSchema]
    unavailable_ids: list[UUID]
