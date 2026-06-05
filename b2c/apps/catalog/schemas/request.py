"""Request-схемы B2C каталога.

`CatalogFilterSchema` соответствует компоненту `CatalogFilter` из
neomarket-protocols b2c/openapi.yaml — deepObject-фильтры листинга
(`?filter[price_min]=...&filter[attributes][color]=red`).
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CatalogFilterSchema(BaseModel):
    """deepObject-фильтры каталога (b2c/openapi.yaml#CatalogFilter).

    Все поля опциональны. `attributes` — динамические характеристики, где
    значение может быть одиночной строкой (`color=red`) либо списком
    (`color=red&color=blue` → `['red', 'blue']`).
    """

    model_config = ConfigDict(extra='forbid')

    category_id: UUID | None = None
    price_min: int | None = Field(default=None, ge=0, description='Минимальная цена в копейках')
    price_max: int | None = Field(default=None, ge=0, description='Максимальная цена в копейках')
    seller_id: UUID | None = None
    attributes: dict[str, str | list[str]] = Field(
        default_factory=dict,
        description='Динамические атрибуты, например color=red, size=[M, L]',
    )

    def is_empty(self) -> bool:
        """True, если ни один фильтр не задан (пустой deepObject)."""
        return (
            self.category_id is None
            and self.price_min is None
            and self.price_max is None
            and self.seller_id is None
            and not self.attributes
        )
