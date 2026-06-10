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
    SKUImagesRequiredError,
    SKUNotFoundError,
    SKUNotOwnerError,
)
from apps.skus.routers import router as skus_router
from apps.skus.schemas.request import SKUCreateRequestSchema, SKUEditRequestSchema
from apps.skus.schemas.response import (
    SKUCharacteristicResponseSchema,
    SKUImageResponseSchema,
    SKUResponseSchema,
)
from apps.skus.use_cases import CreateSKUUseCase, EditSKUUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _make_response() -> SKUResponseSchema:
    now = datetime.now(UTC)
    return SKUResponseSchema(
        id=uuid4(),
        product_id=uuid4(),
        name='256GB Black',
        price=12_999_000,
        cost_price=9_500_000,
        discount=0,
        article=None,
        active_quantity=0,
        reserved_quantity=0,
        stock_quantity=0,
        images=[
            SKUImageResponseSchema(id=uuid4(), url='/s3/iphone15-black-256.jpg', ordering=0),
        ],
        characteristics=[
            SKUCharacteristicResponseSchema(id=uuid4(), name='Цвет', value='Чёрный'),
        ],
        created_at=now,
        updated_at=now,
    )


class StubCreateSKUUseCase:
    def __init__(self):
        self.calls: list[tuple[SKUCreateRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.response = _make_response()

    async def __call__(
        self,
        data: SKUCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> SKUResponseSchema:
        self.calls.append((data, current_user))
        if self.error:
            raise self.error
        return self.response


class StubEditSKUUseCase:
    def __init__(self):
        self.calls: list[tuple[UUID, SKUEditRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.response = _make_response()

    async def __call__(
        self,
        sku_id: UUID,
        data: SKUEditRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> SKUResponseSchema:
        self.calls.append((sku_id, data, current_user))
        if self.error:
            raise self.error
        return self.response


class SKUsRouteProvider(Provider):
    def __init__(self, stub: StubCreateSKUUseCase, edit_stub: StubEditSKUUseCase):
        super().__init__()
        self.stub = stub
        self.edit_stub = edit_stub

    @provide(scope=Scope.REQUEST)
    def get_create_sku_use_case(self) -> CreateSKUUseCase:
        return self.stub

    @provide(scope=Scope.REQUEST)
    def get_edit_sku_use_case(self) -> EditSKUUseCase:
        return self.edit_stub


def _make_app(
    stub: StubCreateSKUUseCase,
    user: AuthenticatedUserSchema | None,
    edit_stub: StubEditSKUUseCase | None = None,
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
        SKUsRouteProvider(stub, edit_stub or StubEditSKUUseCase()),
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
    assert body['stock_quantity'] == 0
    assert len(body['images']) == 1
    assert len(body['characteristics']) == 1
    assert len(stub.calls) == 1
    request_data, current_user = stub.calls[0]
    assert request_data.name == '256GB Black'
    assert current_user.id == user.id


def test_create_sku_endpoint_response_includes_stock_quantity(stub: StubCreateSKUUseCase):
    """SKUResponse exposes stock_quantity per neomarket-protocols/b2b/openapi.yaml."""
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/skus', json=_request_payload())

    assert response.status_code == 201
    assert 'stock_quantity' in response.json()


def test_create_sku_without_cost_price_returns_201(stub: StubCreateSKUUseCase):
    """cost_price is optional per OpenAPI — omitting it must not 422."""
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    payload = _request_payload()
    payload.pop('cost_price')

    response = client.post('/api/v1/skus', json=payload)

    assert response.status_code == 201
    request_data, _ = stub.calls[0]
    assert request_data.cost_price is None


def test_create_sku_with_null_cost_price_returns_201(stub: StubCreateSKUUseCase):
    """cost_price is nullable per OpenAPI — explicit null must not 422."""
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    payload = _request_payload()
    payload['cost_price'] = None

    response = client.post('/api/v1/skus', json=payload)

    assert response.status_code == 201
    request_data, _ = stub.calls[0]
    assert request_data.cost_price is None


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


# ===========================================================================
# PUT /api/v1/skus/{sku_id} — US-B2B-03
# ===========================================================================


@pytest.fixture
def edit_stub() -> StubEditSKUUseCase:
    return StubEditSKUUseCase()


def _edit_request_payload() -> dict:
    return {
        'name': '256GB Black Titanium',
        'price': 13_499_000,
        'cost_price': 9_800_000,
        'discount': 500_000,
        'images': [
            {'url': '/s3/iphone15-black-titanium.jpg', 'ordering': 0},
        ],
        'characteristics': [
            {'name': 'Цвет', 'value': 'Чёрный титан'},
        ],
    }


def test_edit_sku_endpoint_returns_200(stub: StubCreateSKUUseCase, edit_stub: StubEditSKUUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))
    sku_id = uuid4()

    response = client.patch(f'/api/v1/skus/{sku_id}', json=_edit_request_payload())

    assert response.status_code == 200
    body = response.json()
    # Stub возвращает фиксированный ответ.
    assert body['name'] == '256GB Black'
    assert body['reserved_quantity'] == 0
    assert len(edit_stub.calls) == 1
    called_sku_id, request_data, current_user = edit_stub.calls[0]
    assert called_sku_id == sku_id
    assert request_data.name == '256GB Black Titanium'
    assert request_data.price == 13_499_000
    assert current_user.id == user.id


def test_edit_sku_unauthorized_returns_401(stub: StubCreateSKUUseCase, edit_stub: StubEditSKUUseCase):
    client = TestClient(_make_app(stub, user=None, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/skus/{uuid4()}', json=_edit_request_payload())

    assert response.status_code == 401
    assert edit_stub.calls == []


def test_edit_sku_non_seller_returns_403(stub: StubCreateSKUUseCase, edit_stub: StubEditSKUUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/skus/{uuid4()}', json=_edit_request_payload())

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'


def test_edit_sku_not_owner_returns_403(stub: StubCreateSKUUseCase, edit_stub: StubEditSKUUseCase):
    edit_stub.error = SKUNotOwnerError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/skus/{uuid4()}', json=_edit_request_payload())

    assert response.status_code == 403
    assert response.json()['code'] == 'NOT_OWNER'


def test_edit_sku_hard_blocked_returns_403(stub: StubCreateSKUUseCase, edit_stub: StubEditSKUUseCase):
    edit_stub.error = SKUHardBlockedError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/skus/{uuid4()}', json=_edit_request_payload())

    assert response.status_code == 403
    assert response.json()['code'] == 'HARD_BLOCKED'


def test_edit_sku_not_found_returns_404(stub: StubCreateSKUUseCase, edit_stub: StubEditSKUUseCase):
    edit_stub.error = SKUNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/skus/{uuid4()}', json=_edit_request_payload())

    assert response.status_code == 404
    assert response.json()['code'] == 'NOT_FOUND'


def test_edit_sku_validation_error_returns_400(stub: StubCreateSKUUseCase, edit_stub: StubEditSKUUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    payload = _edit_request_payload()
    payload['price'] = -100  # отрицательная цена недопустима (ge=0)

    response = client.patch(f'/api/v1/skus/{uuid4()}', json=payload)

    assert response.status_code == 400
    assert response.json()['code'] == 'INVALID_REQUEST'


def test_edit_sku_missing_images_returns_400(stub: StubCreateSKUUseCase, edit_stub: StubEditSKUUseCase):
    edit_stub.error = SKUImagesRequiredError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    payload = _edit_request_payload()
    payload['images'] = []

    response = client.patch(f'/api/v1/skus/{uuid4()}', json=payload)

    assert response.status_code == 400
    body = response.json()
    assert body['code'] == 'INVALID_REQUEST'


def test_edit_sku_partial_body_accepted(stub: StubCreateSKUUseCase, edit_stub: StubEditSKUUseCase):
    """SKUEditRequestSchema — все поля опциональны. Пустое тело валидно."""
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user, edit_stub=edit_stub))

    response = client.patch(f'/api/v1/skus/{uuid4()}', json={})

    assert response.status_code == 200
    assert len(edit_stub.calls) == 1
