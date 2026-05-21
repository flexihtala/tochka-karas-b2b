"""Response-схемы B2C каталога.

Соответствуют контракту neomarket-protocols/b2c/openapi.yaml — компоненты
CatalogProductCard / PaginatedCatalogProducts. См. canon b2c-catalog-flows.md.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryRefSchema(BaseModel):
    """Ссылка на категорию (b2c/openapi.yaml#CategoryRef)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    parent_id: UUID | None = None
    level: int = Field(ge=0)
    path: list[str] = Field(default_factory=list, description='Хлебные крошки от корня к текущей')


class ImageRefSchema(BaseModel):
    """Изображение товара (b2c/openapi.yaml#ImageRef)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    alt: str | None = None
    ordering: int = Field(ge=0)
    is_main: bool | None = None


class SellerRefSchema(BaseModel):
    """Краткая ссылка на продавца (inline объект в CatalogProductCard)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    display_name: str | None = None


class CatalogProductCardSchema(BaseModel):
    """Карточка товара в листинге каталога.

    Контракт: b2c/openapi.yaml#CatalogProductCard.
    Required: id, name, min_price, has_stock, images.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str | None = None
    category: CategoryRefSchema | None = None
    min_price: int = Field(description='Минимальная цена среди доступных SKU, копейки')
    old_price: int | None = Field(default=None, description='Старая цена (для зачёркивания), копейки')
    has_stock: bool
    rating: float | None = Field(default=None, ge=0, le=5)
    reviews_count: int | None = Field(default=None, ge=0)
    images: list[ImageRefSchema] = Field(default_factory=list)
    seller: SellerRefSchema | None = None


class CatalogPaginatedResponseSchema(BaseModel):
    """Пагинированный листинг товаров (b2c/openapi.yaml#PaginatedCatalogProducts)."""

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
