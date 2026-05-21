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
    """Изображение карточки товара/SKU.

    Соответствует `ImageRef` из b2c/openapi.yaml — required: id, url, ordering.
    """

    model_config = ConfigDict(from_attributes=True, extra='ignore')

    id: UUID
    url: str
    ordering: int = 0


class CatalogProductDetailCharacteristicSchema(BaseModel):
    """Характеристика товара/SKU."""

    model_config = ConfigDict(from_attributes=True, extra='ignore')

    name: str
    value: str


class CatalogProductDetailSkuSchema(BaseModel):
    """Витринный SKU. БЕЗ cost_price и reserved_quantity (только seller-view).

    Имя поля остатка — `available_quantity` (спец. b2c/openapi.yaml#CatalogSku):
    "Остаток за вычетом резерва". Дополнительно отдаём вычисляемый `in_stock`
    (= available_quantity > 0) — это не часть спецификации, но удобно UI.
    """

    model_config = ConfigDict(from_attributes=True, extra='ignore')

    id: UUID
    name: str
    price: int = Field(description='Цена в копейках')
    discount: int = Field(default=0, description='Скидка в копейках (0 если нет)')
    image: str | None = None
    available_quantity: int = Field(default=0, description='Остаток за вычетом резерва')
    in_stock: bool = True
    characteristics: list[CatalogProductDetailCharacteristicSchema] = Field(default_factory=list)


class CatalogProductDetailResponseSchema(BaseModel):
    """Карточка товара для B2C — полные данные + список SKU.

    Соответствует `CatalogProductDetail` (= `CatalogProductCard` + description/skus)
    из b2c/openapi.yaml. Required: id, name, min_price, has_stock, images,
    description, skus.

    - `name` — заголовок товара (раньше назывался `title`, переименовано по спец.).
    - `min_price` — минимальная цена среди SKU с остатком (active+available > 0),
      копейки. Если таких SKU нет — 0.
    - `has_stock` — true, если хотя бы у одного SKU available_quantity > 0.
    """

    model_config = ConfigDict(from_attributes=True, extra='ignore')

    id: UUID
    slug: str | None = None
    name: str
    description: str
    status: str | None = None
    min_price: int = Field(default=0, description='Минимальная цена среди SKU с остатком, копейки')
    has_stock: bool = False
    images: list[CatalogProductDetailImageSchema] = Field(default_factory=list)
    characteristics: list[CatalogProductDetailCharacteristicSchema] = Field(default_factory=list)
    skus: list[CatalogProductDetailSkuSchema] = Field(default_factory=list)
