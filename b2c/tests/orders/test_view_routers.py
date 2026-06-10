"""US-ORD-02 router tests: GET /orders, GET /orders/{id}."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.errors import setup_error_handlers
from apps.orders.errors import OrderNotFoundError
from apps.orders.routers import router as orders_router
from apps.orders.schemas.response import (
    OrderItemResponseSchema,
    OrderListItemResponseSchema,
    OrderListResponseSchema,
    OrderResponseSchema,
)
from apps.addresses.schemas.response import AddressResponseSchema
from apps.orders.use_cases import CheckoutUseCase, GetOrderUseCase, ListOrdersUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _make_address(buyer_id: UUID) -> AddressResponseSchema:
    now = datetime.now(UTC)
    return AddressResponseSchema(
        id=uuid4(),
        buyer_id=buyer_id,
        country='RU',
        city='Екатеринбург',
        street='Мира 19',
        postal_code='620000',
        comment=None,
        is_default=True,
        created_at=now,
        updated_at=now,
    )


def _make_order(order_id: UUID | None = None) -> OrderResponseSchema:
    now = datetime.now(UTC)
    buyer_id = uuid4()
    return OrderResponseSchema(
        id=order_id or uuid4(),
        buyer_id=buyer_id,
        status='PAID',
        items=[
            OrderItemResponseSchema(
                sku_id=uuid4(),
                product_id=uuid4(),
                name='Phone 128GB',
                quantity=1,
                unit_price=10_000,
                line_total=10_000,
            ),
        ],
        subtotal=10_000,
        total=10_000,
        address=_make_address(buyer_id),
        payment_method=None,
        comment=None,
        cancel_reason=None,
        created_at=now,
        paid_at=now,
    )


class StubListOrders:
    def __init__(self):
        self.calls: list[dict] = []
        self.response = OrderListResponseSchema(items=[], total_count=0, limit=20, offset=0)

    async def __call__(
        self,
        current_user: AuthenticatedUserSchema,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> OrderListResponseSchema:
        self.calls.append({'user_id': current_user.id, 'status': status, 'limit': limit, 'offset': offset})
        return self.response


class StubGetOrder:
    def __init__(self):
        self.calls: list[tuple[UUID, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.response: OrderResponseSchema | None = None

    async def __call__(self, order_id: UUID, current_user: AuthenticatedUserSchema) -> OrderResponseSchema:
        self.calls.append((order_id, current_user))
        if self.error:
            raise self.error
        return self.response or _make_order(order_id)


class StubCheckout:
    async def __call__(self, *args, **kwargs):  # not used here
        raise NotImplementedError


class OrdersRouteProvider(Provider):
    def __init__(self, list_stub: StubListOrders, get_stub: StubGetOrder):
        super().__init__()
        self.list_stub = list_stub
        self.get_stub = get_stub

    @provide(scope=Scope.REQUEST)
    def get_checkout(self) -> CheckoutUseCase:
        return StubCheckout()  # type: ignore[return-value]

    @provide(scope=Scope.REQUEST)
    def get_list(self) -> ListOrdersUseCase:
        return self.list_stub  # type: ignore[return-value]

    @provide(scope=Scope.REQUEST)
    def get_detail(self) -> GetOrderUseCase:
        return self.get_stub  # type: ignore[return-value]


def _make_app(list_stub, get_stub, user) -> FastAPI:
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
        OrdersRouteProvider(list_stub, get_stub),
    )
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs():
    return StubListOrders(), StubGetOrder()


def test_list_orders_returns_200(stubs):
    list_stub, get_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    list_stub.response = OrderListResponseSchema(
        items=[
            OrderListItemResponseSchema(
                id=uuid4(),
                buyer_id=uuid4(),
                status='PAID',
                total=10_000,
                items_count=1,
                created_at=datetime.now(UTC),
            )
        ],
        total_count=1,
        limit=20,
        offset=0,
    )
    client = TestClient(_make_app(list_stub, get_stub, user=user))

    response = client.get('/api/v1/orders')

    assert response.status_code == 200
    body = response.json()
    assert body['total_count'] == 1
    assert len(body['items']) == 1
    assert list_stub.calls[0]['user_id'] == user.id
    assert list_stub.calls[0]['status'] is None


def test_list_orders_with_status_filter(stubs):
    list_stub, get_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(list_stub, get_stub, user=user))

    client.get('/api/v1/orders?status=DELIVERED&limit=5&offset=10')

    assert list_stub.calls[0]['status'] == 'DELIVERED'
    assert list_stub.calls[0]['limit'] == 5
    assert list_stub.calls[0]['offset'] == 10


def test_list_orders_unauthorized_returns_401(stubs):
    list_stub, get_stub = stubs
    client = TestClient(_make_app(list_stub, get_stub, user=None))
    response = client.get('/api/v1/orders')
    assert response.status_code == 401


def test_list_orders_non_buyer_returns_403(stubs):
    list_stub, get_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(list_stub, get_stub, user=user))
    response = client.get('/api/v1/orders')
    assert response.status_code == 403


def test_get_order_returns_200(stubs):
    list_stub, get_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    order_id = uuid4()
    client = TestClient(_make_app(list_stub, get_stub, user=user))

    response = client.get(f'/api/v1/orders/{order_id}')

    assert response.status_code == 200
    assert get_stub.calls[0][0] == order_id
    assert get_stub.calls[0][1].id == user.id


def test_get_order_returns_404_for_other_user(stubs):
    list_stub, get_stub = stubs
    get_stub.error = OrderNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(list_stub, get_stub, user=user))

    response = client.get(f'/api/v1/orders/{uuid4()}')

    assert response.status_code == 404
    body = response.json()
    assert body['code'] == 'ORDER_NOT_FOUND'


def test_get_order_unauthorized_returns_401(stubs):
    list_stub, get_stub = stubs
    client = TestClient(_make_app(list_stub, get_stub, user=None))
    response = client.get(f'/api/v1/orders/{uuid4()}')
    assert response.status_code == 401


def test_get_order_invalid_uuid_returns_400(stubs):
    list_stub, get_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(list_stub, get_stub, user=user))
    response = client.get('/api/v1/orders/not-a-uuid')
    assert response.status_code == 400
