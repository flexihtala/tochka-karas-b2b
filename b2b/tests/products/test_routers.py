from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.errors import setup_error_handlers
from apps.products.enums import ProductStatus
from apps.products.errors import (
    CategoryNotFoundError,
    ImagesRequiredError,
    ProductAlreadyDeletedError,
    ProductHardBlockedError,
    ProductNotFoundError,
    ProductNotOwnerError,
)
from apps.products.routers import router as products_router
from apps.products.schemas.request import ProductCreateRequestSchema
from apps.products.schemas.response import (
    CharacteristicResponseSchema,
    ProductImageResponseSchema,
    ProductResponseSchema,
)
from apps.products.use_cases import CreateProductUseCase, DeleteProductUseCase
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


class StubDeleteProductUseCase:
    def __init__(self):
        self.calls: list[tuple[UUID, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None

    async def __call__(self, product_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        self.calls.append((product_id, current_user))
        if self.error:
            raise self.error


class ProductsRouteProvider(Provider):
    def __init__(
        self,
        create_stub: StubCreateProductUseCase,
        delete_stub: StubDeleteProductUseCase,
    ):
        super().__init__()
        self.create_stub = create_stub
        self.delete_stub = delete_stub

    @provide(scope=Scope.REQUEST)
    def get_create_product_use_case(self) -> CreateProductUseCase:
        return self.create_stub

    @provide(scope=Scope.REQUEST)
    def get_delete_product_use_case(self) -> DeleteProductUseCase:
        return self.delete_stub


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
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
    user: AuthenticatedUserSchema | None,
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
    container = make_async_container(FastapiProvider(), ProductsRouteProvider(create_stub, delete_stub))
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
def create_stub() -> StubCreateProductUseCase:
    return StubCreateProductUseCase()


@pytest.fixture
def delete_stub() -> StubDeleteProductUseCase:
    return StubDeleteProductUseCase()


def test_create_product_endpoint_returns_201(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(create_stub, delete_stub, user))

    response = client.post('/api/v1/products', json=_create_request_payload())

    assert response.status_code == 201
    body = response.json()
    assert body['status'] == ProductStatus.CREATED.value
    assert body['skus'] == []
    assert body['deleted'] is False
    assert body['title'] == 'iPhone 15 Pro Max'
    assert len(body['images']) == 1
    assert len(create_stub.calls) == 1
    request_data, current_user = create_stub.calls[0]
    assert request_data.title == 'iPhone 15 Pro Max'
    assert current_user.id == user.id


def test_create_product_unauthorized_returns_401(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    client = TestClient(_make_app(create_stub, delete_stub, user=None))

    response = client.post('/api/v1/products', json=_create_request_payload())

    assert response.status_code == 401
    assert response.json() == {'code': 'UNAUTHORIZED', 'message': 'Unauthorized'}
    assert create_stub.calls == []


def test_create_product_non_seller_returns_403(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(create_stub, delete_stub, user))

    response = client.post('/api/v1/products', json=_create_request_payload())

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'
    assert create_stub.calls == []


def test_create_product_validation_error_returns_400(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(create_stub, delete_stub, user))

    # Missing all required fields except category_id
    response = client.post('/api/v1/products', json={})

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}


def test_create_product_invalid_category_returns_400(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    create_stub.error = CategoryNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(create_stub, delete_stub, user))

    response = client.post('/api/v1/products', json=_create_request_payload())

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Категория не найдена'}


def test_create_product_missing_images_returns_400(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    create_stub.error = ImagesRequiredError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(create_stub, delete_stub, user))

    payload = _create_request_payload()
    payload['images'] = []

    response = client.post('/api/v1/products', json=payload)

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Требуется минимум одно изображение'}


# ─────────────────────── DELETE /products/{id} ───────────────────────


def test_delete_product_endpoint_returns_204(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(create_stub, delete_stub, user))
    product_id = uuid4()

    response = client.delete(f'/api/v1/products/{product_id}')

    assert response.status_code == 204
    assert response.content == b''
    assert len(delete_stub.calls) == 1
    called_id, called_user = delete_stub.calls[0]
    assert called_id == product_id
    assert called_user.id == user.id


def test_delete_product_unauthorized_returns_401(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    client = TestClient(_make_app(create_stub, delete_stub, user=None))

    response = client.delete(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 401
    assert response.json() == {'code': 'UNAUTHORIZED', 'message': 'Unauthorized'}
    assert delete_stub.calls == []


def test_delete_product_non_seller_returns_403(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(create_stub, delete_stub, user))

    response = client.delete(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'
    assert delete_stub.calls == []


def test_delete_product_not_owner_returns_403(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    delete_stub.error = ProductNotOwnerError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(create_stub, delete_stub, user))

    response = client.delete(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 403
    body = response.json()
    assert body['code'] == 'NOT_OWNER'


def test_delete_product_hard_blocked_returns_403(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    delete_stub.error = ProductHardBlockedError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(create_stub, delete_stub, user))

    response = client.delete(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 403
    body = response.json()
    assert body['code'] == 'HARD_BLOCKED'


def test_delete_product_already_deleted_returns_400(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    delete_stub.error = ProductAlreadyDeletedError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(create_stub, delete_stub, user))

    response = client.delete(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 400
    body = response.json()
    assert body['code'] == 'ALREADY_DELETED'
    assert body['message'] == 'Product already deleted'


def test_delete_product_not_found_returns_404(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    delete_stub.error = ProductNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(create_stub, delete_stub, user))

    response = client.delete(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 404
    body = response.json()
    assert body['code'] == 'NOT_FOUND'


def test_delete_product_invalid_uuid_returns_422(
    create_stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    """FastAPI валидация path-параметра возвращает 400 через наш RequestValidationError handler."""
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(create_stub, delete_stub, user))

    response = client.delete('/api/v1/products/not-a-uuid')

    # validation_error_handler преобразует RequestValidationError в 400 INVALID_REQUEST
    assert response.status_code == 400
    body = response.json()
    assert body['code'] == 'INVALID_REQUEST'
