from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.blocking_reasons.routers import router as blocking_reasons_router
from apps.blocking_reasons.schemas.request import (
    BlockingReasonCreateRequestSchema,
    BlockingReasonUpdateRequestSchema,
)
from apps.blocking_reasons.schemas.response import BlockingReasonResponseSchema
from apps.blocking_reasons.use_cases import (
    CreateBlockingReasonUseCase,
    DeleteBlockingReasonUseCase,
    ListBlockingReasonsUseCase,
    UpdateBlockingReasonUseCase,
)
from apps.errors import setup_error_handlers
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _make_response(
    code: str = 'TEST_CODE',
    title: str = 'Test',
    hard_block: bool = False,
) -> BlockingReasonResponseSchema:
    return BlockingReasonResponseSchema(
        id=uuid4(),
        code=code,
        title=title,
        description='desc',
        hard_block=hard_block,
        is_active=True,
    )


class StubListUseCase:
    def __init__(self):
        self.calls: list[tuple[bool | None, bool | None]] = []
        self.response: list[BlockingReasonResponseSchema] = [_make_response(code='A_REASON')]

    async def __call__(self, *, hard_block: bool | None = None, is_active: bool | None = None):
        self.calls.append((hard_block, is_active))
        return self.response


class StubCreateUseCase:
    def __init__(self):
        self.calls: list[BlockingReasonCreateRequestSchema] = []
        self.error: Exception | None = None
        self.response = _make_response()

    async def __call__(self, data: BlockingReasonCreateRequestSchema):
        self.calls.append(data)
        if self.error:
            raise self.error
        return self.response


class StubUpdateUseCase:
    def __init__(self):
        self.calls: list[tuple[UUID, BlockingReasonUpdateRequestSchema]] = []
        self.error: Exception | None = None
        self.response = _make_response()

    async def __call__(self, reason_id: UUID, data: BlockingReasonUpdateRequestSchema):
        self.calls.append((reason_id, data))
        if self.error:
            raise self.error
        return self.response


class StubDeleteUseCase:
    def __init__(self):
        self.calls: list[UUID] = []
        self.error: Exception | None = None

    async def __call__(self, reason_id: UUID) -> None:
        self.calls.append(reason_id)
        if self.error:
            raise self.error


@dataclass
class BlockingReasonsStubs:
    list_: StubListUseCase
    create: StubCreateUseCase
    update: StubUpdateUseCase
    delete: StubDeleteUseCase


class BlockingReasonsRouteProvider(Provider):
    def __init__(self, stubs: BlockingReasonsStubs):
        super().__init__()
        self.stubs = stubs

    @provide(scope=Scope.REQUEST)
    def list_use_case(self) -> ListBlockingReasonsUseCase:
        return self.stubs.list_

    @provide(scope=Scope.REQUEST)
    def create_use_case(self) -> CreateBlockingReasonUseCase:
        return self.stubs.create

    @provide(scope=Scope.REQUEST)
    def update_use_case(self) -> UpdateBlockingReasonUseCase:
        return self.stubs.update

    @provide(scope=Scope.REQUEST)
    def delete_use_case(self) -> DeleteBlockingReasonUseCase:
        return self.stubs.delete


def _make_app(stubs: BlockingReasonsStubs, user: AuthenticatedUserSchema | None) -> FastAPI:
    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(blocking_reasons_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), BlockingReasonsRouteProvider(stubs))
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs() -> BlockingReasonsStubs:
    return BlockingReasonsStubs(
        list_=StubListUseCase(),
        create=StubCreateUseCase(),
        update=StubUpdateUseCase(),
        delete=StubDeleteUseCase(),
    )


def test_list_blocking_reasons_for_authenticated_returns_200(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.MODERATOR)
    client = TestClient(_make_app(stubs, user))

    response = client.get('/api/v1/blocking-reasons?hard_block=true&is_active=true')

    assert response.status_code == 200
    # По спеке — массив прямо в response (не {items: [...]}).
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert stubs.list_.calls == [(True, True)]


def test_list_blocking_reasons_anonymous_returns_401(stubs):
    client = TestClient(_make_app(stubs, user=None))

    response = client.get('/api/v1/blocking-reasons')

    assert response.status_code == 401


def test_create_blocking_reason_requires_admin(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.MODERATOR)
    client = TestClient(_make_app(stubs, user))

    response = client.post(
        '/api/v1/blocking-reasons',
        json={'code': 'X_REASON', 'title': 'X', 'hard_block': False},
    )

    assert response.status_code == 403
    assert stubs.create.calls == []


def test_create_blocking_reason_returns_201_for_admin(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.ADMIN)
    client = TestClient(_make_app(stubs, user))

    response = client.post(
        '/api/v1/blocking-reasons',
        json={
            'code': 'FORBIDDEN_GOODS',
            'title': 'Запрещённые товары',
            'description': 'desc',
            'hard_block': True,
        },
    )

    assert response.status_code == 201
    assert stubs.create.calls[0].code == 'FORBIDDEN_GOODS'
    assert stubs.create.calls[0].title == 'Запрещённые товары'
    assert stubs.create.calls[0].hard_block is True


def test_update_blocking_reason_requires_admin(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.MODERATOR)
    client = TestClient(_make_app(stubs, user))

    response = client.patch(
        f'/api/v1/blocking-reasons/{uuid4()}',
        json={'description': 'new'},
    )

    assert response.status_code == 403


def test_update_blocking_reason_returns_200_for_admin(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.ADMIN)
    client = TestClient(_make_app(stubs, user))
    target_id = uuid4()

    response = client.patch(
        f'/api/v1/blocking-reasons/{target_id}',
        json={'description': 'updated'},
    )

    assert response.status_code == 200
    reason_id, payload = stubs.update.calls[0]
    assert reason_id == target_id
    assert payload.description == 'updated'


def test_delete_blocking_reason_requires_admin(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.MODERATOR)
    client = TestClient(_make_app(stubs, user))

    response = client.delete(f'/api/v1/blocking-reasons/{uuid4()}')

    assert response.status_code == 403


def test_delete_blocking_reason_returns_204_for_admin(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.ADMIN)
    client = TestClient(_make_app(stubs, user))
    target_id = uuid4()

    response = client.delete(f'/api/v1/blocking-reasons/{target_id}')

    assert response.status_code == 204
    assert stubs.delete.calls == [target_id]


# Suppress unused fixture warning
_ = datetime, UTC
