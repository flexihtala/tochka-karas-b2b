"""US-CAT-01 + US-CAT-02: листинг товаров с фильтрами, сортировкой и поиском.

Проксирует запрос в B2B `/api/v1/catalog/products`. B2C не хранит товары
(canon b2c-catalog-flows.md).
"""

from enum import StrEnum
from typing import Any
from uuid import UUID

from apps.catalog.clients import B2BCatalogClient
from apps.catalog.errors import CatalogUnavailableError, InvalidSortError
from apps.catalog.schemas.response import CatalogPaginatedResponseSchema
from shared.http_clients import ServiceClientError


class ProductSort(StrEnum):
    """Допустимые значения параметра sort.

    canon b2c-catalog-flows.md#b2c-1: rating (default), popularity, price_asc,
    price_desc, date_desc, discount_desc.
    """

    RATING = 'rating'
    POPULARITY = 'popularity'
    PRICE_ASC = 'price_asc'
    PRICE_DESC = 'price_desc'
    DATE_DESC = 'date_desc'
    DISCOUNT_DESC = 'discount_desc'


class ListProductsUseCase:
    """GET /api/v1/products — листинг каталога."""

    DEFAULT_LIMIT = 20
    MAX_LIMIT = 100

    def __init__(self, b2b_client: B2BCatalogClient):
        self.b2b_client = b2b_client

    async def __call__(
        self,
        *,
        category_id: UUID | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        sort: str | None = None,
        search: str | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> CatalogPaginatedResponseSchema:
        sort_value = self._validate_sort(sort)

        limit = max(1, min(limit, self.MAX_LIMIT))
        offset = max(0, offset)

        params: dict[str, Any] = {
            'limit': limit,
            'offset': offset,
            'sort': sort_value,
        }
        if category_id is not None:
            params['category_id'] = str(category_id)
        if price_min is not None:
            params['price_min'] = price_min
        if price_max is not None:
            params['price_max'] = price_max
        if search is not None:
            params['search'] = search

        try:
            payload = await self.b2b_client.list_products(params)
        except ServiceClientError as exc:
            if exc.status_code >= 500:
                raise CatalogUnavailableError() from exc
            raise
        except Exception as exc:
            raise CatalogUnavailableError() from exc

        return CatalogPaginatedResponseSchema.model_validate(payload)

    @staticmethod
    def _validate_sort(sort: str | None) -> str:
        if sort is None:
            return ProductSort.RATING.value
        try:
            return ProductSort(sort).value
        except ValueError as exc:
            raise InvalidSortError() from exc
