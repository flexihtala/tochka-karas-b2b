from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.errors import setup_error_handlers
from apps.payment_methods.errors import PaymentMethodNotFoundError
from apps.payment_methods.routers import router as payment_methods_router
from apps.payment_methods.schemas.request import (
    PaymentMethodCreateRequestSchema,
    PaymentMethodUpdateRequestSchema,
)
from apps.payment_methods.schemas.response import PaymentMethodResponseSchema
from apps.payment_methods.use_cases import (
    CreatePaymentMethodUseCase,
    DeletePaymentMethodUseCase,
    ListPaymentMethodsUseCase,
    UpdatePaymentMethodUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _make_response(buyer_id: UUID, method_id: UUID | None = None) -> PaymentMethodResponseSchema:
    now = datetime.now(UTC)
    return PaymentMethodResponseSchema(
        id=method_id or uuid4(),
        buyer_id=buyer_id,
        brand='VISA',
        last4='4242',
        exp_year=2030,
        exp_month=12,
        is_default=False,
        created_at=now,
        updated_at=now,
    )


class StubListPaymentMethods:
    def __init__(self):
        self.calls: list[AuthenticatedUserSchema] = []
        self.response: list[PaymentMethodResponseSchema] = []

    async def __call__(self, current_user: AuthenticatedUserSchema) -> list[PaymentMethodResponseSchema]:
        self.calls.append(current_user)
        return self.response


class StubCreatePaymentMethod:
    def __init__(self):
        self.calls: list[tuple[PaymentMethodCreateRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.response: PaymentMethodResponseSchema | None = None

    async def __call__(
        self,
        data: PaymentMethodCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> PaymentMethodResponseSchema:
        self.calls.append((data, current_user))
        if self.error:
            raise self.error
        return self.response or _make_response(current_user.id)


class StubUpdatePaymentMethod:
    def __init__(self):
        self.calls: list[tuple[UUID, PaymentMethodUpdateRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.response: PaymentMethodResponseSchema | None = None

    async def __call__(
        self,
        method_id: UUID,
        data: PaymentMethodUpdateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> PaymentMethodResponseSchema:
        self.calls.append((method_id, data, current_user))
        if self.error:
            raise self.error
        return self.response or _make_response(current_user.id, method_id)


class StubDeletePaymentMethod:
    def __init__(self):
        self.calls: list[tuple[UUID, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None

    async def __call__(self, method_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        self.calls.append((method_id, current_user))
        if self.error:
            raise self.error


class PaymentMethodsRouteProvider(Provider):
    def __init__(
        self,
        list_stub: StubListPaymentMethods,
        create_stub: StubCreatePaymentMethod,
        update_stub: StubUpdatePaymentMethod,
        delete_stub: StubDeletePaymentMethod,
    ):
        super().__init__()
        self.list_stub = list_stub
        self.create_stub = create_stub
        self.update_stub = update_stub
        self.delete_stub = delete_stub

    @provide(scope=Scope.REQUEST)
    def get_list_use_case(self) -> ListPaymentMethodsUseCase:
        return self.list_stub

    @provide(scope=Scope.REQUEST)
    def get_create_use_case(self) -> CreatePaymentMethodUseCase:
        return self.create_stub

    @provide(scope=Scope.REQUEST)
    def get_update_use_case(self) -> UpdatePaymentMethodUseCase:
        return self.update_stub

    @provide(scope=Scope.REQUEST)
    def get_delete_use_case(self) -> DeletePaymentMethodUseCase:
        return self.delete_stub


def _make_app(
    list_stub: StubListPaymentMethods,
    create_stub: StubCreatePaymentMethod,
    update_stub: StubUpdatePaymentMethod,
    delete_stub: StubDeletePaymentMethod,
    user: AuthenticatedUserSchema | None,
) -> FastAPI:
    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(payment_methods_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        PaymentMethodsRouteProvider(list_stub, create_stub, update_stub, delete_stub),
    )
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs():
    return (
        StubListPaymentMethods(),
        StubCreatePaymentMethod(),
        StubUpdatePaymentMethod(),
        StubDeletePaymentMethod(),
    )


def _create_payload() -> dict:
    return {
        'brand': 'VISA',
        'last4': '4242',
        'exp_year': 2030,
        'exp_month': 12,
        'is_default': False,
    }


def test_list_payment_methods_returns_buyer_methods(stubs):
    list_stub, create_stub, update_stub, delete_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    list_stub.response = [_make_response(user.id)]
    client = TestClient(_make_app(*stubs, user=user))

    response = client.get('/api/v1/buyers/me/payment-methods')

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]['brand'] == 'VISA'


def test_list_payment_methods_unauthorized_returns_401(stubs):
    client = TestClient(_make_app(*stubs, user=None))

    response = client.get('/api/v1/buyers/me/payment-methods')

    assert response.status_code == 401


def test_create_payment_method_returns_201(stubs):
    list_stub, create_stub, update_stub, delete_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.post('/api/v1/buyers/me/payment-methods', json=_create_payload())

    assert response.status_code == 201
    body = response.json()
    assert body['brand'] == 'VISA'
    assert body['last4'] == '4242'
    assert create_stub.calls[0][0].brand == 'VISA'


def test_create_payment_method_rejects_invalid_last4(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    payload = _create_payload()
    payload['last4'] = '12ab'

    response = client.post('/api/v1/buyers/me/payment-methods', json=payload)

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}


def test_create_payment_method_rejects_invalid_month(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    payload = _create_payload()
    payload['exp_month'] = 13

    response = client.post('/api/v1/buyers/me/payment-methods', json=payload)

    assert response.status_code == 400


def test_create_payment_method_non_buyer_returns_403(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.post('/api/v1/buyers/me/payment-methods', json=_create_payload())

    assert response.status_code == 403


def test_update_payment_method_returns_200(stubs):
    list_stub, create_stub, update_stub, delete_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    method_id = uuid4()
    client = TestClient(_make_app(*stubs, user=user))

    response = client.patch(f'/api/v1/buyers/me/payment-methods/{method_id}', json={'is_default': True})

    assert response.status_code == 200
    assert update_stub.calls[0][0] == method_id
    assert update_stub.calls[0][1].is_default is True


def test_delete_payment_method_returns_204(stubs):
    list_stub, create_stub, update_stub, delete_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    method_id = uuid4()
    client = TestClient(_make_app(*stubs, user=user))

    response = client.delete(f'/api/v1/buyers/me/payment-methods/{method_id}')

    assert response.status_code == 204
    assert delete_stub.calls[0][0] == method_id


def test_delete_payment_method_returns_404_when_not_owned(stubs):
    list_stub, create_stub, update_stub, delete_stub = stubs
    delete_stub.error = PaymentMethodNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.delete(f'/api/v1/buyers/me/payment-methods/{uuid4()}')

    assert response.status_code == 404
    assert response.json() == {'code': 'NOT_FOUND', 'message': 'Платёжный метод не найден'}
