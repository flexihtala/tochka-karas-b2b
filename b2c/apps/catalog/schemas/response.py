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


# ----------------------- B2C-3: Карточка товара ---------------------------


class CatalogProductDetailImageSchema(BaseModel):
    """Изображение карточки товара/SKU."""

    model_config = ConfigDict(from_attributes=True, extra='ignore')

    url: str
    ordering: int = 0


class CatalogProductDetailCharacteristicSchema(BaseModel):
    """Характеристика товара/SKU."""

    model_config = ConfigDict(from_attributes=True, extra='ignore')

    name: str
    value: str


class CatalogProductDetailSkuSchema(BaseModel):
    """Витринный SKU. БЕЗ cost_price и reserved_quantity (только seller-view).

    `in_stock` — true, если active_quantity > 0. Также пробрасывается active_quantity
    для UI (показать "осталось 3 шт.").
    """

    model_config = ConfigDict(from_attributes=True, extra='ignore')

    id: UUID
    name: str
    price: int = Field(description='Цена в копейках')
    discount: int = Field(default=0, description='Скидка в копейках (0 если нет)')
    image: str | None = None
    active_quantity: int = 0
    in_stock: bool = True
    characteristics: list[CatalogProductDetailCharacteristicSchema] = Field(default_factory=list)


class CatalogProductDetailResponseSchema(BaseModel):
    """Карточка товара для B2C — полные данные + список SKU."""

    model_config = ConfigDict(from_attributes=True, extra='ignore')

    id: UUID
    slug: str | None = None
    title: str
    description: str
    status: str | None = None
    images: list[CatalogProductDetailImageSchema] = Field(default_factory=list)
    characteristics: list[CatalogProductDetailCharacteristicSchema] = Field(default_factory=list)
    skus: list[CatalogProductDetailSkuSchema] = Field(default_factory=list)
