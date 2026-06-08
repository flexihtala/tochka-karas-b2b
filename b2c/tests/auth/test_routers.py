from dataclasses import dataclass
from uuid import uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.auth.dependencies import get_current_user
from apps.auth.errors import EmailAlreadyExistsError, InvalidCredentialsError
from apps.auth.routers import router as auth_router
from apps.auth.schemas.request import (
    LoginRequestSchema,
    LogoutRequestSchema,
    RefreshRequestSchema,
    RegisterBuyerRequestSchema,
)
from apps.auth.schemas.response import AuthTokensResponseSchema, RefreshTokensResponseSchema
from apps.auth.use_cases import LoginUseCase, LogoutUseCase, RefreshUseCase, RegisterBuyerUseCase
from apps.errors import setup_error_handlers
from shared.auth_lib import AuthenticatedUserSchema, UserRole


class StubRegisterBuyerUseCase:
    def __init__(self):
        self.calls: list[RegisterBuyerRequestSchema] = []
        self.error: Exception | None = None
        self.response = AuthTokensResponseSchema(
            user_id=uuid4(),
            access_token='access-token',
            refresh_token='refresh-token',
            expires_in=3600,
        )

    async def __call__(self, data: RegisterBuyerRequestSchema) -> AuthTokensResponseSchema:
        self.calls.append(data)
        if self.error:
            raise self.error
        return self.response


class StubLoginUseCase:
    def __init__(self):
        self.calls: list[LoginRequestSchema] = []
        self.error: Exception | None = None
        self.response = AuthTokensResponseSchema(
            user_id=uuid4(),
            access_token='login-access-token',
            refresh_token='login-refresh-token',
            expires_in=3600,
        )

    async def __call__(self, data: LoginRequestSchema) -> AuthTokensResponseSchema:
        self.calls.append(data)
        if self.error:
            raise self.error
        return self.response


class StubRefreshUseCase:
    def __init__(self):
        self.calls: list[RefreshRequestSchema] = []
        self.response = RefreshTokensResponseSchema(
            access_token='new-access-token',
            refresh_token='new-refresh-token',
            expires_in=3600,
        )

    async def __call__(self, data: RefreshRequestSchema) -> RefreshTokensResponseSchema:
        self.calls.append(data)
        return self.response


class StubLogoutUseCase:
    def __init__(self):
        self.calls: list[tuple[LogoutRequestSchema, AuthenticatedUserSchema]] = []

    async def __call__(self, data: LogoutRequestSchema, current_user: AuthenticatedUserSchema) -> None:
        self.calls.append((data, current_user))


@dataclass
class AuthRouteStubs:
    register: StubRegisterBuyerUseCase
    login: StubLoginUseCase
    refresh: StubRefreshUseCase
    logout: StubLogoutUseCase


class AuthRouteProvider(Provider):
    def __init__(self, stubs: AuthRouteStubs):
        super().__init__()
        self.stubs = stubs

    @provide(scope=Scope.REQUEST)
    def get_register_use_case(self) -> RegisterBuyerUseCase:
        return self.stubs.register

    @provide(scope=Scope.REQUEST)
    def get_login_use_case(self) -> LoginUseCase:
        return self.stubs.login

    @provide(scope=Scope.REQUEST)
    def get_refresh_use_case(self) -> RefreshUseCase:
        return self.stubs.refresh

    @provide(scope=Scope.REQUEST)
    def get_logout_use_case(self) -> LogoutUseCase:
        return self.stubs.logout


@pytest.fixture
def stubs() -> AuthRouteStubs:
    return AuthRouteStubs(
        register=StubRegisterBuyerUseCase(),
        login=StubLoginUseCase(),
        refresh=StubRefreshUseCase(),
        logout=StubLogoutUseCase(),
    )


@pytest.fixture
def client(stubs: AuthRouteStubs) -> TestClient:
    app = FastAPI()
    app.include_router(auth_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), AuthRouteProvider(stubs))
    setup_dishka(container, app)
    return TestClient(app)


def register_payload(email: str = 'buyer@example.com') -> dict[str, str]:
    return {
        'email': email,
        'password': 'SecurePass123!',
        'first_name': 'Ivan',
        'last_name': 'Ivanov',
        'phone': '+79001234567',
    }


def test_register_returns_201_and_tokens(client: TestClient, stubs: AuthRouteStubs):
    response = client.post('/api/v1/auth/register', json=register_payload())

    assert response.status_code == 201
    assert response.json() == {
        'user_id': str(stubs.register.response.user_id),
        'access_token': 'access-token',
        'refresh_token': 'refresh-token',
        'token_type': 'Bearer',
        'expires_in': 3600,
    }
    assert stubs.register.calls[0].email == 'buyer@example.com'


def test_register_minimal_payload_accepted(client: TestClient, stubs: AuthRouteStubs):
    response = client.post(
        '/api/v1/auth/register',
        json={'email': 'buyer@example.com', 'password': 'SecurePass123!', 'first_name': 'Ivan'},
    )

    assert response.status_code == 201
    assert stubs.register.calls[0].last_name is None
    assert stubs.register.calls[0].phone is None


def test_register_maps_domain_error_to_409(client: TestClient, stubs: AuthRouteStubs):
    stubs.register.error = EmailAlreadyExistsError()

    response = client.post('/api/v1/auth/register', json=register_payload())

    assert response.status_code == 409
    assert response.json() == {'code': 'EMAIL_ALREADY_EXISTS', 'message': 'Email уже зарегистрирован'}


def test_register_validation_error_has_project_error_format(client: TestClient):
    response = client.post('/api/v1/auth/register', json={})

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}


def test_login_returns_tokens(client: TestClient, stubs: AuthRouteStubs):
    response = client.post(
        '/api/v1/auth/login',
        json={'email': 'buyer@example.com', 'password': 'SecurePass123!'},
    )

    assert response.status_code == 200
    assert response.json()['access_token'] == 'login-access-token'
    assert stubs.login.calls[0].email == 'buyer@example.com'


def test_login_maps_invalid_credentials_to_401(client: TestClient, stubs: AuthRouteStubs):
    stubs.login.error = InvalidCredentialsError()

    response = client.post(
        '/api/v1/auth/login',
        json={'email': 'buyer@example.com', 'password': 'WrongPass123!'},
    )

    assert response.status_code == 401
    assert response.json() == {'code': 'INVALID_CREDENTIALS', 'message': 'Неверный email или пароль'}


def test_refresh_returns_new_pair(client: TestClient, stubs: AuthRouteStubs):
    response = client.post('/api/v1/auth/refresh', json={'refresh_token': 'old-refresh-token'})

    assert response.status_code == 200
    assert response.json() == {
        'access_token': 'new-access-token',
        'refresh_token': 'new-refresh-token',
        'token_type': 'Bearer',
        'expires_in': 3600,
    }
    assert stubs.refresh.calls[0].refresh_token == 'old-refresh-token'


def test_logout_requires_current_user(client: TestClient):
    response = client.post('/api/v1/auth/logout', json={'refresh_token': 'refresh-token'})

    assert response.status_code == 401
    assert response.json() == {'code': 'UNAUTHORIZED', 'message': 'Нет заголовка Authorization'}


def test_logout_returns_204_for_authenticated_user(client: TestClient, stubs: AuthRouteStubs):
    user_id = uuid4()
    client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserSchema(
        id=user_id,
        role=UserRole.BUYER,
    )

    response = client.post('/api/v1/auth/logout', json={'refresh_token': 'refresh-token'})

    assert response.status_code == 204
    assert response.text == ''
    request_schema, current_user = stubs.logout.calls[0]
    assert request_schema.refresh_token == 'refresh-token'
    assert current_user.id == user_id
