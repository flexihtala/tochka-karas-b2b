from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.errors import setup_error_handlers
from apps.products.enums import ProductStatus
from apps.products.errors import CategoryNotFoundError, ImagesRequiredError, ProductNotFoundError
from apps.products.routers import router as products_router
from apps.products.schemas.request import ProductCreateRequestSchema
from apps.products.schemas.response import (
    CharacteristicResponseSchema,
    ProductImageResponseSchema,
    ProductResponseSchema,
)
from apps.products.use_cases import CreateProductUseCase, GetProductUseCase
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


class StubGetProductUseCase:
    def __init__(self):
        self.calls: list[tuple[UUID, AuthenticatedUserSchema]] = []
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
            status=ProductStatus.MODERATED,
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
        product_id: UUID,
        current_user: AuthenticatedUserSchema,
    ) -> ProductResponseSchema:
        self.calls.append((product_id, current_user))
        if self.error:
            raise self.error
        return self.response


class ProductsRouteProvider(Provider):
    def __init__(
        self,
        create_stub: StubCreateProductUseCase,
        get_stub: StubGetProductUseCase | None = None,
    ):
        super().__init__()
        self.create_stub = create_stub
        self.get_stub = get_stub or StubGetProductUseCase()

    @provide(scope=Scope.REQUEST)
    def get_create_product_use_case(self) -> CreateProductUseCase:
        return self.create_stub

    @provide(scope=Scope.REQUEST)
    def get_get_product_use_case(self) -> GetProductUseCase:
        return self.get_stub


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
    get_stub: StubGetProductUseCase | None = None,
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
    container = make_async_container(FastapiProvider(), ProductsRouteProvider(stub, get_stub))
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


# ─── GET /api/v1/products/{id} ───


@pytest.fixture
def get_stub() -> StubGetProductUseCase:
    return StubGetProductUseCase()


def test_get_product_endpoint_returns_200(stub: StubCreateProductUseCase, get_stub: StubGetProductUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, get_stub))
    product_id = uuid4()

    response = client.get(f'/api/v1/products/{product_id}')

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == str(get_stub.response.id)
    assert body['status'] == ProductStatus.MODERATED.value
    assert body['skus'] == []
    assert len(get_stub.calls) == 1
    passed_id, current_user = get_stub.calls[0]
    assert passed_id == product_id
    assert current_user.id == user.id


def test_get_product_endpoint_unauthorized_returns_401(stub: StubCreateProductUseCase, get_stub: StubGetProductUseCase):
    client = TestClient(_make_app(stub, user=None, get_stub=get_stub))

    response = client.get(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 401
    assert response.json() == {'code': 'UNAUTHORIZED', 'message': 'Unauthorized'}
    assert get_stub.calls == []


def test_get_product_endpoint_non_seller_returns_403(stub: StubCreateProductUseCase, get_stub: StubGetProductUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(stub, user, get_stub))

    response = client.get(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'
    assert get_stub.calls == []


def test_get_product_endpoint_others_product_returns_404(
    stub: StubCreateProductUseCase, get_stub: StubGetProductUseCase
):
    """Чужой товар (use-case бросает ProductNotFoundError) → 404 NOT_FOUND.

    Канон: НЕ 403, чтобы не раскрыть факт существования чужого товара.
    """
    get_stub.error = ProductNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, get_stub))

    response = client.get(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 404
    assert response.json() == {'code': 'NOT_FOUND', 'message': 'Product not found'}


def test_get_product_endpoint_not_found_returns_404(stub: StubCreateProductUseCase, get_stub: StubGetProductUseCase):
    get_stub.error = ProductNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, get_stub))

    response = client.get(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 404
    assert response.json() == {'code': 'NOT_FOUND', 'message': 'Product not found'}


def test_get_product_endpoint_invalid_uuid_returns_400(stub: StubCreateProductUseCase, get_stub: StubGetProductUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, get_stub))

    response = client.get('/api/v1/products/not-a-uuid')

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}
    assert get_stub.calls == []
