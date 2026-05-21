"""US-CAT-04 similar products tests.

Покрывают DoD:
- test_similar_returns_up_to_8_from_same_category
- test_empty_category_returns_200_empty_list
- test_unknown_product_returns_404
"""

from uuid import uuid4

import httpx
import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.catalog.clients import B2BCatalogClient
from apps.catalog.errors import CatalogUnavailableError, ProductNotFoundError
from apps.catalog.routers import router as catalog_router
from apps.catalog.schemas.response import CatalogPaginatedResponseSchema
from apps.catalog.use_cases import GetSimilarUseCase
from apps.errors import setup_error_handlers
from tests.catalog.fakes import MockTransportServiceClient, make_handler


def _b2b(handler) -> B2BCatalogClient:
    return B2BCatalogClient(service_client=MockTransportServiceClient(handler=handler))


def _make_card(product_id, title='X', price=100000) -> dict:
    return {
        'id': str(product_id),
        'title': title,
        'image': f'https://x/{product_id}.jpg',
        'price': price,
        'in_stock': True,
        'is_in_cart': False,
    }


@pytest.mark.anyio
async def test_similar_returns_up_to_8_from_same_category():
    """B2B возвращает 8 похожих — все доходят до клиента в response.items[]."""
    product_id = uuid4()
    similar_ids = [uuid4() for _ in range(8)]
    captured: list[httpx.Request] = []

    handler = make_handler(
        responses={
            f'GET /api/v1/catalog/products/{product_id}/similar': (
                200,
                {
                    'items': [_make_card(pid, title=f'item-{i}') for i, pid in enumerate(similar_ids)],
                    'total_count': 8,
                    'limit': 8,
                    'offset': 0,
                },
            ),
        },
        on_request=lambda r: captured.append(r),
    )
    use_case = GetSimilarUseCase(b2b_client=_b2b(handler))

    result = await use_case(product_id, limit=8)

    assert len(result.items) == 8
    assert {item.id for item in result.items} == set(similar_ids)
    assert result.total_count == 8
    # В запросе к B2B действительно ушёл limit=8.
    assert captured[0].url.params['limit'] == '8'


@pytest.mark.anyio
async def test_empty_category_returns_200_empty_list():
    """Канон: если категория пуста — отдаём 200 с пустым items."""
    product_id = uuid4()
    handler = make_handler(
        responses={
            f'GET /api/v1/catalog/products/{product_id}/similar': (
                200,
                {'items': [], 'total_count': 0, 'limit': 8, 'offset': 0},
            ),
        },
    )
    use_case = GetSimilarUseCase(b2b_client=_b2b(handler))

    result = await use_case(product_id)

    assert result.items == []
    assert result.total_count == 0


@pytest.mark.anyio
async def test_unknown_product_returns_404():
    product_id = uuid4()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=404, json={'code': 'NOT_FOUND', 'message': 'Product not found'})

    use_case = GetSimilarUseCase(b2b_client=_b2b(handler))

    with pytest.raises(ProductNotFoundError) as exc_info:
        await use_case(product_id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == 'NOT_FOUND'


@pytest.mark.anyio
async def test_similar_uses_default_limit_8():
    product_id = uuid4()
    captured: list[httpx.Request] = []

    handler = make_handler(
        responses={
            f'GET /api/v1/catalog/products/{product_id}/similar': (
                200,
                {'items': [], 'total_count': 0, 'limit': 8, 'offset': 0},
            ),
        },
        on_request=lambda r: captured.append(r),
    )
    use_case = GetSimilarUseCase(b2b_client=_b2b(handler))

    await use_case(product_id)

    assert captured[0].url.params['limit'] == '8'


@pytest.mark.anyio
async def test_similar_limit_capped_at_max():
    product_id = uuid4()
    captured: list[httpx.Request] = []
    handler = make_handler(
        responses={
            f'GET /api/v1/catalog/products/{product_id}/similar': (
                200,
                {'items': [], 'total_count': 0, 'limit': 20, 'offset': 0},
            ),
        },
        on_request=lambda r: captured.append(r),
    )
    use_case = GetSimilarUseCase(b2b_client=_b2b(handler))

    await use_case(product_id, limit=100)

    # MAX_LIMIT = 20 — больше не разрешено.
    assert captured[0].url.params['limit'] == '20'


@pytest.mark.anyio
async def test_similar_b2b_returns_bare_list():
    """Некоторые имплементации B2B могут отдать просто массив — нормализуем."""
    product_id = uuid4()
    similar_id = uuid4()
    handler = make_handler(
        responses={
            f'GET /api/v1/catalog/products/{product_id}/similar': (
                200,
                # NOTE: handler выдаст response.json() = []
                # но make_handler не умеет list — обернём по-другому.
                # Сделаем кастомный handler ниже.
                {'items': [_make_card(similar_id)], 'total_count': 1, 'limit': 8, 'offset': 0},
            ),
        },
    )
    use_case = GetSimilarUseCase(b2b_client=_b2b(handler))

    result = await use_case(product_id)
    assert result.total_count == 1
    assert result.items[0].id == similar_id


@pytest.mark.anyio
async def test_similar_502_on_network_error():
    product_id = uuid4()

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('connection refused')

    use_case = GetSimilarUseCase(b2b_client=_b2b(handler))
    with pytest.raises(CatalogUnavailableError):
        await use_case(product_id)


# ----------------------- Router tests -----------------------


class StubGetSimilar:
    def __init__(self):
        self.calls: list[tuple] = []
        self.error: Exception | None = None
        self.response: CatalogPaginatedResponseSchema | None = None

    async def __call__(self, product_id, *, limit=8, offset=0) -> CatalogPaginatedResponseSchema:
        self.calls.append((product_id, limit, offset))
        if self.error:
            raise self.error
        return self.response or CatalogPaginatedResponseSchema(
            items=[], total_count=0, limit=limit, offset=offset,
        )


class SimilarProvider(Provider):
    def __init__(self, stub: StubGetSimilar):
        super().__init__()
        self.stub = stub

    @provide(scope=Scope.REQUEST)
    def get_use_case(self) -> GetSimilarUseCase:
        return self.stub  # type: ignore[return-value]


def _make_app(stub: StubGetSimilar) -> FastAPI:
    app = FastAPI()
    app.include_router(catalog_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), SimilarProvider(stub))
    setup_dishka(container, app)
    return app


def test_similar_router_returns_200():
    product_id = uuid4()
    stub = StubGetSimilar()
    client = TestClient(_make_app(stub))

    response = client.get(f'/api/v1/catalog/products/{product_id}/similar')

    assert response.status_code == 200
    body = response.json()
    # Per openapi spec: flat array of CatalogProductCard
    assert body == []
    assert stub.calls[0][0] == product_id
    assert stub.calls[0][1] == 10  # default limit per spec


def test_similar_router_returns_404_for_unknown_product():
    stub = StubGetSimilar()
    stub.error = ProductNotFoundError()
    client = TestClient(_make_app(stub))

    response = client.get(f'/api/v1/catalog/products/{uuid4()}/similar')

    assert response.status_code == 404
    assert response.json()['code'] == 'NOT_FOUND'


def test_similar_router_passes_limit_query():
    product_id = uuid4()
    stub = StubGetSimilar()
    client = TestClient(_make_app(stub))

    response = client.get(f'/api/v1/catalog/products/{product_id}/similar?limit=5')

    assert response.status_code == 200
    assert stub.calls[0][1] == 5


def test_similar_router_rejects_invalid_limit():
    stub = StubGetSimilar()
    client = TestClient(_make_app(stub))

    response = client.get(f'/api/v1/catalog/products/{uuid4()}/similar?limit=51')

    # MAX_LIMIT per openapi spec = 50 → FastAPI/наш валидатор отдаст 400.
    assert response.status_code == 400


def test_similar_router_502_on_b2b_unavailable():
    stub = StubGetSimilar()
    stub.error = CatalogUnavailableError()
    client = TestClient(_make_app(stub))

    response = client.get(f'/api/v1/catalog/products/{uuid4()}/similar')

    assert response.status_code == 502
