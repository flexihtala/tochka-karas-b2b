"""US-CAT-01 (B2B side): GET /public/facets — фасеты витрины для B2C.

Считает счётчики по характеристикам (CharacteristicValue) и диапазон цен для
видимых товаров (status == MODERATED, not deleted, есть SKU active_quantity > 0),
отфильтрованных переданными параметрами. B2C проксирует сюда свой /catalog/facets.

Группирует плоский список (name, value, count) из репозитория в фасеты:
    [{name, values: [{value, count}, ...]}, ...] + price_range {min, max}.
"""

from typing import Protocol
from uuid import UUID

from apps.public.schemas.response import (
    FacetPriceRangePublicResponseSchema,
    FacetPublicResponseSchema,
    FacetsPublicResponseSchema,
    FacetValuePublicResponseSchema,
)


class _FacetsRepositoryProtocol(Protocol):
    async def aggregate_facets(
        self,
        *,
        category_id: UUID | None = None,
        search: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        seller_id: UUID | None = None,
    ) -> tuple[list[tuple[str, str, int]], tuple[int, int]]: ...


class GetFacetsUseCase:
    """GET /public/facets — фасеты по характеристикам + диапазон цен."""

    def __init__(self, repository: _FacetsRepositoryProtocol):
        self.repository = repository

    async def __call__(
        self,
        *,
        category_id: UUID | None = None,
        search: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        seller_id: UUID | None = None,
    ) -> FacetsPublicResponseSchema:
        rows, (price_min, price_max) = await self.repository.aggregate_facets(
            category_id=category_id,
            search=search,
            min_price=min_price,
            max_price=max_price,
            seller_id=seller_id,
        )

        # Группируем (name, value, count) в фасеты, сохраняя порядок появления name
        # (репозиторий уже отсортировал по name, затем по count desc).
        facets: list[FacetPublicResponseSchema] = []
        index_by_name: dict[str, int] = {}
        for name, value, count in rows:
            if name not in index_by_name:
                index_by_name[name] = len(facets)
                facets.append(FacetPublicResponseSchema(name=name, values=[]))
            facets[index_by_name[name]].values.append(FacetValuePublicResponseSchema(value=value, count=count))

        return FacetsPublicResponseSchema(
            facets=facets,
            price_range=FacetPriceRangePublicResponseSchema(min=price_min, max=price_max),
        )
