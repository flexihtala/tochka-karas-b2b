"""US-CAT-01 + US-CAT-02: листинг товаров с deepObject-фильтрами, сортировкой и поиском.

Проксирует запрос в B2B public-каталог. B2C не хранит товары
(canon b2c-catalog-flows.md).

Маппинг параметров B2C → B2B (proxy-слой)
-----------------------------------------
B2C-контракт (b2c/openapi.yaml) и B2B-контракт (b2b public/products) имеют
разные имена параметров, поэтому use-case транслирует их при формировании
исходящего запроса:

    B2C (вход)                         → B2B (исходящий запрос)
    -----------------------------------  --------------------------------
    q                                  → search
    filter[category_id]                → category_id
    filter[price_min]                  → min_price
    filter[price_max]                  → max_price
    filter[seller_id]                  → seller_id
    filter[attributes][<k>]=<v>        → filters[<k>]=<v>   (deepObject)
    sort=price_asc                     → sort=price_asc
    sort=price_desc                    → sort=price_desc
    sort=popularity                    → sort=popular
    sort=new                           → sort=created_desc

`filters[<k>]` отправляется как несколько query-параметров с bracket-ключами —
httpx сериализует список значений как `filters[k]=a&filters[k]=b`, что и есть
deepObject explode=true, ожидаемый B2B.
"""

from enum import StrEnum
from typing import Any

from apps.catalog.clients import B2BCatalogClient
from apps.catalog.errors import CatalogUnavailableError, InvalidSearchError, InvalidSortError
from apps.catalog.schemas.request import CatalogFilterSchema
from apps.catalog.schemas.response import CatalogPaginatedResponseSchema
from shared.http_clients import ServiceClientError


class ProductSort(StrEnum):
    """Допустимые значения параметра sort (b2c/openapi.yaml#/catalog/products).

    enum: [price_asc, price_desc, popularity, new], default popularity.
    """

    PRICE_ASC = 'price_asc'
    PRICE_DESC = 'price_desc'
    POPULARITY = 'popularity'
    NEW = 'new'


# Маппинг B2C sort → B2B sort enum (b2b public/products: price_asc, price_desc,
# created_desc, popular).
_SORT_B2C_TO_B2B: dict[ProductSort, str] = {
    ProductSort.PRICE_ASC: 'price_asc',
    ProductSort.PRICE_DESC: 'price_desc',
    ProductSort.POPULARITY: 'popular',
    ProductSort.NEW: 'created_desc',
}

DEFAULT_SORT = ProductSort.POPULARITY


class ListProductsUseCase:
    """GET /api/v1/catalog/products — листинг каталога с фильтрами/сортировкой/поиском."""

    DEFAULT_LIMIT = 20
    MAX_LIMIT = 100
    SEARCH_MIN_LENGTH = 3
    SEARCH_MAX_LENGTH = 200

    def __init__(self, b2b_client: B2BCatalogClient):
        self.b2b_client = b2b_client

    async def __call__(
        self,
        *,
        filter: CatalogFilterSchema | None = None,
        sort: str | None = None,
        q: str | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> CatalogPaginatedResponseSchema:
        catalog_filter = filter if filter is not None else CatalogFilterSchema()
        sort_value = self._validate_sort(sort)
        search_value = self._validate_search(q)

        limit = max(1, min(limit, self.MAX_LIMIT))
        offset = max(0, offset)

        params = self._build_b2b_params(
            catalog_filter=catalog_filter,
            sort_value=sort_value,
            search_value=search_value,
            limit=limit,
            offset=offset,
        )

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
    def _build_b2b_params(
        *,
        catalog_filter: CatalogFilterSchema,
        sort_value: str,
        search_value: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        """Транслирует B2C-параметры в имена/формат B2B public-каталога."""
        params: dict[str, Any] = {
            'limit': limit,
            'offset': offset,
            'sort': sort_value,
        }
        if search_value is not None:
            params['search'] = search_value
        if catalog_filter.category_id is not None:
            params['category_id'] = str(catalog_filter.category_id)
        if catalog_filter.price_min is not None:
            params['min_price'] = catalog_filter.price_min
        if catalog_filter.price_max is not None:
            params['max_price'] = catalog_filter.price_max
        if catalog_filter.seller_id is not None:
            params['seller_id'] = str(catalog_filter.seller_id)
        for attr_key, attr_value in catalog_filter.attributes.items():
            # filter[attributes][color]=red → filters[color]=red (deepObject).
            params[f'filters[{attr_key}]'] = attr_value
        return params

    @staticmethod
    def _validate_sort(sort: str | None) -> str:
        if sort is None:
            return _SORT_B2C_TO_B2B[DEFAULT_SORT]
        try:
            parsed = ProductSort(sort)
        except ValueError as exc:
            raise InvalidSortError() from exc
        return _SORT_B2C_TO_B2B[parsed]

    @classmethod
    def _validate_search(cls, search: str | None) -> str | None:
        """Валидация ?q.

        - None / пустая строка → пропуск поиска (None).
        - 1..2 символа → 400.
        - > 200 символов → 400 (maxLength по spec).
        - Спецсимволы (`%`, `_`, `'`) — НЕ режутся здесь: проксируем как есть,
          B2B экранирует на своей стороне перед SQL LIKE.
        """
        if search is None:
            return None
        if search.strip() == '':
            return None
        if len(search) < cls.SEARCH_MIN_LENGTH:
            raise InvalidSearchError(message=f'Search query must be at least {cls.SEARCH_MIN_LENGTH} characters')
        if len(search) > cls.SEARCH_MAX_LENGTH:
            raise InvalidSearchError(message=f'Search query must be at most {cls.SEARCH_MAX_LENGTH} characters')
        return search
