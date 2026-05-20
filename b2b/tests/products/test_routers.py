from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.errors import setup_error_handlers
from apps.products.enums import ProductStatus
from apps.products.errors import CategoryNotFoundError, ImagesRequiredError
from apps.products.routers import router as products_router
from apps.products.schemas.request import ProductCreateRequestSchema
from apps.products.schemas.response import (
    CharacteristicResponseSchema,
    ProductImageResponseSchema,
    ProductListItemResponseSchema,
    ProductPaginatedResponseSchema,
    ProductResponseSchema,
)
from apps.products.use_cases import CreateProductUseCase, ListSellerProductsUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole


class StubCreateProductUseCase:
    def __init__(self):
        self.calls: list[tuple[ProductCreateRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        now = datetime.now(UTC)
        product_id = uuid4()
        self.response = ProductResponseSchema(
            id=product_id,
            seller_id=uuid4(),
            category_id=uuid4(),
            title='iPhone 15 Pro Max',
            slug='iphone-15-pro-max',
            description='Флагман Apple',
            status=ProductStatus.CREATED,
            deleted=False,
            blocking_reason_id=None,
            moderator_comment=None,
            images=[
                ProductImageResponseSchema(id=uuid4(), url='/s3/iphone15-front.jpg', ordering=0),
            ],
            characteristics=[
                CharacteristicResponseSchema(id=uuid4(), name='Бренд', value='Apple'),
            ],
            skus=[],
            created_at=now,
            updated_at=now,
        )

    async def __call__(
        self,
        data: ProductCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> ProductResponseSchema:
        self.calls.append((data, current_user))
        if self.error:
            raise self.error
        return self.response


class StubListSellerProductsUseCase:
    def __init__(self):
        self.calls: list[dict] = []
        self.error: Exception | None = None
        now = datetime.now(UTC)
        self.response = ProductPaginatedResponseSchema(
            items=[
                ProductListItemResponseSchema(
                    id=uuid4(),
                    seller_id=uuid4(),
                    category_id=uuid4(),
                    title='iPhone 15 Pro Max',
                    slug='iphone-15-pro-max',
                    status=ProductStatus.MODERATED,
                    deleted=False,
                    images=[
                        ProductImageResponseSchema(id=uuid4(), url='/s3/iphone15-front.jpg', ordering=0),
                    ],
                    skus_count=0,
                    total_active_quantity=0,
                    created_at=now,
                    updated_at=now,
                )
            ],
            total_count=1,
            limit=20,
            offset=0,
        )

    async def __call__(
        self,
        *,
        current_user: AuthenticatedUserSchema,
        limit: int,
        offset: int,
        status: ProductStatus | None = None,
        include_deleted: bool = False,
        search: str | None = None,
    ) -> ProductPaginatedResponseSchema:
        self.calls.append(
            {
                'current_user': current_user,
                'limit': limit,
                'offset': offset,
                'status': status,
                'include_deleted': include_deleted,
                'search': search,
            }
        )
        if self.error:
            raise self.error
        return self.response


class ProductsRouteProvider(Provider):
    def __init__(
        self,
        create_stub: StubCreateProductUseCase,
        list_stub: StubListSellerProductsUseCase | None = None,
    ):
        super().__init__()
        self.create_stub = create_stub
        self.list_stub = list_stub or StubListSellerProductsUseCase()

    @provide(scope=Scope.REQUEST)
    def get_create_product_use_case(self) -> CreateProductUseCase:
        return self.create_stub

    @provide(scope=Scope.REQUEST)
    def get_list_seller_products_use_case(self) -> ListSellerProductsUseCase:
        return self.list_stub


class AuthInjectingMiddleware:
    """Минимальный middleware для тестов: ставит request.state.user из переданного пользователя.

    Имитирует AuthMiddleware без декодирования реального JWT.
    """

    def __init__(self, app, user: AuthenticatedUserSchema | None):
        self.app = app
        self.user = user

    async def __call__(self, scope, receive, send):
        if scope.get('type') == 'http':
            scope.setdefault('state', {})
        await self.app(scope, receive, send)


def _make_app(
    stub: StubCreateProductUseCase,
    user: AuthenticatedUserSchema | None,
    list_stub: StubListSellerProductsUseCase | None = None,
) -> FastAPI:
    """Создаёт минимальное FastAPI приложение с роутером products.

    AuthMiddleware заменяется на простую инъекцию в request.state.user.
    """
    from starlette.middleware.base import BaseHTTPMiddleware

    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(products_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), ProductsRouteProvider(stub, list_stub))
    setup_dishka(container, app)
    return app


def _create_request_payload(category_id: UUID | None = None) -> dict:
    return {
        'title': 'iPhone 15 Pro Max',
        'description': 'Флагман Apple',
        'category_id': str(category_id or uuid4()),
        'images': [
            {'url': '/s3/iphone15-front.jpg', 'ordering': 0},
            {'url': '/s3/iphone15-back.jpg', 'ordering': 1},
        ],
        'characteristics': [{'name': 'Бренд', 'value': 'Apple'}],
    }


@pytest.fixture
def stub() -> StubCreateProductUseCase:
    return StubCreateProductUseCase()


@pytest.fixture
def list_stub() -> StubListSellerProductsUseCase:
    return StubListSellerProductsUseCase()


def test_create_product_endpoint_returns_201(stub: StubCreateProductUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/products', json=_create_request_payload())

    assert response.status_code == 201
    body = response.json()
    assert body['status'] == ProductStatus.CREATED.value
    assert body['skus'] == []
    assert body['deleted'] is False
    assert body['title'] == 'iPhone 15 Pro Max'
    assert len(body['images']) == 1
    assert len(stub.calls) == 1
    request_data, current_user = stub.calls[0]
    assert request_data.title == 'iPhone 15 Pro Max'
    assert current_user.id == user.id


def test_create_product_unauthorized_returns_401(stub: StubCreateProductUseCase):
    client = TestClient(_make_app(stub, user=None))

    response = client.post('/api/v1/products', json=_create_request_payload())

    assert response.status_code == 401
    assert response.json() == {'code': 'UNAUTHORIZED', 'message': 'Unauthorized'}
    assert stub.calls == []


def test_create_product_non_seller_returns_403(stub: StubCreateProductUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/products', json=_create_request_payload())

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'
    assert stub.calls == []


def test_create_product_validation_error_returns_400(stub: StubCreateProductUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    # Missing all required fields except category_id
    response = client.post('/api/v1/products', json={})

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}


def test_create_product_invalid_category_returns_400(stub: StubCreateProductUseCase):
    stub.error = CategoryNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/products', json=_create_request_payload())

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Категория не найдена'}


def test_create_product_missing_images_returns_400(stub: StubCreateProductUseCase):
    stub.error = ImagesRequiredError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    payload = _create_request_payload()
    payload['images'] = []

    response = client.post('/api/v1/products', json=payload)

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Требуется минимум одно изображение'}


# ──────────────────────────── GET /api/v1/products ────────────────────────────


def test_list_products_endpoint_returns_200_with_pagination(
    stub: StubCreateProductUseCase, list_stub: StubListSellerProductsUseCase
):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, list_stub=list_stub))

    response = client.get('/api/v1/products')

    assert response.status_code == 200
    body = response.json()
    assert body['total_count'] == 1
    assert body['limit'] == 20
    assert body['offset'] == 0
    assert len(body['items']) == 1
    item = body['items'][0]
    assert item['title'] == 'iPhone 15 Pro Max'
    assert item['skus_count'] == 0
    assert item['total_active_quantity'] == 0
    assert len(list_stub.calls) == 1
    call = list_stub.calls[0]
    assert call['current_user'].id == user.id
    assert call['limit'] == 20
    assert call['offset'] == 0
    assert call['status'] is None
    assert call['include_deleted'] is False
    assert call['search'] is None


def test_list_products_passes_filters_to_use_case(
    stub: StubCreateProductUseCase, list_stub: StubListSellerProductsUseCase
):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, list_stub=list_stub))

    response = client.get(
        '/api/v1/products',
        params={
            'limit': 5,
            'offset': 10,
            'status': ProductStatus.MODERATED.value,
            'include_deleted': 'true',
            'search': 'iphone',
        },
    )

    assert response.status_code == 200
    call = list_stub.calls[0]
    assert call['limit'] == 5
    assert call['offset'] == 10
    assert call['status'] == ProductStatus.MODERATED
    assert call['include_deleted'] is True
    assert call['search'] == 'iphone'


def test_list_products_query_seller_id_ignored(
    stub: StubCreateProductUseCase, list_stub: StubListSellerProductsUseCase
):
    """IDOR: попытка передать seller_id в query НЕ влияет на seller_id из JWT."""
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, list_stub=list_stub))
    attacker_target = uuid4()

    response = client.get('/api/v1/products', params={'seller_id': str(attacker_target)})

    assert response.status_code == 200
    call = list_stub.calls[0]
    # JWT-id передан в use case без изменений
    assert call['current_user'].id == user.id
    # Параметр seller_id из query не вошёл в kwargs (его в сигнатуре use case нет)
    assert 'seller_id' not in call


def test_list_products_unauthorized_returns_401(
    stub: StubCreateProductUseCase, list_stub: StubListSellerProductsUseCase
):
    client = TestClient(_make_app(stub, user=None, list_stub=list_stub))

    response = client.get('/api/v1/products')

    assert response.status_code == 401
    assert response.json() == {'code': 'UNAUTHORIZED', 'message': 'Unauthorized'}
    assert list_stub.calls == []


def test_list_products_non_seller_returns_403(stub: StubCreateProductUseCase, list_stub: StubListSellerProductsUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(stub, user, list_stub=list_stub))

    response = client.get('/api/v1/products')

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'
    assert list_stub.calls == []


def test_list_products_invalid_limit_returns_400(
    stub: StubCreateProductUseCase, list_stub: StubListSellerProductsUseCase
):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, list_stub=list_stub))

    response = client.get('/api/v1/products', params={'limit': 1000})

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}
    assert list_stub.calls == []


def test_list_products_invalid_status_returns_400(
    stub: StubCreateProductUseCase, list_stub: StubListSellerProductsUseCase
):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, list_stub=list_stub))

    response = client.get('/api/v1/products', params={'status': 'INVALID_STATUS'})

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}
    assert list_stub.calls == []
