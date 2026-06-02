"""US-CAT-01 use-case тесты.

Покрывают DoD:
- test_catalog_returns_filtered_sorted_products
- test_facets_return_counts_per_filter_value
- test_invalid_sort_returns_400
- test_b2b_unavailable_returns_502

Архитектура моков: use-case + B2BCatalogClient + ServiceClient запускаются как
в проде — мокается ТОЛЬКО внешний HTTP-транспорт (httpx.MockTransport). Это
гарантирует, что валидация фильтров, проксирование параметров и парсинг ответа
B2B действительно выполняются.
"""

from uuid import uuid4

import httpx
import pytest

from apps.catalog.clients import B2BCatalogClient
from apps.catalog.errors import CatalogUnavailableError, InvalidSortError
from apps.catalog.schemas.request import CatalogFilterSchema
from apps.catalog.use_cases import GetFacetsUseCase, ListProductsUseCase
from tests.catalog.fakes import make_handler, make_service_client


def _make_client(handler) -> B2BCatalogClient:
    return B2BCatalogClient(service_client=make_service_client(handler))


@pytest.mark.anyio
async def test_catalog_returns_filtered_sorted_products():
    category_id = uuid4()
    product_id = uuid4()
    image_id = uuid4()
    captured: list[httpx.Request] = []

    def on_request(request: httpx.Request) -> None:
        captured.append(request)

    handler = make_handler(
        responses={
            'GET /api/v1/catalog/products': (
                200,
                {
                    'items': [
                        {
                            'id': str(product_id),
                            'name': 'iPhone 15',
                            'min_price': 12999000,
                            'has_stock': True,
                            'images': [
                                {
                                    'id': str(image_id),
                                    'url': 'https://cdn/iphone.jpg',
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
        on_request=on_request,
    )
    use_case = ListProductsUseCase(b2b_client=_make_client(handler))

    result = await use_case(
        filter=CatalogFilterSchema(category_id=category_id, price_min=1000, price_max=20000000),
        sort='price_asc',
        limit=20,
        offset=0,
    )

    assert result.total_count == 1
    assert result.items[0].id == product_id
    assert result.items[0].name == 'iPhone 15'
    assert result.items[0].min_price == 12999000
    assert result.items[0].has_stock is True
    assert result.items[0].images[0].url == 'https://cdn/iphone.jpg'

    # Параметры действительно ушли в B2B (с маппингом B2C → B2B имён).
    sent = captured[0]
    assert sent.url.params['category_id'] == str(category_id)
    assert sent.url.params['min_price'] == '1000'
    assert sent.url.params['max_price'] == '20000000'
    assert sent.url.params['sort'] == 'price_asc'
    assert sent.headers['X-Service-Key'] == 'test-key'


@pytest.mark.anyio
async def test_facets_return_counts_per_filter_value():
    category_id = uuid4()
    handler = make_handler(
        responses={
            'GET /api/v1/catalog/facets': (
                200,
                {
                    'category_id': str(category_id),
                    'facets': [
                        {
                            'name': 'brand',
                            'values': [
                                {'value': 'Apple', 'count': 124},
                                {'value': 'Samsung', 'count': 98},
                            ],
                        },
                        {
                            'name': 'color',
                            'values': [
                                {'value': 'black', 'count': 60},
                                {'value': 'white', 'count': 40},
                            ],
                        },
                    ],
                },
            ),
        },
    )
    use_case = GetFacetsUseCase(b2b_client=_make_client(handler))

    result = await use_case(category_id=category_id)

    assert result.category_id == category_id
    assert len(result.facets) == 2
    brand = next(f for f in result.facets if f.name == 'brand')
    assert {v.value: v.count for v in brand.values} == {'Apple': 124, 'Samsung': 98}
    color = next(f for f in result.facets if f.name == 'color')
    assert {v.value: v.count for v in color.values} == {'black': 60, 'white': 40}


@pytest.mark.anyio
async def test_invalid_sort_returns_400():
    handler = make_handler(responses={})
    use_case = ListProductsUseCase(b2b_client=_make_client(handler))

    with pytest.raises(InvalidSortError) as exc_info:
        await use_case(sort='not_a_sort')

    err = exc_info.value
    assert err.code == 'INVALID_REQUEST'
    assert err.status_code == 400


@pytest.mark.anyio
async def test_b2b_unavailable_returns_502():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=503, json={'code': 'UPSTREAM', 'message': 'down'})

    use_case = ListProductsUseCase(b2b_client=_make_client(handler))

    with pytest.raises(CatalogUnavailableError) as exc_info:
        await use_case()

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == 'CATALOG_UNAVAILABLE'


@pytest.mark.anyio
async def test_b2b_network_error_returns_502():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('connection refused')

    use_case = ListProductsUseCase(b2b_client=_make_client(handler))

    with pytest.raises(CatalogUnavailableError):
        await use_case()


@pytest.mark.anyio
async def test_catalog_uses_default_sort_popularity_when_omitted():
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
    use_case = ListProductsUseCase(b2b_client=_make_client(handler))

    await use_case()

    # default popularity → маппится в B2B 'popular'.
    assert captured[0].url.params['sort'] == 'popular'


@pytest.mark.anyio
async def test_catalog_empty_filter_sends_no_filter_params():
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
    use_case = ListProductsUseCase(b2b_client=_make_client(handler))

    await use_case(filter=CatalogFilterSchema())

    params = captured[0].url.params
    assert 'category_id' not in params
    assert 'min_price' not in params
    assert 'max_price' not in params
    assert 'seller_id' not in params


@pytest.mark.anyio
async def test_catalog_empty_results_returns_200():
    handler = make_handler(
        responses={
            'GET /api/v1/catalog/products': (
                200,
                {'items': [], 'total_count': 0, 'limit': 20, 'offset': 0},
            ),
        },
    )
    use_case = ListProductsUseCase(b2b_client=_make_client(handler))

    result = await use_case(filter=CatalogFilterSchema(category_id=uuid4()))

    assert result.total_count == 0
    assert result.items == []


def _empty_handler(captured: list[httpx.Request]):
    return make_handler(
        responses={
            'GET /api/v1/catalog/products': (
                200,
                {'items': [], 'total_count': 0, 'limit': 20, 'offset': 0},
            ),
        },
        on_request=lambda r: captured.append(r),
    )


@pytest.mark.anyio
async def test_sort_new_is_accepted():
    """sort=new больше не 400 — маппится в B2B created_desc."""
    captured: list[httpx.Request] = []
    use_case = ListProductsUseCase(b2b_client=_make_client(_empty_handler(captured)))

    result = await use_case(sort='new')

    assert result.total_count == 0
    assert captured[0].url.params['sort'] == 'created_desc'


@pytest.mark.anyio
@pytest.mark.parametrize(
    ('b2c_sort', 'b2b_sort'),
    [
        ('price_asc', 'price_asc'),
        ('price_desc', 'price_desc'),
        ('popularity', 'popular'),
        ('new', 'created_desc'),
    ],
)
async def test_sort_mapping_b2c_to_b2b(b2c_sort, b2b_sort):
    captured: list[httpx.Request] = []
    use_case = ListProductsUseCase(b2b_client=_make_client(_empty_handler(captured)))

    await use_case(sort=b2c_sort)

    assert captured[0].url.params['sort'] == b2b_sort


@pytest.mark.anyio
async def test_q_param_used_for_search():
    """q=phone проксируется в B2B как search=phone."""
    captured: list[httpx.Request] = []
    use_case = ListProductsUseCase(b2b_client=_make_client(_empty_handler(captured)))

    await use_case(q='phone')

    assert captured[0].url.params['search'] == 'phone'
    assert 'q' not in captured[0].url.params


@pytest.mark.anyio
async def test_seller_id_filter_applied():
    """filter[seller_id] доходит до B2B как seller_id."""
    seller_id = uuid4()
    captured: list[httpx.Request] = []
    use_case = ListProductsUseCase(b2b_client=_make_client(_empty_handler(captured)))

    await use_case(filter=CatalogFilterSchema(seller_id=seller_id))

    assert captured[0].url.params['seller_id'] == str(seller_id)


@pytest.mark.anyio
async def test_attributes_filter_applied():
    """filter[attributes][color]=red доходит до B2B как filters[color]=red."""
    captured: list[httpx.Request] = []
    use_case = ListProductsUseCase(b2b_client=_make_client(_empty_handler(captured)))

    await use_case(filter=CatalogFilterSchema(attributes={'color': 'red'}))

    assert captured[0].url.params['filters[color]'] == 'red'


@pytest.mark.anyio
async def test_attributes_filter_multi_value_applied():
    """Список значений атрибута → несколько filters[key]=... (deepObject explode)."""
    captured: list[httpx.Request] = []
    use_case = ListProductsUseCase(b2b_client=_make_client(_empty_handler(captured)))

    await use_case(filter=CatalogFilterSchema(attributes={'color': ['red', 'blue']}))

    values = captured[0].url.params.get_list('filters[color]')
    assert values == ['red', 'blue']


@pytest.mark.anyio
async def test_price_filters_mapped_to_min_max_price():
    """filter[price_min]/filter[price_max] → min_price/max_price."""
    captured: list[httpx.Request] = []
    use_case = ListProductsUseCase(b2b_client=_make_client(_empty_handler(captured)))

    await use_case(filter=CatalogFilterSchema(price_min=10000, price_max=50000))

    assert captured[0].url.params['min_price'] == '10000'
    assert captured[0].url.params['max_price'] == '50000'
