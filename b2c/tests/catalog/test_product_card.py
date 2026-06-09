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
from tests.catalog.fakes import make_handler, make_service_client


def _b2b_client(handler) -> B2BCatalogClient:
    return B2BCatalogClient(service_client=make_service_client(handler=handler))


@pytest.mark.anyio
async def test_product_card_returns_full_data_with_skus():
    product_id = uuid4()
    sku1_id = uuid4()
    sku2_id = uuid4()
    image1_id = uuid4()
    image2_id = uuid4()

    handler = make_handler(
        responses={
            # B2B отдаёт ProductPublicResponse: title (не name) + skus[].active_quantity.
            f'GET /api/v1/public/products/{product_id}': (
                200,
                {
                    'id': str(product_id),
                    'slug': 'iphone-15-pro-max',
                    'title': 'iPhone 15 Pro Max',
                    'description': 'Флагман Apple',
                    'status': 'MODERATED',
                    'images': [
                        {'id': str(image1_id), 'url': 'https://x/1.jpg', 'ordering': 0},
                        {'id': str(image2_id), 'url': 'https://x/2.jpg', 'ordering': 1},
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
                            'images': [{'id': str(uuid4()), 'url': '/s3/black.jpg', 'ordering': 0}],
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
                            'images': [{'id': str(uuid4()), 'url': '/s3/white.jpg', 'ordering': 0}],
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
    assert result.name == 'iPhone 15 Pro Max'
    assert result.description == 'Флагман Apple'
    assert len(result.images) == 2
    assert result.images[0].id == image1_id
    assert result.images[0].url == 'https://x/1.jpg'
    assert len(result.characteristics) == 1
    assert result.characteristics[0].name == 'Бренд'

    # min_price = минимум по SKU с остатком, has_stock = true т.к. есть SKU с остатком.
    assert result.min_price == 12999000
    assert result.has_stock is True

    assert len(result.skus) == 2
    sku1, sku2 = result.skus
    assert sku1.id == sku1_id
    assert sku1.price == 12999000
    assert sku1.discount == 0
    assert sku1.available_quantity == 10
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
            f'GET /api/v1/public/products/{product_id}': (
                200,
                {
                    'id': str(product_id),
                    'slug': 'p',
                    'name': 'X',
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
                            'available_quantity': 5,
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
async def test_sku_with_zero_available_quantity_has_in_stock_false():
    """Канон: SKU с available_quantity=0 → in_stock=false, но карточка всё равно отдаётся."""
    product_id = uuid4()
    sku_id = uuid4()

    handler = make_handler(
        responses={
            f'GET /api/v1/public/products/{product_id}': (
                200,
                {
                    'id': str(product_id),
                    'slug': 'p',
                    'name': 'T',
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
                            'available_quantity': 0,
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

    assert result.skus[0].available_quantity == 0
    assert result.skus[0].in_stock is False


@pytest.mark.anyio
async def test_min_price_returns_lowest_sku_price():
    """min_price = минимум sku.price среди SKU с available_quantity > 0."""
    product_id = uuid4()

    handler = make_handler(
        responses={
            f'GET /api/v1/public/products/{product_id}': (
                200,
                {
                    'id': str(product_id),
                    'slug': 'p',
                    'name': 'T',
                    'description': '',
                    'status': 'MODERATED',
                    'images': [],
                    'characteristics': [],
                    'skus': [
                        {
                            'id': str(uuid4()),
                            'name': 'big',
                            'price': 50000,
                            'discount': 0,
                            'available_quantity': 1,
                            'characteristics': [],
                            'images': [],
                        },
                        {
                            'id': str(uuid4()),
                            'name': 'small',
                            'price': 12000,
                            'discount': 0,
                            'available_quantity': 5,
                            'characteristics': [],
                            'images': [],
                        },
                        {
                            'id': str(uuid4()),
                            'name': 'cheap-but-no-stock',
                            'price': 5000,
                            'discount': 0,
                            'available_quantity': 0,
                            'characteristics': [],
                            'images': [],
                        },
                    ],
                },
            ),
        },
    )

    use_case = GetProductUseCase(b2b_client=_b2b_client(handler))
    result = await use_case(product_id)

    # 5000 (нет остатка) исключён — min среди с остатком = 12000.
    assert result.min_price == 12000
    assert result.has_stock is True


@pytest.mark.anyio
async def test_has_stock_false_when_no_skus_have_stock():
    """has_stock=false и min_price=0 если все SKU имеют available_quantity=0."""
    product_id = uuid4()

    handler = make_handler(
        responses={
            f'GET /api/v1/public/products/{product_id}': (
                200,
                {
                    'id': str(product_id),
                    'slug': 'p',
                    'name': 'T',
                    'description': '',
                    'status': 'MODERATED',
                    'images': [],
                    'characteristics': [],
                    'skus': [
                        {
                            'id': str(uuid4()),
                            'name': 'a',
                            'price': 1000,
                            'discount': 0,
                            'available_quantity': 0,
                            'characteristics': [],
                            'images': [],
                        },
                        {
                            'id': str(uuid4()),
                            'name': 'b',
                            'price': 2000,
                            'discount': 0,
                            'available_quantity': 0,
                            'characteristics': [],
                            'images': [],
                        },
                    ],
                },
            ),
        },
    )

    use_case = GetProductUseCase(b2b_client=_b2b_client(handler))
    result = await use_case(product_id)

    assert result.has_stock is False
    # Все распроданы — min_price=0 (UI скрывает цену).
    assert result.min_price == 0
    # Карточка отдаётся, SKU видны (статус остатка отражён на уровне SKU).
    assert len(result.skus) == 2
    assert all(s.in_stock is False for s in result.skus)


@pytest.mark.anyio
async def test_image_id_propagated_from_b2b():
    """Поле id у изображения обязательно (спец. b2c/openapi.yaml#ImageRef)."""
    product_id = uuid4()
    image_id = uuid4()

    handler = make_handler(
        responses={
            f'GET /api/v1/public/products/{product_id}': (
                200,
                {
                    'id': str(product_id),
                    'slug': 'p',
                    'name': 'T',
                    'description': '',
                    'status': 'MODERATED',
                    'images': [
                        {'id': str(image_id), 'url': 'https://x/1.jpg', 'ordering': 0},
                    ],
                    'characteristics': [],
                    'skus': [],
                },
            ),
        },
    )

    use_case = GetProductUseCase(b2b_client=_b2b_client(handler))
    result = await use_case(product_id)

    assert len(result.images) == 1
    assert result.images[0].id == image_id


@pytest.mark.anyio
async def test_legacy_active_quantity_accepted_for_backward_compat():
    """Backward-compat: B2B мог раньше отдавать active_quantity — принимаем."""
    product_id = uuid4()
    sku_id = uuid4()

    handler = make_handler(
        responses={
            f'GET /api/v1/public/products/{product_id}': (
                200,
                {
                    'id': str(product_id),
                    'slug': 'p',
                    'name': 'T',
                    'description': '',
                    'status': 'MODERATED',
                    'images': [],
                    'characteristics': [],
                    'skus': [
                        {
                            'id': str(sku_id),
                            'name': 'x',
                            'price': 1000,
                            'discount': 0,
                            'active_quantity': 7,
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

    assert result.skus[0].available_quantity == 7
    assert result.skus[0].in_stock is True
    assert result.has_stock is True
    assert result.min_price == 1000


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
        id=product_id,
        slug='x',
        name='Test',
        description='',
        status='MODERATED',
        min_price=1000,
        has_stock=True,
    )
    client = TestClient(_make_app(stub))

    response = client.get(f'/api/v1/catalog/products/{product_id}')

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == str(product_id)
    assert body['name'] == 'Test'
    assert body['min_price'] == 1000
    assert body['has_stock'] is True
    assert 'cost_price' not in body
    assert 'reserved_quantity' not in body


def test_get_product_router_returns_404():
    stub = StubGetProduct()
    stub.error = ProductNotFoundError()
    client = TestClient(_make_app(stub))

    response = client.get(f'/api/v1/catalog/products/{uuid4()}')

    assert response.status_code == 404
    body = response.json()
    assert body['code'] == 'NOT_FOUND'


def test_get_product_router_502_on_b2b_unavailable():
    stub = StubGetProduct()
    stub.error = CatalogUnavailableError()
    client = TestClient(_make_app(stub))

    response = client.get(f'/api/v1/catalog/products/{uuid4()}')

    assert response.status_code == 502


def test_get_product_invalid_uuid_returns_422():
    """Невалидный UUID в path — FastAPI отвечает 422 (валидация path-параметра)."""
    stub = StubGetProduct()
    client = TestClient(_make_app(stub))

    response = client.get('/api/v1/catalog/products/not-a-uuid')

    # FastAPI 422 на path-валидации — это стандартное поведение, не наша ошибка.
    assert response.status_code in (400, 422)
