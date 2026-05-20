from dataclasses import dataclass
from uuid import uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.auth.dependencies import get_current_user
from apps.auth.routers import router as auth_router
from apps.auth.schemas.request import LoginRequestSchema, LogoutRequestSchema, RefreshRequestSchema
from apps.auth.schemas.response import AuthTokensResponseSchema, RefreshTokensResponseSchema
from apps.auth.use_cases import LoginUseCase, LogoutUseCase, RefreshUseCase
from apps.errors import setup_error_handlers
from shared.auth_lib import AuthenticatedUserSchema, UserRole


class StubLoginUseCase:
    def __init__(self):
        self.calls: list[LoginRequestSchema] = []
        self.response = AuthTokensResponseSchema(
            user_id=uuid4(),
            access_token='login-access-token',
            refresh_token='login-refresh-token',
            expires_in=3600,
            role=UserRole.MODERATOR,
        )

    async def __call__(self, data: LoginRequestSchema) -> AuthTokensResponseSchema:
        self.calls.append(data)
        return self.response


class StubRefreshUseCase:
    def __init__(self):
        self.calls: list[RefreshRequestSchema] = []
        self.response = RefreshTokensResponseSchema(
            user_id=uuid4(),
            access_token='new-access-token',
            refresh_token='new-refresh-token',
            expires_in=3600,
            role=UserRole.MODERATOR,
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
    login: StubLoginUseCase
    refresh: StubRefreshUseCase
    logout: StubLogoutUseCase


class AuthRouteProvider(Provider):
    def __init__(self, stubs: AuthRouteStubs):
        super().__init__()
        self.stubs = stubs

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


def test_login_returns_tokens(client: TestClient, stubs: AuthRouteStubs):
    response = client.post(
        '/api/v1/auth/login',
        json={'email': 'mod@example.com', 'password': 'SecurePass123!'},
    )

    assert response.status_code == 200
    assert response.json()['access_token'] == 'login-access-token'
    assert response.json()['role'] == 'moderator'
    assert stubs.login.calls[0].email == 'mod@example.com'


def test_login_validation_error_returns_400(client: TestClient):
    response = client.post('/api/v1/auth/login', json={})

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}


def test_refresh_returns_new_pair(client: TestClient, stubs: AuthRouteStubs):
    response = client.post('/api/v1/auth/refresh', json={'refresh_token': 'old-refresh-token'})

    assert response.status_code == 200
    body = response.json()
    assert body['access_token'] == 'new-access-token'
    assert body['refresh_token'] == 'new-refresh-token'
    assert body['token_type'] == 'Bearer'
    assert body['expires_in'] == 3600
    assert stubs.refresh.calls[0].refresh_token == 'old-refresh-token'


def test_logout_requires_current_user(client: TestClient):
    response = client.post('/api/v1/auth/logout', json={'refresh_token': 'refresh-token'})

    assert response.status_code == 401
    assert response.json() == {'code': 'UNAUTHORIZED', 'message': 'Нет заголовка Authorization'}


def test_logout_returns_204_for_authenticated_user(client: TestClient, stubs: AuthRouteStubs):
    user_id = uuid4()
    client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserSchema(
        id=user_id,
        role=UserRole.MODERATOR,
    )

    response = client.post('/api/v1/auth/logout', json={'refresh_token': 'refresh-token'})

    assert response.status_code == 204
    assert response.text == ''
    request_schema, current_user = stubs.logout.calls[0]
    assert request_schema.refresh_token == 'refresh-token'
    assert current_user.id == user_id
