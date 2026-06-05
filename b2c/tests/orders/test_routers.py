from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.addresses.schemas.response import AddressResponseSchema
from apps.errors import setup_error_handlers
from apps.orders.errors import (
    B2BUnavailableError,
    CartInvalidError,
    InvalidAddressError,
    ReserveFailedError,
)
from apps.orders.routers import router as orders_router
from apps.orders.schemas.request import OrderCreateRequestSchema
from apps.orders.schemas.response import OrderItemResponseSchema, OrderResponseSchema
from apps.orders.use_cases import CheckoutUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _make_address_response(buyer_id: UUID) -> AddressResponseSchema:
    now = datetime.now(UTC)
    return AddressResponseSchema(
        id=uuid4(),
        buyer_id=buyer_id,
        country='RU',
        city='Екатеринбург',
        street='ул. Мира 19',
        postal_code='620000',
        comment=None,
        is_default=True,
        created_at=now,
        updated_at=now,
    )


def _make_order_response(buyer_id: UUID, order_id: UUID | None = None) -> OrderResponseSchema:
    now = datetime.now(UTC)
    sku_id = uuid4()
    return OrderResponseSchema(
        id=order_id or uuid4(),
        buyer_id=buyer_id,
        status='PAID',
        items=[
            OrderItemResponseSchema(
                sku_id=sku_id,
                product_id=uuid4(),
                name='Phone 128GB',
                quantity=2,
                unit_price=10_000,
                line_total=20_000,
            ),
        ],
        subtotal=20_000,
        total=20_000,
        address=_make_address_response(buyer_id),
        payment_method=None,
        comment=None,
        created_at=now,
        paid_at=now,
    )


class StubCheckoutUseCase:
    def __init__(self):
        self.calls: list[tuple[UUID, OrderCreateRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.response: tuple[OrderResponseSchema, bool] | None = None

    async def __call__(
        self,
        *,
        idempotency_key: UUID,
        data: OrderCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> tuple[OrderResponseSchema, bool]:
        self.calls.append((idempotency_key, data, current_user))
        if self.error:
            raise self.error
        if self.response is None:
            return _make_order_response(current_user.id), True
        return self.response


class OrdersRouteProvider(Provider):
    def __init__(self, checkout_stub: StubCheckoutUseCase):
        super().__init__()
        self.checkout_stub = checkout_stub

    @provide(scope=Scope.REQUEST)
    def get_checkout(self) -> CheckoutUseCase:
        return self.checkout_stub


def _make_app(checkout_stub: StubCheckoutUseCase, user: AuthenticatedUserSchema | None) -> FastAPI:
    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(orders_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        OrdersRouteProvider(checkout_stub),
    )
    setup_dishka(container, app)
    return app


@pytest.fixture
def checkout_stub():
    return StubCheckoutUseCase()


def _payload(**overrides) -> dict:
    base = {'address_id': str(uuid4()), 'payment_method_id': str(uuid4())}
    base.update(overrides)
    return base


def _headers(key: UUID | None = None) -> dict:
    return {'Idempotency-Key': str(key or uuid4())}


def test_checkout_creates_order_returns_201(checkout_stub):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(checkout_stub, user=user))

    response = client.post('/api/v1/orders', json=_payload(), headers=_headers())

    assert response.status_code == 201
    body = response.json()
    assert body['status'] == 'PAID'
    assert len(body['items']) == 1
    assert checkout_stub.calls[0][2].id == user.id


def test_checkout_idempotent_replay_returns_200(checkout_stub):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    checkout_stub.response = (_make_order_response(user.id), False)
    client = TestClient(_make_app(checkout_stub, user=user))

    response = client.post('/api/v1/orders', json=_payload(), headers=_headers())

    assert response.status_code == 200


def test_checkout_missing_idempotency_key_returns_400(checkout_stub):
    """Spec: Idempotency-Key header is required; missing → 400 INVALID_REQUEST."""
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(checkout_stub, user=user))

    response = client.post('/api/v1/orders', json=_payload())

    assert response.status_code == 400
    assert response.json()['code'] == 'INVALID_REQUEST'


def test_checkout_unauthorized_returns_401(checkout_stub):
    client = TestClient(_make_app(checkout_stub, user=None))
    response = client.post('/api/v1/orders', json=_payload(), headers=_headers())
    assert response.status_code == 401


def test_checkout_non_buyer_returns_403(checkout_stub):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(checkout_stub, user=user))
    response = client.post('/api/v1/orders', json=_payload(), headers=_headers())
    assert response.status_code == 403


def test_checkout_missing_address_id_returns_400(checkout_stub):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(checkout_stub, user=user))
    response = client.post(
        '/api/v1/orders',
        json={'payment_method_id': str(uuid4())},
        headers=_headers(),
    )
    assert response.status_code == 400


def test_checkout_reserve_failed_returns_409_with_failed_items(checkout_stub):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    sku_id = uuid4()
    checkout_stub.error = ReserveFailedError(
        failed_items=[
            {'sku_id': str(sku_id), 'requested': 5, 'available': 1, 'reason': 'INSUFFICIENT_STOCK'},
        ],
    )
    client = TestClient(_make_app(checkout_stub, user=user))

    response = client.post('/api/v1/orders', json=_payload(), headers=_headers())

    assert response.status_code == 409
    body = response.json()
    assert body['code'] == 'RESERVE_FAILED'
    assert body['failed_items'][0]['sku_id'] == str(sku_id)


def test_checkout_cart_invalid_returns_422(checkout_stub):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    sku_id = uuid4()
    checkout_stub.error = CartInvalidError(
        issues=[{'sku_id': str(sku_id), 'type': 'OUT_OF_STOCK', 'message': 'Нет в наличии'}],
    )
    client = TestClient(_make_app(checkout_stub, user=user))

    response = client.post('/api/v1/orders', json=_payload(), headers=_headers())

    assert response.status_code == 422
    body = response.json()
    assert body['code'] == 'CART_INVALID'
    assert body['details']['issues'][0]['sku_id'] == str(sku_id)


def test_checkout_invalid_address_returns_400(checkout_stub):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    checkout_stub.error = InvalidAddressError()
    client = TestClient(_make_app(checkout_stub, user=user))

    response = client.post('/api/v1/orders', json=_payload(), headers=_headers())

    assert response.status_code == 400
    assert response.json()['code'] == 'INVALID_ADDRESS'


def test_checkout_b2b_unavailable_returns_503(checkout_stub):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    checkout_stub.error = B2BUnavailableError()
    client = TestClient(_make_app(checkout_stub, user=user))

    response = client.post('/api/v1/orders', json=_payload(), headers=_headers())

    assert response.status_code == 503
    body = response.json()
    assert body['code'] == 'B2B_UNAVAILABLE'


def test_checkout_idempotency_key_header_passed_to_use_case(checkout_stub):
    """Spec: Idempotency-Key is a header; it is forwarded to the use case verbatim."""
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(checkout_stub, user=user))
    header_key = uuid4()

    response = client.post('/api/v1/orders', json=_payload(), headers=_headers(header_key))

    assert response.status_code == 201
    assert checkout_stub.calls[0][0] == header_key


def test_checkout_response_uses_spec_field_names(checkout_stub):
    """Spec OrderResponse: `total`, `buyer_id`, `subtotal`, `address`, item.name."""
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(checkout_stub, user=user))

    response = client.post('/api/v1/orders', json=_payload(), headers=_headers())

    assert response.status_code == 201
    body = response.json()
    assert 'total' in body
    assert 'buyer_id' in body
    assert 'subtotal' in body
    assert 'address' in body
    assert body['subtotal'] == sum(it['line_total'] for it in body['items'])
    assert 'name' in body['items'][0]
