"""Router-level тесты для /api/v1/inventory/{reserve,unreserve,fulfill}.

Используем stub use-case в DI-контейнере (как в tests/skus/test_routers.py).
"""

from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.errors import setup_error_handlers
from apps.inventory.errors import InventoryConflictError
from apps.inventory.routers import router as inventory_router
from apps.inventory.schemas import (
    FulfillRequestSchema,
    FulfillResponseSchema,
    ReserveItemResponseSchema,
    ReserveRequestSchema,
    ReserveResponseSchema,
    UnreserveRequestSchema,
    UnreserveResponseSchema,
)
from apps.inventory.use_cases import (
    FulfillInventoryUseCase,
    ReserveInventoryUseCase,
    UnreserveInventoryUseCase,
)
from settings import settings


class StubReserveUseCase:
    def __init__(self):
        self.calls: list[ReserveRequestSchema] = []
        self.error: Exception | None = None
        sku_id = uuid4()
        self.response = ReserveResponseSchema(
            reserved=True,
            items=[ReserveItemResponseSchema(sku_id=sku_id, reserved_quantity=2, remaining_stock=8)],
        )

    async def __call__(self, data: ReserveRequestSchema) -> ReserveResponseSchema:
        self.calls.append(data)
        if self.error:
            raise self.error
        return self.response


class StubUnreserveUseCase:
    def __init__(self):
        self.calls: list[UnreserveRequestSchema] = []
        self.response = UnreserveResponseSchema(ok=True)

    async def __call__(self, data: UnreserveRequestSchema) -> UnreserveResponseSchema:
        self.calls.append(data)
        return self.response


class StubFulfillUseCase:
    def __init__(self):
        from datetime import UTC, datetime

        self.calls: list[FulfillRequestSchema] = []
        self.response = FulfillResponseSchema(
            order_id=uuid4(),
            status='FULFILLED',
            processed_at=datetime.now(UTC),
        )

    async def __call__(self, data: FulfillRequestSchema) -> FulfillResponseSchema:
        self.calls.append(data)
        return self.response


class InventoryRouteProvider(Provider):
    def __init__(
        self,
        reserve_stub: StubReserveUseCase,
        unreserve_stub: StubUnreserveUseCase,
        fulfill_stub: StubFulfillUseCase,
    ):
        super().__init__()
        self.reserve_stub = reserve_stub
        self.unreserve_stub = unreserve_stub
        self.fulfill_stub = fulfill_stub

    @provide(scope=Scope.REQUEST)
    def get_reserve_use_case(self) -> ReserveInventoryUseCase:
        return self.reserve_stub  # type: ignore[return-value]

    @provide(scope=Scope.REQUEST)
    def get_unreserve_use_case(self) -> UnreserveInventoryUseCase:
        return self.unreserve_stub  # type: ignore[return-value]

    @provide(scope=Scope.REQUEST)
    def get_fulfill_use_case(self) -> FulfillInventoryUseCase:
        return self.fulfill_stub  # type: ignore[return-value]


def _make_app(
    reserve_stub: StubReserveUseCase,
    unreserve_stub: StubUnreserveUseCase,
    fulfill_stub: StubFulfillUseCase,
) -> FastAPI:
    app = FastAPI()
    app.include_router(inventory_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        InventoryRouteProvider(reserve_stub, unreserve_stub, fulfill_stub),
    )
    setup_dishka(container, app)
    return app


def _reserve_payload(sku_id: UUID | None = None, idempotency_key: UUID | None = None) -> dict:
    return {
        'idempotency_key': str(idempotency_key or uuid4()),
        'items': [
            {'sku_id': str(sku_id or uuid4()), 'quantity': 2},
        ],
    }


def _unreserve_payload(sku_id: UUID | None = None, idempotency_key: UUID | None = None) -> dict:
    return {
        'idempotency_key': str(idempotency_key or uuid4()),
        'items': [
            {'sku_id': str(sku_id or uuid4()), 'quantity': 2},
        ],
    }


def _fulfill_payload(sku_id: UUID | None = None, order_id: UUID | None = None) -> dict:
    return {
        'order_id': str(order_id or uuid4()),
        'items': [
            {'sku_id': str(sku_id or uuid4()), 'quantity': 2},
        ],
    }


@pytest.fixture
def stubs() -> tuple[StubReserveUseCase, StubUnreserveUseCase, StubFulfillUseCase]:
    return StubReserveUseCase(), StubUnreserveUseCase(), StubFulfillUseCase()


@pytest.fixture
def client(stubs: tuple[StubReserveUseCase, StubUnreserveUseCase, StubFulfillUseCase]) -> TestClient:
    reserve, unreserve, fulfill = stubs
    return TestClient(_make_app(reserve, unreserve, fulfill))


@pytest.fixture
def service_key_headers() -> dict:
    return {'X-Service-Key': settings.b2c_to_b2b_key}


# ─────── /inventory/reserve ───────


def test_reserve_returns_200(client: TestClient, stubs, service_key_headers):
    reserve_stub, _, _ = stubs
    payload = _reserve_payload()
    response = client.post('/api/v1/inventory/reserve', json=payload, headers=service_key_headers)

    assert response.status_code == 200
    body = response.json()
    assert body['reserved'] is True
    assert len(body['items']) == 1
    assert len(reserve_stub.calls) == 1


def test_reserve_without_service_key_returns_401(client: TestClient, stubs):
    reserve_stub, _, _ = stubs
    response = client.post('/api/v1/inventory/reserve', json=_reserve_payload())

    assert response.status_code == 401
    assert response.json()['code'] == 'INVALID_SERVICE_KEY'
    assert reserve_stub.calls == []


def test_reserve_with_wrong_service_key_returns_401(client: TestClient, stubs):
    reserve_stub, _, _ = stubs
    response = client.post(
        '/api/v1/inventory/reserve',
        json=_reserve_payload(),
        headers={'X-Service-Key': 'wrong-key'},
    )

    assert response.status_code == 401
    assert response.json()['code'] == 'INVALID_SERVICE_KEY'
    assert reserve_stub.calls == []


def test_reserve_validation_error_returns_400(client: TestClient, service_key_headers):
    response = client.post('/api/v1/inventory/reserve', json={}, headers=service_key_headers)

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}


def test_reserve_empty_items_returns_400(client: TestClient, service_key_headers):
    payload = _reserve_payload()
    payload['items'] = []  # min_length=1 нарушен
    response = client.post('/api/v1/inventory/reserve', json=payload, headers=service_key_headers)

    assert response.status_code == 400


def test_reserve_zero_quantity_returns_400(client: TestClient, service_key_headers):
    payload = _reserve_payload()
    payload['items'][0]['quantity'] = 0  # ge=1 нарушен
    response = client.post('/api/v1/inventory/reserve', json=payload, headers=service_key_headers)

    assert response.status_code == 400


def test_reserve_conflict_returns_409_with_failed_items(
    client: TestClient,
    stubs,
    service_key_headers,
):
    reserve_stub, _, _ = stubs
    failed_items = [
        {
            'sku_id': str(uuid4()),
            'requested': 5,
            'available': 3,
            'reason': 'INSUFFICIENT_STOCK',
        }
    ]
    reserve_stub.error = InventoryConflictError(failed_items=failed_items)

    response = client.post(
        '/api/v1/inventory/reserve',
        json=_reserve_payload(),
        headers=service_key_headers,
    )

    assert response.status_code == 409
    body = response.json()
    assert body['code'] == 'RESERVE_FAILED'
    assert body['details']['failed_items'] == failed_items


# ─────── /inventory/unreserve ───────


def test_unreserve_returns_200(client: TestClient, stubs, service_key_headers):
    _, unreserve_stub, _ = stubs
    response = client.post(
        '/api/v1/inventory/unreserve',
        json=_unreserve_payload(),
        headers=service_key_headers,
    )

    assert response.status_code == 200
    assert response.json() == {'ok': True}
    assert len(unreserve_stub.calls) == 1


def test_unreserve_without_service_key_returns_401(client: TestClient, stubs):
    _, unreserve_stub, _ = stubs
    response = client.post('/api/v1/inventory/unreserve', json=_unreserve_payload())

    assert response.status_code == 401
    assert response.json()['code'] == 'INVALID_SERVICE_KEY'
    assert unreserve_stub.calls == []


def test_unreserve_validation_error_returns_400(client: TestClient, service_key_headers):
    response = client.post('/api/v1/inventory/unreserve', json={}, headers=service_key_headers)

    assert response.status_code == 400


# ─────── /inventory/fulfill ───────


def test_fulfill_returns_200(client: TestClient, stubs, service_key_headers):
    _, _, fulfill_stub = stubs
    response = client.post(
        '/api/v1/inventory/fulfill',
        json=_fulfill_payload(),
        headers=service_key_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'FULFILLED'
    assert 'order_id' in body
    assert 'processed_at' in body
    assert len(fulfill_stub.calls) == 1


def test_fulfill_without_service_key_returns_401(client: TestClient, stubs):
    _, _, fulfill_stub = stubs
    response = client.post('/api/v1/inventory/fulfill', json=_fulfill_payload())

    assert response.status_code == 401
    assert response.json()['code'] == 'INVALID_SERVICE_KEY'
    assert fulfill_stub.calls == []


def test_fulfill_with_wrong_service_key_returns_401(client: TestClient, stubs):
    _, _, fulfill_stub = stubs
    response = client.post(
        '/api/v1/inventory/fulfill',
        json=_fulfill_payload(),
        headers={'X-Service-Key': 'wrong-key'},
    )

    assert response.status_code == 401
    assert response.json()['code'] == 'INVALID_SERVICE_KEY'
    assert fulfill_stub.calls == []


def test_fulfill_validation_error_returns_400(client: TestClient, service_key_headers):
    response = client.post('/api/v1/inventory/fulfill', json={}, headers=service_key_headers)

    assert response.status_code == 400


def test_fulfill_empty_items_returns_400(client: TestClient, service_key_headers):
    payload = _fulfill_payload()
    payload['items'] = []  # min_length=1 нарушен
    response = client.post('/api/v1/inventory/fulfill', json=payload, headers=service_key_headers)

    assert response.status_code == 400


def test_fulfill_zero_quantity_returns_400(client: TestClient, service_key_headers):
    payload = _fulfill_payload()
    payload['items'][0]['quantity'] = 0  # ge=1 нарушен
    response = client.post('/api/v1/inventory/fulfill', json=payload, headers=service_key_headers)

    assert response.status_code == 400


def test_fulfill_invalid_order_id_returns_400(client: TestClient, service_key_headers):
    payload = _fulfill_payload()
    payload['order_id'] = 'not-a-uuid'
    response = client.post('/api/v1/inventory/fulfill', json=payload, headers=service_key_headers)

    assert response.status_code == 400
