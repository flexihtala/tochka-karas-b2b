"""US-CAT-01 + US-CAT-02: листинг товаров с фильтрами, сортировкой и поиском.

Проксирует запрос в B2B `/api/v1/catalog/products`. B2C не хранит товары
(canon b2c-catalog-flows.md).
"""

from enum import StrEnum
from typing import Any
from uuid import UUID

from apps.catalog.clients import B2BCatalogClient
from apps.catalog.errors import CatalogUnavailableError, InvalidSearchError, InvalidSortError
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
    """GET /api/v1/catalog/products — листинг каталога с фильтрами/сортировкой/поиском."""

    DEFAULT_LIMIT = 20
    MAX_LIMIT = 100
    SEARCH_MIN_LENGTH = 3
    SEARCH_MAX_LENGTH = 255

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
        search_value = self._validate_search(search)

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
        if search_value is not None:
            params['search'] = search_value

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

    @classmethod
    def _validate_search(cls, search: str | None) -> str | None:
        """Валидация ?search.

        - None / пустая строка → пропуск поиска (None).
        - 1..2 символа → 400.
        - > 255 символов → 400.
        - Спецсимволы (`%`, `_`, `'`) — НЕ режутся здесь: проксируем как есть,
          B2B экранирует на своей стороне перед SQL LIKE. Главное — сохраним
          их в URL-параметрах, чтобы B2B получил оригинальный текст.
        """
        if search is None:
            return None
        # Не trim'им: пробелы внутри запроса значимы (фраза). Но "только пробелы"
        # эквивалентны пустой строке.
        if search.strip() == '':
            return None
        if len(search) < cls.SEARCH_MIN_LENGTH:
            raise InvalidSearchError(message=f'Search query must be at least {cls.SEARCH_MIN_LENGTH} characters')
        if len(search) > cls.SEARCH_MAX_LENGTH:
            raise InvalidSearchError(message=f'Search query must be at most {cls.SEARCH_MAX_LENGTH} characters')
        return search
