"""Response-схемы B2C каталога.

Опираются на canon b2c-catalog-flows.md#b2c-1-catalog-filters.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CatalogProductCardSchema(BaseModel):
    """Краткая карточка товара в листинге каталога (B2C-1)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    image: str | None = None
    price: int = Field(description='Минимальная актуальная цена в копейках')
    in_stock: bool = True
    is_in_cart: bool = False


class CatalogPaginatedResponseSchema(BaseModel):
    """Пагинированный листинг товаров."""

    items: list[CatalogProductCardSchema] = Field(default_factory=list)
    total_count: int
    limit: int
    offset: int


class CatalogFacetValueSchema(BaseModel):
    """Значение фасета и количество товаров под ним."""

    value: str
    count: int


class CatalogFacetSchema(BaseModel):
    """Один фасет (один атрибут с возможными значениями)."""

    name: str
    values: list[CatalogFacetValueSchema] = Field(default_factory=list)


class CatalogFacetsResponseSchema(BaseModel):
    """Ответ /catalog/facets."""

    category_id: UUID | None = None
    facets: list[CatalogFacetSchema] = Field(default_factory=list)
