from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.errors import setup_error_handlers
from apps.subscriptions.errors import (
    ProductNotFoundError,
    SubscriptionAlreadyExistsError,
    SubscriptionNotFoundError,
)
from apps.subscriptions.routers import router as subscriptions_router
from apps.subscriptions.schemas.request import SubscriptionCreateRequestSchema
from apps.subscriptions.schemas.response import SubscriptionResponseSchema
from apps.subscriptions.use_cases import SubscribeUseCase, UnsubscribeUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _make_response(
    user_id: UUID,
    product_id: UUID | None = None,
    notify_on: list[str] | None = None,
) -> SubscriptionResponseSchema:
    now = datetime.now(UTC)
    return SubscriptionResponseSchema(
        id=uuid4(),
        user_id=user_id,
        product_id=product_id or uuid4(),
        notify_on=notify_on or ['PRICE_DROP', 'BACK_IN_STOCK'],
        created_at=now,
        updated_at=now,
    )


class StubSubscribe:
    def __init__(self):
        self.calls: list[tuple[SubscriptionCreateRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.response: SubscriptionResponseSchema | None = None

    async def __call__(
        self,
        data: SubscriptionCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> SubscriptionResponseSchema:
        self.calls.append((data, current_user))
        if self.error:
            raise self.error
        return self.response or _make_response(current_user.id, data.product_id, data.notify_on)


class StubUnsubscribe:
    def __init__(self):
        self.calls: list[tuple[UUID, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None

    async def __call__(self, product_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        self.calls.append((product_id, current_user))
        if self.error:
            raise self.error


class SubscriptionsRouteProvider(Provider):
    def __init__(self, subscribe_stub: StubSubscribe, unsubscribe_stub: StubUnsubscribe):
        super().__init__()
        self.subscribe_stub = subscribe_stub
        self.unsubscribe_stub = unsubscribe_stub

    @provide(scope=Scope.REQUEST)
    def get_subscribe_use_case(self) -> SubscribeUseCase:
        return self.subscribe_stub

    @provide(scope=Scope.REQUEST)
    def get_unsubscribe_use_case(self) -> UnsubscribeUseCase:
        return self.unsubscribe_stub


def _make_app(
    subscribe_stub: StubSubscribe,
    unsubscribe_stub: StubUnsubscribe,
    user: AuthenticatedUserSchema | None,
) -> FastAPI:
    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(subscriptions_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        SubscriptionsRouteProvider(subscribe_stub, unsubscribe_stub),
    )
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs():
    return (StubSubscribe(), StubUnsubscribe())


def _create_payload(notify_on: list[str] | None = None, product_id: UUID | None = None) -> dict:
    return {
        'product_id': str(product_id or uuid4()),
        'notify_on': notify_on if notify_on is not None else ['PRICE_DROP', 'BACK_IN_STOCK'],
    }


def test_subscribe_returns_201_with_notify_on(stubs):
    subscribe_stub, unsubscribe_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(subscribe_stub, unsubscribe_stub, user=user))

    payload = _create_payload(notify_on=['PRICE_DROP', 'BACK_IN_STOCK'])
    response = client.post('/api/v1/subscriptions', json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body['user_id'] == str(user.id)
    assert body['product_id'] == payload['product_id']
    assert body['notify_on'] == ['PRICE_DROP', 'BACK_IN_STOCK']
    # user_id берётся из JWT, а не из тела
    assert subscribe_stub.calls[0][0].product_id == UUID(payload['product_id'])
    assert subscribe_stub.calls[0][0].notify_on == ['PRICE_DROP', 'BACK_IN_STOCK']
    assert subscribe_stub.calls[0][1].id == user.id


def test_duplicate_subscription_returns_409(stubs):
    subscribe_stub, unsubscribe_stub = stubs
    subscribe_stub.error = SubscriptionAlreadyExistsError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(subscribe_stub, unsubscribe_stub, user=user))

    response = client.post('/api/v1/subscriptions', json=_create_payload())

    assert response.status_code == 409
    assert response.json() == {
        'code': 'SUBSCRIPTION_ALREADY_EXISTS',
        'message': 'Подписка уже существует',
    }


def test_invalid_notify_on_returns_400(stubs):
    subscribe_stub, unsubscribe_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(subscribe_stub, unsubscribe_stub, user=user))

    response = client.post(
        '/api/v1/subscriptions',
        json=_create_payload(notify_on=['NOT_A_REAL_EVENT']),
    )

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}
    assert subscribe_stub.calls == []


def test_subscribe_to_unknown_product_returns_404(stubs):
    """Слой routers/use_case даёт 404 PRODUCT_NOT_FOUND если бизнес-логика
    решит, что товар не существует (например, при опциональной проверке через
    ServiceClient к B2B). По умолчанию B2C принимает любой валидный UUID,
    верификация — в B2B/inbox, но протокол требует возможности 404.
    """
    subscribe_stub, unsubscribe_stub = stubs
    subscribe_stub.error = ProductNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(subscribe_stub, unsubscribe_stub, user=user))

    response = client.post('/api/v1/subscriptions', json=_create_payload())

    assert response.status_code == 404
    assert response.json() == {'code': 'PRODUCT_NOT_FOUND', 'message': 'Товар не найден'}


def test_subscribe_unauthorized_returns_401(stubs):
    subscribe_stub, unsubscribe_stub = stubs
    client = TestClient(_make_app(subscribe_stub, unsubscribe_stub, user=None))

    response = client.post('/api/v1/subscriptions', json=_create_payload())

    assert response.status_code == 401


def test_subscribe_non_buyer_returns_403(stubs):
    subscribe_stub, unsubscribe_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(subscribe_stub, unsubscribe_stub, user=user))

    response = client.post('/api/v1/subscriptions', json=_create_payload())

    assert response.status_code == 403


def test_unsubscribe_returns_204(stubs):
    subscribe_stub, unsubscribe_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    product_id = uuid4()
    client = TestClient(_make_app(subscribe_stub, unsubscribe_stub, user=user))

    response = client.delete(f'/api/v1/subscriptions/{product_id}')

    assert response.status_code == 204
    assert unsubscribe_stub.calls[0][0] == product_id
    assert unsubscribe_stub.calls[0][1].id == user.id


def test_unsubscribe_returns_404_when_no_subscription(stubs):
    subscribe_stub, unsubscribe_stub = stubs
    unsubscribe_stub.error = SubscriptionNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(subscribe_stub, unsubscribe_stub, user=user))

    response = client.delete(f'/api/v1/subscriptions/{uuid4()}')

    assert response.status_code == 404
    assert response.json() == {
        'code': 'SUBSCRIPTION_NOT_FOUND',
        'message': 'Подписка не найдена',
    }


def test_subscribe_rejects_empty_notify_on(stubs):
    subscribe_stub, unsubscribe_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(subscribe_stub, unsubscribe_stub, user=user))

    response = client.post('/api/v1/subscriptions', json=_create_payload(notify_on=[]))

    assert response.status_code == 400
    assert subscribe_stub.calls == []
