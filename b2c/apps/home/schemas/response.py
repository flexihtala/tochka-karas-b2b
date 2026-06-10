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
