from datetime import UTC, datetime
from uuid import uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.buyers.errors import BuyerNotFoundError
from apps.buyers.routers import router as buyers_router
from apps.buyers.schemas.request import BuyerUpdateRequestSchema
from apps.buyers.schemas.response import BuyerResponseSchema
from apps.buyers.use_cases import GetBuyerUseCase, UpdateBuyerUseCase
from apps.errors import setup_error_handlers
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _make_response(user_id: uuid4) -> BuyerResponseSchema:
    now = datetime.now(UTC)
    return BuyerResponseSchema(
        id=user_id,
        email='buyer@example.com',
        first_name='Ivan',
        last_name='Ivanov',
        phone='+79001234567',
        is_active=True,
        created_at=now,
        updated_at=now,
    )


class StubGetBuyerUseCase:
    def __init__(self):
        self.calls: list[AuthenticatedUserSchema] = []
        self.error: Exception | None = None
        self.response: BuyerResponseSchema | None = None

    async def __call__(self, current_user: AuthenticatedUserSchema) -> BuyerResponseSchema:
        self.calls.append(current_user)
        if self.error:
            raise self.error
        return self.response or _make_response(current_user.id)


class StubUpdateBuyerUseCase:
    def __init__(self):
        self.calls: list[tuple[BuyerUpdateRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.response: BuyerResponseSchema | None = None

    async def __call__(
        self,
        data: BuyerUpdateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> BuyerResponseSchema:
        self.calls.append((data, current_user))
        if self.error:
            raise self.error
        return self.response or _make_response(current_user.id)


class BuyersRouteProvider(Provider):
    def __init__(self, get_stub: StubGetBuyerUseCase, update_stub: StubUpdateBuyerUseCase):
        super().__init__()
        self.get_stub = get_stub
        self.update_stub = update_stub

    @provide(scope=Scope.REQUEST)
    def get_get_use_case(self) -> GetBuyerUseCase:
        return self.get_stub

    @provide(scope=Scope.REQUEST)
    def get_update_use_case(self) -> UpdateBuyerUseCase:
        return self.update_stub


def _make_app(
    get_stub: StubGetBuyerUseCase,
    update_stub: StubUpdateBuyerUseCase,
    user: AuthenticatedUserSchema | None,
) -> FastAPI:
    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(buyers_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), BuyersRouteProvider(get_stub, update_stub))
    setup_dishka(container, app)
    return app


@pytest.fixture
def get_stub() -> StubGetBuyerUseCase:
    return StubGetBuyerUseCase()


@pytest.fixture
def update_stub() -> StubUpdateBuyerUseCase:
    return StubUpdateBuyerUseCase()


def test_get_me_returns_buyer_profile(get_stub: StubGetBuyerUseCase, update_stub: StubUpdateBuyerUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(get_stub, update_stub, user))

    response = client.get('/api/v1/buyers/me')

    assert response.status_code == 200
    body = response.json()
    assert body['email'] == 'buyer@example.com'
    assert body['id'] == str(user.id)
    assert get_stub.calls[0].id == user.id


def test_get_me_unauthorized_returns_401(get_stub: StubGetBuyerUseCase, update_stub: StubUpdateBuyerUseCase):
    client = TestClient(_make_app(get_stub, update_stub, user=None))

    response = client.get('/api/v1/buyers/me')

    assert response.status_code == 401
    assert response.json() == {'code': 'UNAUTHORIZED', 'message': 'Unauthorized'}
    assert get_stub.calls == []


def test_get_me_non_buyer_returns_403(get_stub: StubGetBuyerUseCase, update_stub: StubUpdateBuyerUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(get_stub, update_stub, user))

    response = client.get('/api/v1/buyers/me')

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'
    assert get_stub.calls == []


def test_get_me_returns_404_when_buyer_record_missing(
    get_stub: StubGetBuyerUseCase, update_stub: StubUpdateBuyerUseCase
):
    get_stub.error = BuyerNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(get_stub, update_stub, user))

    response = client.get('/api/v1/buyers/me')

    assert response.status_code == 404
    assert response.json() == {'code': 'NOT_FOUND', 'message': 'Покупатель не найден'}


def test_patch_me_updates_profile(get_stub: StubGetBuyerUseCase, update_stub: StubUpdateBuyerUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(get_stub, update_stub, user))

    response = client.patch('/api/v1/buyers/me', json={'first_name': 'Petr'})

    assert response.status_code == 200
    assert update_stub.calls[0][0].first_name == 'Petr'
    assert update_stub.calls[0][1].id == user.id


def test_patch_me_validation_error_returns_400(get_stub: StubGetBuyerUseCase, update_stub: StubUpdateBuyerUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(get_stub, update_stub, user))

    response = client.patch('/api/v1/buyers/me', json={'phone': 'not-a-phone'})

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}
    assert update_stub.calls == []
