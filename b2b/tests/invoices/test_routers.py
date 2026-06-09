from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.errors import setup_error_handlers
from apps.invoices.enums import InvoiceStatus
from apps.invoices.errors import (
    InvoiceEmptyItemsError,
    InvoiceNotOwnerError,
    InvoiceSKUNotFoundError,
    InvoiceSKUNotModeratedError,
)
from apps.invoices.routers import router as invoices_router
from apps.invoices.schemas.request import InvoiceCreateRequestSchema
from apps.invoices.schemas.response import (
    InvoiceItemResponseSchema,
    InvoiceResponseSchema,
)
from apps.invoices.use_cases import CreateInvoiceUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole


class StubCreateInvoiceUseCase:
    def __init__(self):
        self.calls: list[tuple[InvoiceCreateRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        now = datetime.now(UTC)
        invoice_id = uuid4()
        self.response = InvoiceResponseSchema(
            id=invoice_id,
            seller_id=uuid4(),
            status=InvoiceStatus.CREATED,
            items=[
                InvoiceItemResponseSchema(
                    id=uuid4(),
                    sku_id=uuid4(),
                    quantity=10,
                    accepted_quantity=0,
                ),
            ],
            created_at=now,
            updated_at=now,
        )

    async def __call__(
        self,
        data: InvoiceCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> InvoiceResponseSchema:
        self.calls.append((data, current_user))
        if self.error:
            raise self.error
        return self.response


class InvoicesRouteProvider(Provider):
    def __init__(self, stub: StubCreateInvoiceUseCase):
        super().__init__()
        self.stub = stub

    @provide(scope=Scope.REQUEST)
    def get_create_invoice_use_case(self) -> CreateInvoiceUseCase:
        return self.stub


def _make_app(stub: StubCreateInvoiceUseCase, user: AuthenticatedUserSchema | None) -> FastAPI:
    from starlette.middleware.base import BaseHTTPMiddleware

    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(invoices_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), InvoicesRouteProvider(stub))
    setup_dishka(container, app)
    return app


def _request_payload(sku_id: UUID | None = None) -> dict:
    return {
        'items': [
            {'sku_id': str(sku_id or uuid4()), 'quantity': 10},
        ],
    }


@pytest.fixture
def stub() -> StubCreateInvoiceUseCase:
    return StubCreateInvoiceUseCase()


def test_create_invoice_endpoint_returns_201(stub: StubCreateInvoiceUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/invoices', json=_request_payload())

    assert response.status_code == 201
    body = response.json()
    assert body['status'] == InvoiceStatus.CREATED.value
    assert len(body['items']) == 1
    assert body['items'][0]['quantity'] == 10
    assert body['items'][0]['accepted_quantity'] == 0
    assert len(stub.calls) == 1
    request_data, current_user = stub.calls[0]
    assert len(request_data.items) == 1
    assert current_user.id == user.id


def test_create_invoice_unauthorized_returns_401(stub: StubCreateInvoiceUseCase):
    client = TestClient(_make_app(stub, user=None))

    response = client.post('/api/v1/invoices', json=_request_payload())

    assert response.status_code == 401
    assert response.json() == {'code': 'UNAUTHORIZED', 'message': 'Unauthorized'}
    assert stub.calls == []


def test_create_invoice_non_seller_returns_403(stub: StubCreateInvoiceUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/invoices', json=_request_payload())

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'
    assert stub.calls == []


def test_create_invoice_validation_error_returns_400(stub: StubCreateInvoiceUseCase):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    # Невалидное тело: items отсутствует — InvoiceCreateRequestSchema требует List, но
    # с дефолтом — пустой список пройдёт сериализацию, поэтому проверяем явно невалидный JSON.
    response = client.post('/api/v1/invoices', json={'items': 'not-a-list'})

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}
    assert stub.calls == []


def test_create_invoice_empty_items_returns_400(stub: StubCreateInvoiceUseCase):
    stub.error = InvoiceEmptyItemsError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/invoices', json={'items': []})

    assert response.status_code == 400
    body = response.json()
    assert body['code'] == 'INVALID_REQUEST'
    assert body['message'] == 'At least one item is required'


def test_create_invoice_not_owner_returns_403(stub: StubCreateInvoiceUseCase):
    stub.error = InvoiceNotOwnerError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/invoices', json=_request_payload())

    assert response.status_code == 403
    body = response.json()
    assert body['code'] == 'NOT_OWNER'


def test_create_invoice_non_moderated_sku_returns_400(stub: StubCreateInvoiceUseCase):
    stub.error = InvoiceSKUNotModeratedError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/invoices', json=_request_payload())

    assert response.status_code == 400
    body = response.json()
    assert body['code'] == 'INVALID_REQUEST'
    assert 'MODERATED' in body['message']


def test_create_invoice_unknown_sku_returns_400(stub: StubCreateInvoiceUseCase):
    stub.error = InvoiceSKUNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    response = client.post('/api/v1/invoices', json=_request_payload())

    assert response.status_code == 400
    body = response.json()
    assert body['code'] == 'INVALID_REQUEST'


def test_create_invoice_quantity_zero_validation_error(stub: StubCreateInvoiceUseCase):
    """quantity < 1 на уровне pydantic-схемы → 400."""
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(stub, user))

    payload = {'items': [{'sku_id': str(uuid4()), 'quantity': 0}]}
    response = client.post('/api/v1/invoices', json=payload)

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}
    assert stub.calls == []
