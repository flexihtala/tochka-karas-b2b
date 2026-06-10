from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class BannerResponseSchema(BaseModel):
    """Баннер главной (канон B2C-14).

    Канон-форма ответа: {id, title, image_url, link, priority}.
    DB-колонка называется link_url — отдаём как link через alias, без миграции.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    title: str
    image_url: str
    link: str = Field(validation_alias=AliasChoices('link', 'link_url'))
    priority: int


class BannerListResponseSchema(BaseModel):
    """Конверт списка баннеров (канон B2C-14): {items, total_count}.

    Пагинация не нужна (баннеров десятки), но конверт {items, total_count}
    единообразен с остальными листингами B2C и зафиксирован в каноне.
    """

    items: list[BannerResponseSchema]
    total_count: int


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
