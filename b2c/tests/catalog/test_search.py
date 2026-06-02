"""US-CAT-02 search tests.

Покрывают DoD:
- test_search_returns_matching_products
- test_short_query_returns_400
- test_special_chars_do_not_break_query
- test_empty_results_returns_200

Мокается только httpx-транспорт (httpx.MockTransport) — use-case, ServiceClient
и валидация поискового запроса работают как в проде.
"""

from uuid import uuid4

import httpx
import pytest

from apps.catalog.clients import B2BCatalogClient
from apps.catalog.errors import InvalidSearchError
from apps.catalog.schemas.request import CatalogFilterSchema
from apps.catalog.use_cases import ListProductsUseCase
from tests.catalog.fakes import make_handler, make_service_client


def _client(handler) -> B2BCatalogClient:
    return B2BCatalogClient(service_client=make_service_client(handler))


@pytest.mark.anyio
async def test_search_returns_matching_products():
    product_id = uuid4()
    image_id = uuid4()
    captured: list[httpx.Request] = []

    handler = make_handler(
        responses={
            'GET /api/v1/catalog/products': (
                200,
                {
                    'items': [
                        {
                            'id': str(product_id),
                            'name': 'Беспроводные наушники Sony',
                            'min_price': 2999000,
                            'has_stock': True,
                            'images': [
                                {
                                    'id': str(image_id),
                                    'url': 'https://x/h.jpg',
                                    'ordering': 0,
                                    'is_main': True,
                                }
                            ],
                        }
                    ],
                    'total_count': 1,
                    'limit': 20,
                    'offset': 0,
                },
            ),
        },
        on_request=lambda r: captured.append(r),
    )
    use_case = ListProductsUseCase(b2b_client=_client(handler))

    result = await use_case(q='наушники')

    assert result.total_count == 1
    assert result.items[0].name == 'Беспроводные наушники Sony'
    # q должен попасть в query string B2B запроса как search.
    assert captured[0].url.params['search'] == 'наушники'


@pytest.mark.anyio
async def test_short_query_returns_400():
    handler = make_handler(responses={})
    use_case = ListProductsUseCase(b2b_client=_client(handler))

    with pytest.raises(InvalidSearchError) as exc_info:
        await use_case(q='ab')

    assert exc_info.value.code == 'INVALID_REQUEST'
    assert exc_info.value.status_code == 400
    assert '3 characters' in exc_info.value.message


@pytest.mark.anyio
async def test_query_too_long_returns_400():
    handler = make_handler(responses={})
    use_case = ListProductsUseCase(b2b_client=_client(handler))

    with pytest.raises(InvalidSearchError) as exc_info:
        await use_case(q='a' * 201)

    assert exc_info.value.code == 'INVALID_REQUEST'
    assert '200 characters' in exc_info.value.message


@pytest.mark.anyio
async def test_special_chars_do_not_break_query():
    """%/_/' и подобные символы проксируются как есть — B2B экранирует их сам.

    Здесь мы проверяем, что use-case не падает на спецсимволах и они доходят до B2B.
    """
    captured: list[httpx.Request] = []
    handler = make_handler(
        responses={
            'GET /api/v1/catalog/products': (
                200,
                {'items': [], 'total_count': 0, 'limit': 20, 'offset': 0},
            ),
        },
        on_request=lambda r: captured.append(r),
    )
    use_case = ListProductsUseCase(b2b_client=_client(handler))

    tricky = "100% O'Reilly_book"
    result = await use_case(q=tricky)

    # Не упало.
    assert result.total_count == 0
    # Передалось без изменений.
    assert captured[0].url.params['search'] == tricky


@pytest.mark.anyio
async def test_empty_results_returns_200():
    handler = make_handler(
        responses={
            'GET /api/v1/catalog/products': (
                200,
                {'items': [], 'total_count': 0, 'limit': 20, 'offset': 0},
            ),
        },
    )
    use_case = ListProductsUseCase(b2b_client=_client(handler))

    result = await use_case(q='unknown_product_xyz')

    assert result.total_count == 0
    assert result.items == []


@pytest.mark.anyio
async def test_search_whitespace_only_skips_search():
    """Только пробелы → ?search в B2B не передаём (эквивалентно отсутствию)."""
    captured: list[httpx.Request] = []
    handler = make_handler(
        responses={
            'GET /api/v1/catalog/products': (
                200,
                {'items': [], 'total_count': 0, 'limit': 20, 'offset': 0},
            ),
        },
        on_request=lambda r: captured.append(r),
    )
    use_case = ListProductsUseCase(b2b_client=_client(handler))

    await use_case(q='   ')

    assert 'search' not in captured[0].url.params


@pytest.mark.anyio
async def test_search_with_category_combined():
    """Канон B2C-2: поиск можно комбинировать с category_id и фильтрами."""
    captured: list[httpx.Request] = []
    handler = make_handler(
        responses={
            'GET /api/v1/catalog/products': (
                200,
                {'items': [], 'total_count': 0, 'limit': 20, 'offset': 0},
            ),
        },
        on_request=lambda r: captured.append(r),
    )
    category_id = uuid4()
    use_case = ListProductsUseCase(b2b_client=_client(handler))

    await use_case(q='наушники', filter=CatalogFilterSchema(category_id=category_id), sort='price_asc')

    assert captured[0].url.params['search'] == 'наушники'
    assert captured[0].url.params['category_id'] == str(category_id)
    assert captured[0].url.params['sort'] == 'price_asc'
