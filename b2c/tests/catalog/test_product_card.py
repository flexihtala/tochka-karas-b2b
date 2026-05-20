"""US-CAT-03 product card tests.

Покрывают DoD:
- test_product_card_returns_full_data_with_skus
- test_cost_price_absent_in_response
- test_blocked_product_returns_404
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
from apps.catalog.schemas.response import CatalogProductDetailResponseSchema
from apps.catalog.use_cases import GetProductUseCase
from apps.errors import setup_error_handlers
from tests.catalog.fakes import MockTransportServiceClient, make_handler


def _b2b_client(handler) -> B2BCatalogClient:
    return B2BCatalogClient(service_client=MockTransportServiceClient(handler=handler))


@pytest.mark.anyio
async def test_product_card_returns_full_data_with_skus():
    product_id = uuid4()
    sku1_id = uuid4()
    sku2_id = uuid4()

    handler = make_handler(
        responses={
            f'GET /api/v1/catalog/products/{product_id}': (
                200,
                {
                    'id': str(product_id),
                    'slug': 'iphone-15-pro-max',
                    'title': 'iPhone 15 Pro Max',
                    'description': 'Флагман Apple',
                    'status': 'MODERATED',
                    'images': [
                        {'url': 'https://x/1.jpg', 'ordering': 0},
                        {'url': 'https://x/2.jpg', 'ordering': 1},
                    ],
                    'characteristics': [
                        {'name': 'Бренд', 'value': 'Apple'},
                    ],
                    'skus': [
                        {
                            'id': str(sku1_id),
                            'name': '256GB Black',
                            'price': 12999000,
                            'discount': 0,
                            'active_quantity': 10,
                            'images': [{'url': '/s3/black.jpg', 'ordering': 0}],
                            'characteristics': [
                                {'name': 'Цвет', 'value': 'Чёрный'},
                                {'name': 'Объём памяти', 'value': '256 ГБ'},
                            ],
                        },
                        {
                            'id': str(sku2_id),
                            'name': '256GB White',
                            'price': 12999000,
                            'discount': 500000,
                            'active_quantity': 3,
                            'images': [{'url': '/s3/white.jpg', 'ordering': 0}],
                            'characteristics': [
                                {'name': 'Цвет', 'value': 'Белый'},
                            ],
                        },
                    ],
                },
            ),
        },
    )

    use_case = GetProductUseCase(b2b_client=_b2b_client(handler))
    result = await use_case(product_id)

    assert result.id == product_id
    assert result.title == 'iPhone 15 Pro Max'
    assert result.description == 'Флагман Apple'
    assert len(result.images) == 2
    assert result.images[0].url == 'https://x/1.jpg'
    assert len(result.characteristics) == 1
    assert result.characteristics[0].name == 'Бренд'

    assert len(result.skus) == 2
    sku1, sku2 = result.skus
    assert sku1.id == sku1_id
    assert sku1.price == 12999000
    assert sku1.discount == 0
    assert sku1.active_quantity == 10
    assert sku1.in_stock is True
    assert sku2.discount == 500000  # discount > 0 сохранён
    assert sku2.in_stock is True


@pytest.mark.anyio
async def test_cost_price_absent_in_response():
    """ADR: даже если B2B по ошибке отдал cost_price/reserved_quantity — они НЕ попадают в B2C-response."""
    product_id = uuid4()
    sku_id = uuid4()

    handler = make_handler(
        responses={
            f'GET /api/v1/catalog/products/{product_id}': (
                200,
                {
                    'id': str(product_id),
                    'slug': 'p',
                    'title': 'X',
                    'description': '',
                    'status': 'MODERATED',
                    'images': [],
                    'characteristics': [],
                    'skus': [
                        {
                            'id': str(sku_id),
                            'name': 'main',
                            'price': 10000,
                            'discount': 0,
                            'active_quantity': 5,
                            # Эти два поля НЕ должны попасть в JSON-ответ:
                            'cost_price': 7000,
                            'reserved_quantity': 2,
                            'characteristics': [],
                            'images': [],
                        }
                    ],
                },
            ),
        },
    )
    use_case = GetProductUseCase(b2b_client=_b2b_client(handler))
    result = await use_case(product_id)

    # Pydantic schema dump НЕ содержит cost_price/reserved_quantity.
    dumped_sku = result.skus[0].model_dump()
    assert 'cost_price' not in dumped_sku
    assert 'reserved_quantity' not in dumped_sku

    full = result.model_dump()
    full_json = str(full)
    assert 'cost_price' not in full_json
    assert 'reserved_quantity' not in full_json


@pytest.mark.anyio
async def test_blocked_product_returns_404():
    """B2B возвращает 404 если товар blocked/deleted/не виден — пробрасываем ProductNotFoundError."""
    product_id = uuid4()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=404, json={'code': 'NOT_FOUND', 'message': 'product not found'})

    use_case = GetProductUseCase(b2b_client=_b2b_client(handler))

    with pytest.raises(ProductNotFoundError) as exc_info:
        await use_case(product_id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == 'NOT_FOUND'


@pytest.mark.anyio
async def test_b2b_unavailable_returns_502():
    product_id = uuid4()

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('no route')

    use_case = GetProductUseCase(b2b_client=_b2b_client(handler))

    with pytest.raises(CatalogUnavailableError):
        await use_case(product_id)


@pytest.mark.anyio
async def test_sku_with_zero_active_quantity_has_in_stock_false():
    """Канон: SKU с active_quantity=0 → in_stock=false, но карточка всё равно отдаётся."""
    product_id = uuid4()
    sku_id = uuid4()

    handler = make_handler(
        responses={
            f'GET /api/v1/catalog/products/{product_id}': (
                200,
                {
                    'id': str(product_id),
                    'slug': 'p',
                    'title': 'T',
                    'description': '',
                    'status': 'MODERATED',
                    'images': [],
                    'characteristics': [],
                    'skus': [
                        {
                            'id': str(sku_id),
                            'name': 'x',
                            'price': 1,
                            'discount': 0,
                            'active_quantity': 0,
                            'characteristics': [],
                            'images': [],
                        }
                    ],
                },
            ),
        },
    )
    use_case = GetProductUseCase(b2b_client=_b2b_client(handler))
    result = await use_case(product_id)

    assert result.skus[0].active_quantity == 0
    assert result.skus[0].in_stock is False


# ----------------------- Router tests -----------------------


class StubGetProduct:
    def __init__(self):
        self.calls: list = []
        self.error: Exception | None = None
        self.response: CatalogProductDetailResponseSchema | None = None

    async def __call__(self, product_id) -> CatalogProductDetailResponseSchema:
        self.calls.append(product_id)
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


class ProductCardProvider(Provider):
    def __init__(self, stub: StubGetProduct):
        super().__init__()
        self.stub = stub

    @provide(scope=Scope.REQUEST)
    def get_use_case(self) -> GetProductUseCase:
        return self.stub  # type: ignore[return-value]


def _make_app(stub: StubGetProduct) -> FastAPI:
    app = FastAPI()
    app.include_router(catalog_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), ProductCardProvider(stub))
    setup_dishka(container, app)
    return app


def test_get_product_router_returns_200():
    product_id = uuid4()
    stub = StubGetProduct()
    stub.response = CatalogProductDetailResponseSchema(
        id=product_id, slug='x', title='Test', description='', status='MODERATED',
    )
    client = TestClient(_make_app(stub))

    response = client.get(f'/api/v1/products/{product_id}')

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == str(product_id)
    assert body['title'] == 'Test'
    assert 'cost_price' not in body
    assert 'reserved_quantity' not in body


def test_get_product_router_returns_404():
    stub = StubGetProduct()
    stub.error = ProductNotFoundError()
    client = TestClient(_make_app(stub))

    response = client.get(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 404
    body = response.json()
    assert body['code'] == 'NOT_FOUND'


def test_get_product_router_502_on_b2b_unavailable():
    stub = StubGetProduct()
    stub.error = CatalogUnavailableError()
    client = TestClient(_make_app(stub))

    response = client.get(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 502


def test_get_product_invalid_uuid_returns_422():
    """Невалидный UUID в path — FastAPI отвечает 422 (валидация path-параметра)."""
    stub = StubGetProduct()
    client = TestClient(_make_app(stub))

    response = client.get('/api/v1/products/not-a-uuid')

    # FastAPI 422 на path-валидации — это стандартное поведение, не наша ошибка.
    assert response.status_code in (400, 422)
