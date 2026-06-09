"""Router-level тесты US-B2B-07: 5 эндпоинтов Public Catalog.

Проверяем интеграцию: парсинг query (включая filters[...] deepObject и sort),
auth через X-Service-Key (401 без ключа), маршрутизацию в нужный use-case,
формат ответа (короткие карточки в листинге, полные в batch/detail).

Замечание про подмену verify-зависимости: роутер собирает её один раз при импорте
из `settings.b2c_to_b2b_key` (по умолчанию пусто). Для тестов используем
`app.dependency_overrides`, подменяя зависимость на ту, что знает TEST_SERVICE_KEY.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.errors import setup_error_handlers
from apps.products.enums import ProductStatus
from apps.public.errors import PublicProductNotFoundError, PublicSKUNotFoundError
from apps.public.routers import router as public_router
from apps.public.routers import verify_b2c_to_b2b
from apps.public.schemas.response import (
    CharacteristicPublicResponseSchema,
    ProductImagePublicResponseSchema,
    ProductPublicPaginatedResponseSchema,
    ProductPublicResponseSchema,
    ProductPublicShortResponseSchema,
    SKUImagePublicResponseSchema,
    SKUPublicResponseSchema,
)
from apps.public.use_cases import (
    BatchProductsUseCase,
    GetPublicProductUseCase,
    GetPublicSKUUseCase,
    GetSimilarProductsUseCase,
    ListCatalogUseCase,
)
from shared.inbox.dependencies import make_verify_service_key
from shared.types import ServiceKeyDirection

TEST_SERVICE_KEY = 'test-b2c-to-b2b-key'
_AUTH = {'X-Service-Key': TEST_SERVICE_KEY}

_verify_with_test_key = make_verify_service_key(ServiceKeyDirection.B2C_TO_B2B, TEST_SERVICE_KEY)


def _short_item() -> ProductPublicShortResponseSchema:
    return ProductPublicShortResponseSchema(
        id=uuid4(),
        title='iPhone 15 Pro Max',
        slug='iphone-15-pro-max',
        status=ProductStatus.MODERATED,
        category_id=uuid4(),
        min_price=9_900_000,
        cover_image='/s3/cover.jpg',
        created_at=datetime.now(UTC),
    )


def _full_product() -> ProductPublicResponseSchema:
    now = datetime.now(UTC)
    product_id = uuid4()
    sku_id = uuid4()
    return ProductPublicResponseSchema(
        id=product_id,
        seller_id=uuid4(),
        category_id=uuid4(),
        title='iPhone 15 Pro Max',
        slug='iphone-15-pro-max',
        description='Флагман Apple',
        status=ProductStatus.MODERATED,
        images=[ProductImagePublicResponseSchema(id=uuid4(), url='/s3/p1.jpg', ordering=0)],
        characteristics=[CharacteristicPublicResponseSchema(id=uuid4(), name='Бренд', value='Apple')],
        skus=[
            SKUPublicResponseSchema(
                id=sku_id,
                product_id=product_id,
                name='256GB Black',
                price=12_999_000,
                discount=0,
                stock_quantity=13,
                active_quantity=10,
                article=None,
                images=[SKUImagePublicResponseSchema(id=uuid4(), url='/s3/sku.jpg', ordering=0)],
                characteristics=[CharacteristicPublicResponseSchema(id=uuid4(), name='Цвет', value='Чёрный')],
            )
        ],
        created_at=now,
        updated_at=now,
    )


def _sku_response() -> SKUPublicResponseSchema:
    return SKUPublicResponseSchema(
        id=uuid4(),
        product_id=uuid4(),
        name='256GB Black',
        price=12_999_000,
        discount=0,
        stock_quantity=13,
        active_quantity=10,
        article=None,
    )


class StubListCatalogUseCase:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, **kwargs) -> ProductPublicPaginatedResponseSchema:
        self.calls.append(kwargs)
        return ProductPublicPaginatedResponseSchema(items=[_short_item()], total_count=1, limit=20, offset=0)


class StubBatchUseCase:
    def __init__(self) -> None:
        self.calls: list[list[UUID]] = []

    async def __call__(self, *, product_ids: list[UUID]) -> list[ProductPublicResponseSchema]:
        self.calls.append(product_ids)
        return [_full_product()]


class StubGetProductUseCase:
    def __init__(self, raise_404: bool = False) -> None:
        self.raise_404 = raise_404
        self.calls: list[UUID] = []

    async def __call__(self, product_id: UUID) -> ProductPublicResponseSchema:
        self.calls.append(product_id)
        if self.raise_404:
            raise PublicProductNotFoundError()
        return _full_product()


class StubSimilarUseCase:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, product_id: UUID, *, limit: int = 10) -> list[ProductPublicShortResponseSchema]:
        self.calls.append({'product_id': product_id, 'limit': limit})
        return [_short_item()]


class StubGetSKUUseCase:
    def __init__(self, raise_404: bool = False) -> None:
        self.raise_404 = raise_404
        self.calls: list[UUID] = []

    async def __call__(self, sku_id: UUID) -> SKUPublicResponseSchema:
        self.calls.append(sku_id)
        if self.raise_404:
            raise PublicSKUNotFoundError()
        return _sku_response()


class _StubProvider(Provider):
    def __init__(self, stubs: dict):
        super().__init__()
        self._stubs = stubs

    @provide(scope=Scope.REQUEST)
    def get_list(self) -> ListCatalogUseCase:
        return self._stubs['list']  # type: ignore[return-value]

    @provide(scope=Scope.REQUEST)
    def get_batch(self) -> BatchProductsUseCase:
        return self._stubs['batch']  # type: ignore[return-value]

    @provide(scope=Scope.REQUEST)
    def get_detail(self) -> GetPublicProductUseCase:
        return self._stubs['detail']  # type: ignore[return-value]

    @provide(scope=Scope.REQUEST)
    def get_similar(self) -> GetSimilarProductsUseCase:
        return self._stubs['similar']  # type: ignore[return-value]

    @provide(scope=Scope.REQUEST)
    def get_sku(self) -> GetPublicSKUUseCase:
        return self._stubs['sku']  # type: ignore[return-value]


def _make_app(stubs: dict) -> FastAPI:
    app = FastAPI()
    app.include_router(public_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), _StubProvider(stubs))
    setup_dishka(container, app)
    app.dependency_overrides[verify_b2c_to_b2b] = _verify_with_test_key
    return app


def _default_stubs(**overrides) -> dict:
    stubs = {
        'list': StubListCatalogUseCase(),
        'batch': StubBatchUseCase(),
        'detail': StubGetProductUseCase(),
        'similar': StubSimilarUseCase(),
        'sku': StubGetSKUUseCase(),
    }
    stubs.update(overrides)
    return stubs


@pytest.fixture
def stubs() -> dict:
    return _default_stubs()


# --- listing ---------------------------------------------------------------


def test_list_returns_200_short_cards(stubs: dict):
    client = TestClient(_make_app(stubs))

    response = client.get('/api/v1/public/products', headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body['total_count'] == 1
    item = body['items'][0]
    # короткая карточка: есть min_price/cover_image, нет skus
    assert item['min_price'] == 9_900_000
    assert item['cover_image'] == '/s3/cover.jpg'
    assert 'skus' not in item
    assert len(stubs['list'].calls) == 1


def test_list_missing_service_key_returns_401(stubs: dict):
    client = TestClient(_make_app(stubs))

    response = client.get('/api/v1/public/products')

    assert response.status_code == 401
    assert response.json()['code'] == 'INVALID_SERVICE_KEY'
    assert stubs['list'].calls == []


def test_list_wrong_service_key_returns_401(stubs: dict):
    client = TestClient(_make_app(stubs))

    response = client.get('/api/v1/public/products', headers={'X-Service-Key': 'wrong'})

    assert response.status_code == 401
    assert response.json()['code'] == 'INVALID_SERVICE_KEY'


def test_list_passes_filters_sort_and_pagination(stubs: dict):
    client = TestClient(_make_app(stubs))
    cat = uuid4()
    seller = uuid4()

    response = client.get(
        '/api/v1/public/products',
        params=[
            ('category_id', str(cat)),
            ('seller_id', str(seller)),
            ('search', 'iphone'),
            ('min_price', 1000),
            ('max_price', 999999),
            ('sort', 'price_asc'),
            ('limit', 50),
            ('offset', 10),
            ('filters[brand]', 'apple'),
            ('filters[brand]', 'samsung'),
            ('filters[memory]', '256'),
        ],
        headers=_AUTH,
    )

    assert response.status_code == 200
    call = stubs['list'].calls[0]
    assert call['category_id'] == cat
    assert call['seller_id'] == seller
    assert call['search'] == 'iphone'
    assert call['min_price'] == 1000
    assert call['max_price'] == 999999
    assert call['sort'].value == 'price_asc'
    assert call['limit'] == 50
    assert call['offset'] == 10
    assert call['filters'] == {'brand': ['apple', 'samsung'], 'memory': ['256']}


def test_list_no_filters_passes_none(stubs: dict):
    client = TestClient(_make_app(stubs))

    client.get('/api/v1/public/products', headers=_AUTH)

    assert stubs['list'].calls[0]['filters'] is None


def test_list_invalid_sort_returns_422(stubs: dict):
    client = TestClient(_make_app(stubs))

    response = client.get('/api/v1/public/products', params={'sort': 'bogus'}, headers=_AUTH)

    assert response.status_code in (400, 422)


def test_list_search_too_short_returns_422(stubs: dict):
    client = TestClient(_make_app(stubs))

    response = client.get('/api/v1/public/products', params={'search': 'ab'}, headers=_AUTH)

    assert response.status_code in (400, 422)


def test_list_limit_too_high_returns_422(stubs: dict):
    client = TestClient(_make_app(stubs))

    response = client.get('/api/v1/public/products', params={'limit': 500}, headers=_AUTH)

    assert response.status_code in (400, 422)


# --- batch -----------------------------------------------------------------


def test_batch_post_returns_full_visible_subset(stubs: dict):
    """POST /batch с {product_ids} → массив полных карточек; auth обязателен."""
    client = TestClient(_make_app(stubs))
    id1, id2 = uuid4(), uuid4()

    response = client.post(
        '/api/v1/public/products/batch',
        json={'product_ids': [str(id1), str(id2)]},
        headers=_AUTH,
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    # полная карточка содержит skus и stock_quantity, без cost_price/reserved_quantity
    sku = body[0]['skus'][0]
    assert 'cost_price' not in sku
    assert 'reserved_quantity' not in sku
    assert sku['stock_quantity'] == 13
    assert stubs['batch'].calls[0] == [id1, id2]


def test_batch_missing_service_key_returns_401(stubs: dict):
    client = TestClient(_make_app(stubs))

    response = client.post('/api/v1/public/products/batch', json={'product_ids': [str(uuid4())]})

    assert response.status_code == 401
    assert stubs['batch'].calls == []


def test_batch_too_many_ids_returns_422(stubs: dict):
    client = TestClient(_make_app(stubs))
    ids = [str(uuid4()) for _ in range(101)]

    response = client.post('/api/v1/public/products/batch', json={'product_ids': ids}, headers=_AUTH)

    assert response.status_code in (400, 422)


# --- detail ----------------------------------------------------------------


def test_get_product_returns_full(stubs: dict):
    client = TestClient(_make_app(stubs))
    pid = uuid4()

    response = client.get(f'/api/v1/public/products/{pid}', headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert 'skus' in body
    assert body['skus'][0]['stock_quantity'] == 13
    assert stubs['detail'].calls == [pid]


def test_get_product_404_when_not_visible():
    stubs = _default_stubs(detail=StubGetProductUseCase(raise_404=True))
    client = TestClient(_make_app(stubs))

    response = client.get(f'/api/v1/public/products/{uuid4()}', headers=_AUTH)

    assert response.status_code == 404
    assert response.json()['code'] == 'NOT_FOUND'


def test_get_product_missing_service_key_returns_401(stubs: dict):
    client = TestClient(_make_app(stubs))

    response = client.get(f'/api/v1/public/products/{uuid4()}')

    assert response.status_code == 401


# --- similar ---------------------------------------------------------------


def test_similar_returns_short_cards(stubs: dict):
    client = TestClient(_make_app(stubs))
    pid = uuid4()

    response = client.get(f'/api/v1/public/products/{pid}/similar', params={'limit': 5}, headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert 'min_price' in body[0]
    assert 'skus' not in body[0]
    assert stubs['similar'].calls[0] == {'product_id': pid, 'limit': 5}


def test_similar_default_limit_is_10(stubs: dict):
    client = TestClient(_make_app(stubs))

    client.get(f'/api/v1/public/products/{uuid4()}/similar', headers=_AUTH)

    assert stubs['similar'].calls[0]['limit'] == 10


def test_similar_limit_too_high_returns_422(stubs: dict):
    client = TestClient(_make_app(stubs))

    response = client.get(f'/api/v1/public/products/{uuid4()}/similar', params={'limit': 100}, headers=_AUTH)

    assert response.status_code in (400, 422)


# --- sku -------------------------------------------------------------------


def test_get_sku_returns_public_sku(stubs: dict):
    client = TestClient(_make_app(stubs))
    sku_id = uuid4()

    response = client.get(f'/api/v1/public/skus/{sku_id}', headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert 'cost_price' not in body
    assert 'reserved_quantity' not in body
    assert body['stock_quantity'] == 13
    assert stubs['sku'].calls == [sku_id]


def test_get_sku_404_when_product_not_visible():
    stubs = _default_stubs(sku=StubGetSKUUseCase(raise_404=True))
    client = TestClient(_make_app(stubs))

    response = client.get(f'/api/v1/public/skus/{uuid4()}', headers=_AUTH)

    assert response.status_code == 404
    assert response.json()['code'] == 'NOT_FOUND'


def test_get_sku_missing_service_key_returns_401(stubs: dict):
    client = TestClient(_make_app(stubs))

    response = client.get(f'/api/v1/public/skus/{uuid4()}')

    assert response.status_code == 401
