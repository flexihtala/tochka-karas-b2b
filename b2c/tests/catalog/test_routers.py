"""US-CAT-01 router тесты — listing + facets."""

from uuid import uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.catalog.errors import CatalogUnavailableError, InvalidSearchError, InvalidSortError
from apps.catalog.routers import router as catalog_router
from apps.catalog.schemas.response import (
    CatalogFacetSchema,
    CatalogFacetsResponseSchema,
    CatalogFacetValueSchema,
    CatalogPaginatedResponseSchema,
    CatalogProductCardSchema,
)
from apps.catalog.use_cases import GetFacetsUseCase, ListProductsUseCase
from apps.errors import setup_error_handlers


class StubListProducts:
    def __init__(self):
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.response: CatalogPaginatedResponseSchema | None = None

    async def __call__(self, **kwargs) -> CatalogPaginatedResponseSchema:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response or CatalogPaginatedResponseSchema(
            items=[], total_count=0, limit=20, offset=0,
        )


class StubGetFacets:
    def __init__(self):
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.response: CatalogFacetsResponseSchema | None = None

    async def __call__(self, **kwargs) -> CatalogFacetsResponseSchema:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response or CatalogFacetsResponseSchema(facets=[])


class CatalogRouteProvider(Provider):
    def __init__(self, list_stub: StubListProducts, facets_stub: StubGetFacets):
        super().__init__()
        self.list_stub = list_stub
        self.facets_stub = facets_stub

    @provide(scope=Scope.REQUEST)
    def get_list_use_case(self) -> ListProductsUseCase:
        return self.list_stub  # type: ignore[return-value]

    @provide(scope=Scope.REQUEST)
    def get_facets_use_case(self) -> GetFacetsUseCase:
        return self.facets_stub  # type: ignore[return-value]


def _make_app(list_stub: StubListProducts, facets_stub: StubGetFacets) -> FastAPI:
    app = FastAPI()
    app.include_router(catalog_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        CatalogRouteProvider(list_stub, facets_stub),
    )
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs():
    return StubListProducts(), StubGetFacets()


def test_list_products_returns_200(stubs):
    list_stub, facets_stub = stubs
    product_id = uuid4()
    list_stub.response = CatalogPaginatedResponseSchema(
        items=[
            CatalogProductCardSchema(
                id=product_id,
                title='Test',
                image='https://x.test/i.jpg',
                price=10000,
                in_stock=True,
                is_in_cart=False,
            )
        ],
        total_count=1,
        limit=20,
        offset=0,
    )
    client = TestClient(_make_app(*stubs))

    response = client.get('/api/v1/products?sort=price_asc&category_id=' + str(uuid4()))

    assert response.status_code == 200
    body = response.json()
    assert body['total_count'] == 1
    assert body['items'][0]['id'] == str(product_id)
    assert body['items'][0]['title'] == 'Test'


def test_list_products_invalid_sort_returns_400(stubs):
    list_stub, facets_stub = stubs
    list_stub.error = InvalidSortError()
    client = TestClient(_make_app(*stubs))

    response = client.get('/api/v1/products?sort=not_a_sort')

    assert response.status_code == 400
    body = response.json()
    assert body['code'] == 'INVALID_REQUEST'
    assert 'price_asc' in body['message']


def test_list_products_b2b_unavailable_returns_502(stubs):
    list_stub, facets_stub = stubs
    list_stub.error = CatalogUnavailableError()
    client = TestClient(_make_app(*stubs))

    response = client.get('/api/v1/products')

    assert response.status_code == 502
    body = response.json()
    assert body['code'] == 'CATALOG_UNAVAILABLE'


def test_get_facets_returns_200(stubs):
    list_stub, facets_stub = stubs
    category_id = uuid4()
    facets_stub.response = CatalogFacetsResponseSchema(
        category_id=category_id,
        facets=[
            CatalogFacetSchema(
                name='brand',
                values=[
                    CatalogFacetValueSchema(value='Apple', count=10),
                    CatalogFacetValueSchema(value='Samsung', count=20),
                ],
            )
        ],
    )
    client = TestClient(_make_app(*stubs))

    response = client.get('/api/v1/catalog/facets?category_id=' + str(category_id))

    assert response.status_code == 200
    body = response.json()
    assert body['category_id'] == str(category_id)
    assert body['facets'][0]['name'] == 'brand'
    assert body['facets'][0]['values'][0] == {'value': 'Apple', 'count': 10}


def test_get_facets_b2b_unavailable_returns_502(stubs):
    list_stub, facets_stub = stubs
    facets_stub.error = CatalogUnavailableError()
    client = TestClient(_make_app(*stubs))

    response = client.get('/api/v1/catalog/facets')

    assert response.status_code == 502


def test_list_products_invalid_limit_returns_400(stubs):
    client = TestClient(_make_app(*stubs))

    response = client.get('/api/v1/products?limit=0')

    assert response.status_code == 400
    assert response.json()['code'] == 'INVALID_REQUEST'


def test_list_products_invalid_price_returns_400(stubs):
    client = TestClient(_make_app(*stubs))

    response = client.get('/api/v1/products?price_min=-1')

    assert response.status_code == 400


def test_list_products_short_search_returns_400(stubs):
    list_stub, facets_stub = stubs
    list_stub.error = InvalidSearchError(message='Search query must be at least 3 characters')
    client = TestClient(_make_app(*stubs))

    response = client.get('/api/v1/products?search=ab')

    assert response.status_code == 400
    body = response.json()
    assert body['code'] == 'INVALID_REQUEST'
    assert '3 characters' in body['message']


def test_list_products_with_search_passes_value_to_use_case(stubs):
    list_stub, facets_stub = stubs
    client = TestClient(_make_app(*stubs))

    response = client.get('/api/v1/products?search=наушники')

    assert response.status_code == 200
    assert list_stub.calls[0]['search'] == 'наушники'
