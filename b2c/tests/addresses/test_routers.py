from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.addresses.errors import AddressNotFoundError
from apps.addresses.routers import router as addresses_router
from apps.addresses.schemas.request import AddressCreateRequestSchema, AddressUpdateRequestSchema
from apps.addresses.schemas.response import AddressResponseSchema
from apps.addresses.use_cases import (
    CreateAddressUseCase,
    DeleteAddressUseCase,
    ListAddressesUseCase,
    UpdateAddressUseCase,
)
from apps.errors import setup_error_handlers
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _make_response(buyer_id: UUID, address_id: UUID | None = None) -> AddressResponseSchema:
    now = datetime.now(UTC)
    return AddressResponseSchema(
        id=address_id or uuid4(),
        buyer_id=buyer_id,
        country='Russia',
        city='Moscow',
        street='Lenin str. 1',
        postal_code='101000',
        comment=None,
        is_default=False,
        created_at=now,
        updated_at=now,
    )


class StubListAddresses:
    def __init__(self):
        self.calls: list[AuthenticatedUserSchema] = []
        self.response: list[AddressResponseSchema] = []

    async def __call__(self, current_user: AuthenticatedUserSchema) -> list[AddressResponseSchema]:
        self.calls.append(current_user)
        return self.response


class StubCreateAddress:
    def __init__(self):
        self.calls: list[tuple[AddressCreateRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.response: AddressResponseSchema | None = None

    async def __call__(
        self,
        data: AddressCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> AddressResponseSchema:
        self.calls.append((data, current_user))
        if self.error:
            raise self.error
        return self.response or _make_response(current_user.id)


class StubUpdateAddress:
    def __init__(self):
        self.calls: list[tuple[UUID, AddressUpdateRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.response: AddressResponseSchema | None = None

    async def __call__(
        self,
        address_id: UUID,
        data: AddressUpdateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> AddressResponseSchema:
        self.calls.append((address_id, data, current_user))
        if self.error:
            raise self.error
        return self.response or _make_response(current_user.id, address_id)


class StubDeleteAddress:
    def __init__(self):
        self.calls: list[tuple[UUID, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None

    async def __call__(self, address_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        self.calls.append((address_id, current_user))
        if self.error:
            raise self.error


class AddressesRouteProvider(Provider):
    def __init__(
        self,
        list_stub: StubListAddresses,
        create_stub: StubCreateAddress,
        update_stub: StubUpdateAddress,
        delete_stub: StubDeleteAddress,
    ):
        super().__init__()
        self.list_stub = list_stub
        self.create_stub = create_stub
        self.update_stub = update_stub
        self.delete_stub = delete_stub

    @provide(scope=Scope.REQUEST)
    def get_list_use_case(self) -> ListAddressesUseCase:
        return self.list_stub

    @provide(scope=Scope.REQUEST)
    def get_create_use_case(self) -> CreateAddressUseCase:
        return self.create_stub

    @provide(scope=Scope.REQUEST)
    def get_update_use_case(self) -> UpdateAddressUseCase:
        return self.update_stub

    @provide(scope=Scope.REQUEST)
    def get_delete_use_case(self) -> DeleteAddressUseCase:
        return self.delete_stub


def _make_app(
    list_stub: StubListAddresses,
    create_stub: StubCreateAddress,
    update_stub: StubUpdateAddress,
    delete_stub: StubDeleteAddress,
    user: AuthenticatedUserSchema | None,
) -> FastAPI:
    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(addresses_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        AddressesRouteProvider(list_stub, create_stub, update_stub, delete_stub),
    )
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs():
    return StubListAddresses(), StubCreateAddress(), StubUpdateAddress(), StubDeleteAddress()


def _create_payload(is_default: bool = False) -> dict:
    return {
        'country': 'Russia',
        'city': 'Moscow',
        'street': 'Lenin str. 1',
        'postal_code': '101000',
        'is_default': is_default,
    }


def test_list_addresses_returns_user_addresses(stubs):
    list_stub, create_stub, update_stub, delete_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    list_stub.response = [_make_response(user.id)]
    client = TestClient(_make_app(*stubs, user=user))

    response = client.get('/api/v1/buyers/me/addresses')

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]['buyer_id'] == str(user.id)
    assert list_stub.calls[0].id == user.id


def test_list_addresses_unauthorized_returns_401(stubs):
    client = TestClient(_make_app(*stubs, user=None))

    response = client.get('/api/v1/buyers/me/addresses')

    assert response.status_code == 401


def test_create_address_returns_201(stubs):
    list_stub, create_stub, update_stub, delete_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.post('/api/v1/buyers/me/addresses', json=_create_payload())

    assert response.status_code == 201
    body = response.json()
    assert body['country'] == 'Russia'
    assert body['city'] == 'Moscow'
    data, current_user = create_stub.calls[0]
    assert data.city == 'Moscow'
    assert current_user.id == user.id


def test_create_address_validation_error_returns_400(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.post('/api/v1/buyers/me/addresses', json={'country': 'Russia'})

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}


def test_create_address_non_buyer_returns_403(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.post('/api/v1/buyers/me/addresses', json=_create_payload())

    assert response.status_code == 403


def test_update_address_returns_200(stubs):
    list_stub, create_stub, update_stub, delete_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    address_id = uuid4()
    client = TestClient(_make_app(*stubs, user=user))

    response = client.patch(f'/api/v1/buyers/me/addresses/{address_id}', json={'city': 'Saint Petersburg'})

    assert response.status_code == 200
    assert update_stub.calls[0][0] == address_id
    assert update_stub.calls[0][1].city == 'Saint Petersburg'


def test_update_address_returns_404_when_not_owned(stubs):
    list_stub, create_stub, update_stub, delete_stub = stubs
    update_stub.error = AddressNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.patch(f'/api/v1/buyers/me/addresses/{uuid4()}', json={'city': 'Other'})

    assert response.status_code == 404
    assert response.json() == {'code': 'NOT_FOUND', 'message': 'Адрес не найден'}


def test_delete_address_returns_204(stubs):
    list_stub, create_stub, update_stub, delete_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    address_id = uuid4()
    client = TestClient(_make_app(*stubs, user=user))

    response = client.delete(f'/api/v1/buyers/me/addresses/{address_id}')

    assert response.status_code == 204
    assert response.text == ''
    assert delete_stub.calls[0][0] == address_id


def test_delete_address_returns_404_when_not_owned(stubs):
    list_stub, create_stub, update_stub, delete_stub = stubs
    delete_stub.error = AddressNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.delete(f'/api/v1/buyers/me/addresses/{uuid4()}')

    assert response.status_code == 404
