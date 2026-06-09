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
from apps.products.schemas.request import ProductCreateRequestSchema, ProductEditRequestSchema
from apps.products.schemas.response import (
    CharacteristicResponseSchema,
    ProductDetailResponseSchema,
    ProductImageResponseSchema,
    ProductResponseSchema,
)
from apps.products.use_cases import (
    CreateProductUseCase,
    DeleteProductUseCase,
    EditProductUseCase,
    GetProductUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _make_response(status: ProductStatus = ProductStatus.CREATED) -> ProductResponseSchema:
    now = datetime.now(UTC)
    return ProductResponseSchema(
        id=uuid4(),
        seller_id=uuid4(),
        category_id=uuid4(),
        title='iPhone 15 Pro Max',
        slug='iphone-15-pro-max',
        description='Флагман Apple',
        status=status,
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


class StubCreateProductUseCase:
    def __init__(self):
        self.calls: list[tuple[ProductCreateRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.response = _make_response()

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
        self.response = ProductDetailResponseSchema(
            id=product_id,
            seller_id=uuid4(),
            category_id=uuid4(),
            title='iPhone 15 Pro Max',
            slug='iphone-15-pro-max',
            description='Флагман Apple',
            status=ProductStatus.MODERATED,
            deleted=False,
            images=[
                ProductImageResponseSchema(id=uuid4(), url='/s3/iphone15-front.jpg', ordering=0),
            ],
            characteristics=[
                CharacteristicResponseSchema(id=uuid4(), name='Бренд', value='Apple'),
            ],
            skus=[],
            created_at=now,
            updated_at=now,
            blocked=False,
            blocking_reason=None,
            field_reports=[],
        )

    async def __call__(
        self,
        product_id: UUID,
        current_user: AuthenticatedUserSchema,
    ) -> ProductDetailResponseSchema:
        self.calls.append((product_id, current_user))
        if self.error:
            raise self.error
        return self.response


class StubEditProductUseCase:
    def __init__(self):
        self.calls: list[tuple[UUID, ProductEditRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.response = _make_response(status=ProductStatus.ON_MODERATION)

    async def __call__(
        self,
        product_id: UUID,
        data: ProductEditRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> ProductResponseSchema:
        self.calls.append((product_id, data, current_user))
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
        edit_stub: StubEditProductUseCase,
        delete_stub: StubDeleteProductUseCase,
        get_stub: StubGetProductUseCase | None = None,
    ):
        super().__init__()
        self.create_stub = create_stub
        self.edit_stub = edit_stub
        self.delete_stub = delete_stub
        self.get_stub = get_stub or StubGetProductUseCase()

    @provide(scope=Scope.REQUEST)
    def get_create_product_use_case(self) -> CreateProductUseCase:
        return self.create_stub

    @provide(scope=Scope.REQUEST)
    def get_edit_product_use_case(self) -> EditProductUseCase:
        return self.edit_stub

    @provide(scope=Scope.REQUEST)
    def get_delete_product_use_case(self) -> DeleteProductUseCase:
        return self.delete_stub

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
    create_stub: StubCreateProductUseCase,
    user: AuthenticatedUserSchema | None,
    edit_stub: StubEditProductUseCase | None = None,
    delete_stub: StubDeleteProductUseCase | None = None,
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
    container = make_async_container(
        FastapiProvider(),
        ProductsRouteProvider(
            create_stub,
            edit_stub or StubEditProductUseCase(),
            delete_stub or StubDeleteProductUseCase(),
            get_stub,
        ),
    )
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
def edit_stub() -> StubEditProductUseCase:
    return StubEditProductUseCase()


@pytest.fixture
def delete_stub() -> StubDeleteProductUseCase:
    return StubDeleteProductUseCase()


def test_create_product_endpoint_returns_201(stub: StubCreateProductUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/products', json=_create_request_payload())

    assert response.status_code == 201
    body = response.json()
    assert body['status'] == ProductStatus.CREATED.value
    # placeholder until US-B2B-02 (PR #8) merges; real SKU list will populate then
    assert isinstance(body['skus'], list)
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
    client = TestClient(_make_app(stub, user, get_stub=get_stub))
    product_id = uuid4()

    response = client.get(f'/api/v1/products/{product_id}')

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == str(get_stub.response.id)
    assert body['status'] == ProductStatus.MODERATED.value
    assert isinstance(body['skus'], list)
    # ProductDetailResponse-поля присутствуют в ответе
    assert body['blocked'] is False
    assert body['blocking_reason'] is None
    assert body['field_reports'] == []
    # плоских legacy-полей в seller-карточке быть не должно
    assert 'blocking_reason_id' not in body
    assert 'moderator_comment' not in body
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
    client = TestClient(_make_app(stub, user, get_stub=get_stub))

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
    client = TestClient(_make_app(stub, user, get_stub=get_stub))

    response = client.get(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 404
    assert response.json() == {'code': 'NOT_FOUND', 'message': 'Product not found'}


def test_get_product_endpoint_not_found_returns_404(stub: StubCreateProductUseCase, get_stub: StubGetProductUseCase):
    get_stub.error = ProductNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, get_stub=get_stub))

    response = client.get(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 404
    assert response.json() == {'code': 'NOT_FOUND', 'message': 'Product not found'}


def test_get_product_endpoint_invalid_uuid_returns_400(stub: StubCreateProductUseCase, get_stub: StubGetProductUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, get_stub=get_stub))

    response = client.get('/api/v1/products/not-a-uuid')

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}
    assert get_stub.calls == []



# ===========================================================================
# PATCH /api/v1/products/{product_id} — US-B2B-03
# ===========================================================================


def _edit_request_payload(category_id: UUID | None = None) -> dict:
    return {
        'title': 'iPhone 15 Pro Max (обновлено)',
        'description': 'Обновлённое описание',
        'category_id': str(category_id or uuid4()),
        'images': [
            {'url': '/s3/iphone15-front-v2.jpg', 'ordering': 0},
        ],
        'characteristics': [{'name': 'Бренд', 'value': 'Apple'}],
    }


def test_edit_product_endpoint_returns_200(stub: StubCreateProductUseCase, edit_stub: StubEditProductUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))
    product_id = uuid4()

    response = client.patch(f'/api/v1/products/{product_id}', json=_edit_request_payload())

    assert response.status_code == 200
    body = response.json()
    # Stub возвращает фиксированный ответ.
    assert body['title'] == 'iPhone 15 Pro Max'
    assert body['status'] == ProductStatus.ON_MODERATION.value
    assert len(edit_stub.calls) == 1
    called_product_id, request_data, current_user = edit_stub.calls[0]
    assert called_product_id == product_id
    assert request_data.title == 'iPhone 15 Pro Max (обновлено)'
    assert current_user.id == user.id


def test_edit_product_unauthorized_returns_401(stub: StubCreateProductUseCase, edit_stub: StubEditProductUseCase):
    client = TestClient(_make_app(stub, user=None, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/products/{uuid4()}', json=_edit_request_payload())

    assert response.status_code == 401
    assert edit_stub.calls == []


def test_edit_product_non_seller_returns_403(stub: StubCreateProductUseCase, edit_stub: StubEditProductUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/products/{uuid4()}', json=_edit_request_payload())

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'
    assert edit_stub.calls == []


def test_edit_product_not_owner_returns_403(stub: StubCreateProductUseCase, edit_stub: StubEditProductUseCase):
    edit_stub.error = ProductNotOwnerError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/products/{uuid4()}', json=_edit_request_payload())

    assert response.status_code == 403
    assert response.json()['code'] == 'NOT_OWNER'


def test_edit_product_hard_blocked_returns_403(stub: StubCreateProductUseCase, edit_stub: StubEditProductUseCase):
    edit_stub.error = ProductHardBlockedError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/products/{uuid4()}', json=_edit_request_payload())

    assert response.status_code == 403
    assert response.json()['code'] == 'HARD_BLOCKED'


def test_edit_product_not_found_returns_404(stub: StubCreateProductUseCase, edit_stub: StubEditProductUseCase):
    edit_stub.error = ProductNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/products/{uuid4()}', json=_edit_request_payload())

    assert response.status_code == 404
    assert response.json()['code'] == 'NOT_FOUND'


def test_edit_product_invalid_category_returns_400(stub: StubCreateProductUseCase, edit_stub: StubEditProductUseCase):
    edit_stub.error = CategoryNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/products/{uuid4()}', json=_edit_request_payload())

    assert response.status_code == 400
    assert response.json()['code'] == 'INVALID_REQUEST'


def test_edit_product_validation_error_returns_400(stub: StubCreateProductUseCase, edit_stub: StubEditProductUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    # title слишком длинный (>255)
    payload = _edit_request_payload()
    payload['title'] = 'x' * 256

    response = client.patch(f'/api/v1/products/{uuid4()}', json=payload)

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}


def test_edit_product_partial_body_accepted(stub: StubCreateProductUseCase, edit_stub: StubEditProductUseCase):
    """ProductEditRequestSchema — все поля опциональны. Пустое тело валидно (хотя без эффекта)."""
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/products/{uuid4()}', json={})

    assert response.status_code == 200
    assert len(edit_stub.calls) == 1


# ===========================================================================
# DELETE /api/v1/products/{product_id} — US-B2B-04
# ===========================================================================


def test_delete_product_endpoint_returns_204(
    stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, delete_stub=delete_stub))
    product_id = uuid4()

    response = client.delete(f'/api/v1/products/{product_id}')

    assert response.status_code == 204
    assert response.content == b''
    assert len(delete_stub.calls) == 1
    called_id, called_user = delete_stub.calls[0]
    assert called_id == product_id
    assert called_user.id == user.id


def test_delete_product_unauthorized_returns_401(
    stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    client = TestClient(_make_app(stub, user=None, delete_stub=delete_stub))

    response = client.delete(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 401
    assert response.json() == {'code': 'UNAUTHORIZED', 'message': 'Unauthorized'}
    assert delete_stub.calls == []


def test_delete_product_non_seller_returns_403(
    stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(stub, user, delete_stub=delete_stub))

    response = client.delete(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'
    assert delete_stub.calls == []


def test_delete_product_not_owner_returns_403(
    stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    delete_stub.error = ProductNotOwnerError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, delete_stub=delete_stub))

    response = client.delete(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 403
    body = response.json()
    assert body['code'] == 'NOT_OWNER'


def test_delete_product_hard_blocked_returns_403(
    stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    delete_stub.error = ProductHardBlockedError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, delete_stub=delete_stub))

    response = client.delete(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 403
    body = response.json()
    assert body['code'] == 'HARD_BLOCKED'


def test_delete_product_already_deleted_returns_400(
    stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    delete_stub.error = ProductAlreadyDeletedError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, delete_stub=delete_stub))

    response = client.delete(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 400
    body = response.json()
    assert body['code'] == 'ALREADY_DELETED'
    assert body['message'] == 'Product already deleted'


def test_delete_product_not_found_returns_404(
    stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    delete_stub.error = ProductNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, delete_stub=delete_stub))

    response = client.delete(f'/api/v1/products/{uuid4()}')

    assert response.status_code == 404
    body = response.json()
    assert body['code'] == 'NOT_FOUND'


def test_delete_product_invalid_uuid_returns_422(
    stub: StubCreateProductUseCase,
    delete_stub: StubDeleteProductUseCase,
):
    """FastAPI валидация path-параметра возвращает 400 через наш RequestValidationError handler."""
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, delete_stub=delete_stub))

    response = client.delete('/api/v1/products/not-a-uuid')

    # validation_error_handler преобразует RequestValidationError в 400 INVALID_REQUEST
    assert response.status_code == 400
    body = response.json()
    assert body['code'] == 'INVALID_REQUEST'
