from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.errors import setup_error_handlers
from apps.skus.errors import (
    ProductNotFoundError,
    SKUHardBlockedError,
    SKUHasActiveReservesError,
    SKUImagesRequiredError,
    SKUNotFoundError,
    SKUNotOwnerError,
)
from apps.skus.routers import router as skus_router
from apps.skus.schemas.request import SKUCreateRequestSchema
from apps.skus.schemas.response import (
    SKUCharacteristicResponseSchema,
    SKUImageResponseSchema,
    SKUResponseSchema,
)
from apps.skus.use_cases import CreateSKUUseCase, DeleteSKUUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole


class StubCreateSKUUseCase:
    def __init__(self):
        self.calls: list[tuple[SKUCreateRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        now = datetime.now(UTC)
        sku_id = uuid4()
        self.response = SKUResponseSchema(
            id=sku_id,
            product_id=uuid4(),
            name='256GB Black',
            price=12_999_000,
            cost_price=9_500_000,
            discount=0,
            article=None,
            active_quantity=0,
            reserved_quantity=0,
            images=[
                SKUImageResponseSchema(id=uuid4(), url='/s3/iphone15-black-256.jpg', ordering=0),
            ],
            characteristics=[
                SKUCharacteristicResponseSchema(id=uuid4(), name='Цвет', value='Чёрный'),
            ],
            created_at=now,
            updated_at=now,
        )

    async def __call__(
        self,
        data: SKUCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> SKUResponseSchema:
        self.calls.append((data, current_user))
        if self.error:
            raise self.error
        return self.response


class StubDeleteSKUUseCase:
    def __init__(self):
        self.calls: list[tuple[UUID, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None

    async def __call__(self, sku_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        self.calls.append((sku_id, current_user))
        if self.error:
            raise self.error
        return None


class SKUsRouteProvider(Provider):
    def __init__(
        self,
        create_stub: StubCreateSKUUseCase | None = None,
        delete_stub: StubDeleteSKUUseCase | None = None,
    ):
        super().__init__()
        self.create_stub = create_stub or StubCreateSKUUseCase()
        self.delete_stub = delete_stub or StubDeleteSKUUseCase()

    @provide(scope=Scope.REQUEST)
    def get_create_sku_use_case(self) -> CreateSKUUseCase:
        return self.create_stub

    @provide(scope=Scope.REQUEST)
    def get_delete_sku_use_case(self) -> DeleteSKUUseCase:
        return self.delete_stub


def _make_app(
    stub: StubCreateSKUUseCase | None,
    user: AuthenticatedUserSchema | None,
    delete_stub: StubDeleteSKUUseCase | None = None,
) -> FastAPI:
    from starlette.middleware.base import BaseHTTPMiddleware

    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(skus_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        SKUsRouteProvider(create_stub=stub, delete_stub=delete_stub),
    )
    setup_dishka(container, app)
    return app


def _request_payload(product_id: UUID | None = None) -> dict:
    return {
        'product_id': str(product_id or uuid4()),
        'name': '256GB Black',
        'price': 12_999_000,
        'cost_price': 9_500_000,
        'discount': 0,
        'stock_quantity': 0,
        'images': [
            {'url': '/s3/iphone15-black-256.jpg', 'ordering': 0},
        ],
        'characteristics': [
            {'name': 'Цвет', 'value': 'Чёрный'},
        ],
    }


@pytest.fixture
def stub() -> StubCreateSKUUseCase:
    return StubCreateSKUUseCase()


def test_create_sku_endpoint_returns_201(stub: StubCreateSKUUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/skus', json=_request_payload())

    assert response.status_code == 201
    body = response.json()
    assert body['name'] == '256GB Black'
    assert body['price'] == 12_999_000
    assert body['cost_price'] == 9_500_000
    assert body['active_quantity'] == 0
    assert body['reserved_quantity'] == 0
    assert len(body['images']) == 1
    assert len(body['characteristics']) == 1
    assert len(stub.calls) == 1
    request_data, current_user = stub.calls[0]
    assert request_data.name == '256GB Black'
    assert current_user.id == user.id


def test_create_sku_unauthorized_returns_401(stub: StubCreateSKUUseCase):
    client = TestClient(_make_app(stub, user=None))

    response = client.post('/api/v1/skus', json=_request_payload())

    assert response.status_code == 401
    assert response.json() == {'code': 'UNAUTHORIZED', 'message': 'Unauthorized'}
    assert stub.calls == []


def test_create_sku_non_seller_returns_403(stub: StubCreateSKUUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/skus', json=_request_payload())

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'
    assert stub.calls == []


def test_create_sku_validation_error_returns_400(stub: StubCreateSKUUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    # отсутствуют обязательные поля
    response = client.post('/api/v1/skus', json={})

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}


def test_create_sku_hard_blocked_returns_403(stub: StubCreateSKUUseCase):
    stub.error = SKUHardBlockedError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/skus', json=_request_payload())

    assert response.status_code == 403
    body = response.json()
    assert body['code'] == 'HARD_BLOCKED'


def test_create_sku_not_owner_returns_403(stub: StubCreateSKUUseCase):
    stub.error = SKUNotOwnerError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/skus', json=_request_payload())

    assert response.status_code == 403
    body = response.json()
    assert body['code'] == 'NOT_OWNER'


def test_create_sku_product_not_found_returns_404(stub: StubCreateSKUUseCase):
    stub.error = ProductNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/skus', json=_request_payload())

    assert response.status_code == 404
    body = response.json()
    assert body['code'] == 'NOT_FOUND'


def test_create_sku_missing_images_returns_400(stub: StubCreateSKUUseCase):
    stub.error = SKUImagesRequiredError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    payload = _request_payload()
    payload['images'] = []

    response = client.post('/api/v1/skus', json=payload)

    assert response.status_code == 400
    body = response.json()
    assert body['code'] == 'INVALID_REQUEST'
    assert body['message'] == 'Требуется минимум одно изображение'


# --- DELETE /api/v1/skus/{sku_id} ---


@pytest.fixture
def delete_stub() -> StubDeleteSKUUseCase:
    return StubDeleteSKUUseCase()


def test_delete_sku_endpoint_returns_204(delete_stub: StubDeleteSKUUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub=None, user=user, delete_stub=delete_stub))
    sku_id = uuid4()

    response = client.delete(f'/api/v1/skus/{sku_id}')

    assert response.status_code == 204
    assert response.content == b''
    assert len(delete_stub.calls) == 1
    called_sku_id, called_user = delete_stub.calls[0]
    assert called_sku_id == sku_id
    assert called_user.id == user.id


def test_delete_sku_unauthorized_returns_401(delete_stub: StubDeleteSKUUseCase):
    client = TestClient(_make_app(stub=None, user=None, delete_stub=delete_stub))

    response = client.delete(f'/api/v1/skus/{uuid4()}')

    assert response.status_code == 401
    assert response.json() == {'code': 'UNAUTHORIZED', 'message': 'Unauthorized'}
    assert delete_stub.calls == []


def test_delete_sku_non_seller_returns_403(delete_stub: StubDeleteSKUUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(stub=None, user=user, delete_stub=delete_stub))

    response = client.delete(f'/api/v1/skus/{uuid4()}')

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'
    assert delete_stub.calls == []


def test_delete_sku_not_found_returns_404(delete_stub: StubDeleteSKUUseCase):
    delete_stub.error = SKUNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub=None, user=user, delete_stub=delete_stub))

    response = client.delete(f'/api/v1/skus/{uuid4()}')

    assert response.status_code == 404
    assert response.json()['code'] == 'NOT_FOUND'


def test_delete_sku_not_owner_returns_403(delete_stub: StubDeleteSKUUseCase):
    delete_stub.error = SKUNotOwnerError(message='SKU does not belong to the authenticated seller')
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub=None, user=user, delete_stub=delete_stub))

    response = client.delete(f'/api/v1/skus/{uuid4()}')

    assert response.status_code == 403
    assert response.json()['code'] == 'NOT_OWNER'


def test_delete_sku_hard_blocked_returns_403(delete_stub: StubDeleteSKUUseCase):
    delete_stub.error = SKUHardBlockedError(message='Cannot delete SKU of hard-blocked product')
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub=None, user=user, delete_stub=delete_stub))

    response = client.delete(f'/api/v1/skus/{uuid4()}')

    assert response.status_code == 403
    assert response.json()['code'] == 'HARD_BLOCKED'


def test_delete_sku_active_reserves_returns_409(delete_stub: StubDeleteSKUUseCase):
    delete_stub.error = SKUHasActiveReservesError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub=None, user=user, delete_stub=delete_stub))

    response = client.delete(f'/api/v1/skus/{uuid4()}')

    assert response.status_code == 409
    body = response.json()
    assert body['code'] == 'HAS_ACTIVE_RESERVES'
    assert body['message'] == 'Cannot delete SKU with active reserves'


def test_delete_sku_invalid_uuid_returns_400(delete_stub: StubDeleteSKUUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub=None, user=user, delete_stub=delete_stub))

    response = client.delete('/api/v1/skus/not-a-uuid')

    assert response.status_code == 400
    assert response.json()['code'] == 'INVALID_REQUEST'
    assert delete_stub.calls == []
