"""Router-level тесты US-B2B-07: GET /api/v1/catalog/products.

Проверяем интеграцию: парсинг query, auth через X-Service-Key, формат ответа.

Замечание про подмену verify-зависимости: роутер собирает её один раз при импорте
из `settings.b2c_to_b2b_key` (по умолчанию пусто). Чтобы тесты могли проверить
auth, мы используем `app.dependency_overrides`, подменяя зависимость на ту,
что знает наш TEST_SERVICE_KEY.
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
from apps.public.routers import router as public_router
from apps.public.routers import verify_b2c_to_b2b
from apps.public.schemas.response import (
    CharacteristicPublicResponseSchema,
    ProductImagePublicResponseSchema,
    ProductPublicPaginatedResponseSchema,
    ProductPublicResponseSchema,
    SKUImagePublicResponseSchema,
    SKUPublicResponseSchema,
)
from apps.public.use_cases import ListCatalogUseCase
from shared.inbox.dependencies import make_verify_service_key
from shared.types import ServiceKeyDirection

TEST_SERVICE_KEY = 'test-b2c-to-b2b-key'

# Подменённая зависимость с известным ключом — используется через app.dependency_overrides.
_verify_with_test_key = make_verify_service_key(ServiceKeyDirection.B2C_TO_B2B, TEST_SERVICE_KEY)


def _make_response_payload() -> ProductPublicPaginatedResponseSchema:
    now = datetime.now(UTC)
    product_id = uuid4()
    sku_id = uuid4()
    return ProductPublicPaginatedResponseSchema(
        items=[
            ProductPublicResponseSchema(
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
                        active_quantity=10,
                        article=None,
                        images=[SKUImagePublicResponseSchema(id=uuid4(), url='/s3/sku.jpg', ordering=0)],
                        characteristics=[CharacteristicPublicResponseSchema(id=uuid4(), name='Цвет', value='Чёрный')],
                    )
                ],
                created_at=now,
                updated_at=now,
            )
        ],
        total_count=1,
        limit=20,
        offset=0,
    )


class StubListCatalogUseCase:
    def __init__(self, response: ProductPublicPaginatedResponseSchema | None = None):
        self.response = response or _make_response_payload()
        self.calls: list[dict] = []

    async def __call__(
        self,
        *,
        ids: list[UUID] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ProductPublicPaginatedResponseSchema:
        self.calls.append({'ids': ids, 'limit': limit, 'offset': offset})
        return self.response


class _StubProvider(Provider):
    def __init__(self, stub: StubListCatalogUseCase):
        super().__init__()
        self._stub = stub

    @provide(scope=Scope.REQUEST)
    def get_list_catalog_use_case(self) -> ListCatalogUseCase:
        return self._stub  # type: ignore[return-value]


def _make_app(stub: StubListCatalogUseCase) -> FastAPI:
    app = FastAPI()
    app.include_router(public_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), _StubProvider(stub))
    setup_dishka(container, app)
    # Подмена auth-зависимости для тестов — теперь dep знает TEST_SERVICE_KEY.
    app.dependency_overrides[verify_b2c_to_b2b] = _verify_with_test_key
    return app


@pytest.fixture
def stub() -> StubListCatalogUseCase:
    return StubListCatalogUseCase()


def test_catalog_endpoint_returns_200_with_service_key(stub: StubListCatalogUseCase):
    client = TestClient(_make_app(stub))

    response = client.get(
        '/api/v1/catalog/products',
        headers={'X-Service-Key': TEST_SERVICE_KEY},
    )

    assert response.status_code == 200
    body = response.json()
    assert body['total_count'] == 1
    assert body['limit'] == 20
    assert body['offset'] == 0
    assert len(body['items']) == 1
    item = body['items'][0]
    assert item['status'] == ProductStatus.MODERATED.value
    assert len(item['skus']) == 1
    sku = item['skus'][0]
    # ключевая инвариант — в JSON нет cost_price / reserved_quantity
    assert 'cost_price' not in sku
    assert 'reserved_quantity' not in sku
    assert sku['active_quantity'] == 10
    # use-case был вызван
    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert call['ids'] is None
    assert call['limit'] == 20
    assert call['offset'] == 0


def test_catalog_missing_service_key_returns_401(stub: StubListCatalogUseCase):
    """Без заголовка X-Service-Key — 401, use-case не вызывается."""
    client = TestClient(_make_app(stub))

    response = client.get('/api/v1/catalog/products')

    assert response.status_code == 401
    body = response.json()
    assert body['code'] == 'INVALID_SERVICE_KEY'
    assert stub.calls == []


def test_catalog_wrong_service_key_returns_401(stub: StubListCatalogUseCase):
    """Неверный X-Service-Key — 401."""
    client = TestClient(_make_app(stub))

    response = client.get(
        '/api/v1/catalog/products',
        headers={'X-Service-Key': 'wrong-key'},
    )

    assert response.status_code == 401
    body = response.json()
    assert body['code'] == 'INVALID_SERVICE_KEY'
    assert stub.calls == []


def test_catalog_passes_pagination_to_use_case(stub: StubListCatalogUseCase):
    client = TestClient(_make_app(stub))

    response = client.get(
        '/api/v1/catalog/products',
        params={'limit': 50, 'offset': 100},
        headers={'X-Service-Key': TEST_SERVICE_KEY},
    )

    assert response.status_code == 200
    assert len(stub.calls) == 1
    assert stub.calls[0]['limit'] == 50
    assert stub.calls[0]['offset'] == 100


def test_catalog_batch_ids_query_parsed(stub: StubListCatalogUseCase):
    """?ids=uuid1,uuid2 пробрасывается в use-case как list[UUID]."""
    client = TestClient(_make_app(stub))
    id1, id2 = uuid4(), uuid4()

    response = client.get(
        '/api/v1/catalog/products',
        params={'ids': f'{id1},{id2}'},
        headers={'X-Service-Key': TEST_SERVICE_KEY},
    )

    assert response.status_code == 200
    assert len(stub.calls) == 1
    assert stub.calls[0]['ids'] == [id1, id2]


def test_catalog_batch_invalid_uuid_returns_400(stub: StubListCatalogUseCase):
    """?ids=notauuid — 400 (UUID-parsing в роутере), use-case не вызывается."""
    client = TestClient(_make_app(stub))

    response = client.get(
        '/api/v1/catalog/products',
        params={'ids': 'not-a-uuid'},
        headers={'X-Service-Key': TEST_SERVICE_KEY},
    )

    assert response.status_code in (400, 422)
    assert stub.calls == []


def test_catalog_limit_too_high_returns_400(stub: StubListCatalogUseCase):
    """limit > 100 → 400 (Query валидация)."""
    client = TestClient(_make_app(stub))

    response = client.get(
        '/api/v1/catalog/products',
        params={'limit': 500},
        headers={'X-Service-Key': TEST_SERVICE_KEY},
    )

    assert response.status_code in (400, 422)
