from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.errors import setup_error_handlers
from apps.moderators.errors import EmailAlreadyExistsError, ModeratorNotFoundError
from apps.moderators.routers import router as moderators_router
from apps.moderators.schemas.request import ModeratorCreateRequestSchema, ModeratorUpdateRequestSchema
from apps.moderators.schemas.response import ModeratorListResponseSchema, ModeratorResponseSchema
from apps.moderators.use_cases import (
    CreateModeratorUseCase,
    GetModeratorUseCase,
    ListModeratorsUseCase,
    UpdateModeratorUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _make_response(role: UserRole = UserRole.MODERATOR, email: str = 'mod@example.com') -> ModeratorResponseSchema:
    return ModeratorResponseSchema(
        id=uuid4(),
        email=email,
        first_name='Ivan',
        last_name='Ivanov',
        role=role,
        is_active=True,
        created_at=datetime.now(UTC),
    )


class StubCreateModeratorUseCase:
    def __init__(self):
        self.calls: list[ModeratorCreateRequestSchema] = []
        self.error: Exception | None = None
        self.response = _make_response()

    async def __call__(self, data: ModeratorCreateRequestSchema) -> ModeratorResponseSchema:
        self.calls.append(data)
        if self.error:
            raise self.error
        return self.response


class StubGetModeratorUseCase:
    def __init__(self):
        self.calls: list[UUID] = []
        self.error: Exception | None = None
        self.response = _make_response()

    async def __call__(self, moderator_id: UUID) -> ModeratorResponseSchema:
        self.calls.append(moderator_id)
        if self.error:
            raise self.error
        return self.response


class StubListModeratorsUseCase:
    def __init__(self):
        self.calls: list[tuple[int, int, bool | None]] = []
        self.response = ModeratorListResponseSchema(
            items=[_make_response(email='a@example.com'), _make_response(email='b@example.com')],
            total_count=2,
            limit=20,
            offset=0,
        )

    async def __call__(
        self,
        *,
        limit: int,
        offset: int,
        is_active: bool | None = None,
    ) -> ModeratorListResponseSchema:
        self.calls.append((limit, offset, is_active))
        return self.response


class StubUpdateModeratorUseCase:
    def __init__(self):
        self.calls: list[tuple[UUID, ModeratorUpdateRequestSchema]] = []
        self.error: Exception | None = None
        self.response = _make_response()

    async def __call__(self, moderator_id: UUID, data: ModeratorUpdateRequestSchema) -> ModeratorResponseSchema:
        self.calls.append((moderator_id, data))
        if self.error:
            raise self.error
        return self.response


class ModeratorsRouteProvider(Provider):
    def __init__(
        self,
        create_stub: StubCreateModeratorUseCase,
        get_stub: StubGetModeratorUseCase,
        list_stub: StubListModeratorsUseCase,
        update_stub: StubUpdateModeratorUseCase,
    ):
        super().__init__()
        self.create_stub = create_stub
        self.get_stub = get_stub
        self.list_stub = list_stub
        self.update_stub = update_stub

    @provide(scope=Scope.REQUEST)
    def get_create_use_case(self) -> CreateModeratorUseCase:
        return self.create_stub

    @provide(scope=Scope.REQUEST)
    def get_get_use_case(self) -> GetModeratorUseCase:
        return self.get_stub

    @provide(scope=Scope.REQUEST)
    def get_list_use_case(self) -> ListModeratorsUseCase:
        return self.list_stub

    @provide(scope=Scope.REQUEST)
    def get_update_use_case(self) -> UpdateModeratorUseCase:
        return self.update_stub


def _make_app(
    create_stub: StubCreateModeratorUseCase,
    get_stub: StubGetModeratorUseCase,
    list_stub: StubListModeratorsUseCase,
    update_stub: StubUpdateModeratorUseCase,
    user: AuthenticatedUserSchema | None,
) -> FastAPI:
    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(moderators_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        ModeratorsRouteProvider(create_stub, get_stub, list_stub, update_stub),
    )
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs() -> tuple[
    StubCreateModeratorUseCase,
    StubGetModeratorUseCase,
    StubListModeratorsUseCase,
    StubUpdateModeratorUseCase,
]:
    return (
        StubCreateModeratorUseCase(),
        StubGetModeratorUseCase(),
        StubListModeratorsUseCase(),
        StubUpdateModeratorUseCase(),
    )


def _create_payload() -> dict:
    return {
        'email': 'mod@example.com',
        'password': 'SecurePass123!',
        'first_name': 'Ivan',
        'last_name': 'Ivanov',
        'role': UserRole.MODERATOR.value,
    }


def test_list_moderators_requires_admin(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.MODERATOR)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    response = client.get('/api/v1/moderators')

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'
    assert list_stub.calls == []


def test_list_moderators_for_admin_returns_200(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.ADMIN)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    response = client.get('/api/v1/moderators?limit=10&offset=0&is_active=true')

    assert response.status_code == 200
    body = response.json()
    assert body['total_count'] == 2
    assert len(body['items']) == 2
    assert list_stub.calls == [(10, 0, True)]


def test_list_moderators_anonymous_returns_401(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user=None))

    response = client.get('/api/v1/moderators')

    assert response.status_code == 401
    assert response.json()['code'] == 'UNAUTHORIZED'


def test_get_me_returns_profile(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.MODERATOR)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    response = client.get('/api/v1/moderators/me')

    assert response.status_code == 200
    assert response.json()['email'] == 'mod@example.com'
    # GetUseCase должен вызваться с id из JWT.
    assert get_stub.calls == [user.id]


def test_get_me_requires_authentication(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user=None))

    response = client.get('/api/v1/moderators/me')

    assert response.status_code == 401


def test_get_moderator_by_id_admin_only(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.MODERATOR)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    response = client.get(f'/api/v1/moderators/{uuid4()}')

    assert response.status_code == 403
    assert response.json()['code'] == 'FORBIDDEN'


def test_get_moderator_by_id_returns_200(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.ADMIN)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    target_id = uuid4()
    response = client.get(f'/api/v1/moderators/{target_id}')

    assert response.status_code == 200
    assert get_stub.calls == [target_id]


def test_get_moderator_by_id_returns_404(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    get_stub.error = ModeratorNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.ADMIN)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    response = client.get(f'/api/v1/moderators/{uuid4()}')

    assert response.status_code == 404
    assert response.json() == {'code': 'MODERATOR_NOT_FOUND', 'message': 'Модератор не найден'}


def test_create_moderator_requires_admin(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.MODERATOR)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    response = client.post('/api/v1/moderators', json=_create_payload())

    assert response.status_code == 403
    assert create_stub.calls == []


def test_create_moderator_anonymous_returns_401(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user=None))

    response = client.post('/api/v1/moderators', json=_create_payload())

    assert response.status_code == 401


def test_create_moderator_returns_201(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.ADMIN)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    response = client.post('/api/v1/moderators', json=_create_payload())

    assert response.status_code == 201
    body = response.json()
    assert body['email'] == 'mod@example.com'
    assert 'password_hash' not in body
    assert create_stub.calls[0].email == 'mod@example.com'


def test_create_moderator_email_conflict_returns_409(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    create_stub.error = EmailAlreadyExistsError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.ADMIN)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    response = client.post('/api/v1/moderators', json=_create_payload())

    assert response.status_code == 409
    assert response.json() == {'code': 'EMAIL_ALREADY_EXISTS', 'message': 'Email уже зарегистрирован'}


def test_create_moderator_validation_error_returns_400(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.ADMIN)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    response = client.post('/api/v1/moderators', json={})

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}


def test_update_moderator_requires_admin(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.MODERATOR)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    response = client.patch(f'/api/v1/moderators/{uuid4()}', json={'first_name': 'X'})

    assert response.status_code == 403


def test_update_moderator_returns_200_for_admin(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.ADMIN)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    target_id = uuid4()
    response = client.patch(f'/api/v1/moderators/{target_id}', json={'first_name': 'Алексей'})

    assert response.status_code == 200
    moderator_id, payload = update_stub.calls[0]
    assert moderator_id == target_id
    assert payload.first_name == 'Алексей'


def test_update_moderator_404_when_missing(stubs):
    create_stub, get_stub, list_stub, update_stub = stubs
    update_stub.error = ModeratorNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.ADMIN)
    client = TestClient(_make_app(create_stub, get_stub, list_stub, update_stub, user))

    response = client.patch(f'/api/v1/moderators/{uuid4()}', json={'first_name': 'X'})

    assert response.status_code == 404
