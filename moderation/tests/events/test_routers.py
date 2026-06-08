"""Integration-тесты POST /api/v1/b2b/events.

Идёмпотентность тестируется без живого Postgres: мы подменяем
IdempotentHandler стабом, который запоминает (sender, key) → cached.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.errors import setup_error_handlers
from apps.events.errors import TicketNotFoundForEditError
from apps.events.routers import router as events_router
from apps.events.schemas.request import IncomingB2BEventSchema
from apps.events.schemas.response import EventAcceptedResponseSchema
from apps.events.use_cases import HandleB2BEventUseCase
from apps.inbox.models import ProcessedEvent
from settings import settings
from shared.db import SessionManager
from shared.inbox import IdempotentHandler
from shared.types import ServiceName


class StubHandleB2BEventUseCase:
    def __init__(self):
        self.calls: list[IncomingB2BEventSchema] = []
        self.error: Exception | None = None
        self.response = EventAcceptedResponseSchema(ticket_id=uuid4())

    async def __call__(self, event: IncomingB2BEventSchema) -> EventAcceptedResponseSchema:
        self.calls.append(event)
        if self.error:
            raise self.error
        return self.response


class StubIdempotentHandler:
    """Имитирует IdempotentHandler без БД: in-memory кеш по (sender, key)."""

    def __init__(self):
        self.cache: dict[tuple[ServiceName, UUID], dict] = {}
        self.handler_calls = 0

    async def handle(
        self,
        session,
        sender: ServiceName,
        key: UUID,
        handler,
        result_to_payload=None,
    ):
        cached = self.cache.get((sender, key))
        if cached is not None:
            return cached
        result = await handler()
        self.handler_calls += 1
        payload = result_to_payload(result) if result_to_payload else None
        if payload is not None:
            self.cache[(sender, key)] = payload
        return result


class StubSessionManager:
    """Имитирует SessionManager — yield None в качестве сессии."""

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def get_session(self):
        yield None


class EventsRouteProvider(Provider):
    def __init__(
        self,
        use_case_stub: StubHandleB2BEventUseCase,
        idempotent_stub: StubIdempotentHandler,
        session_stub: StubSessionManager,
    ):
        super().__init__()
        self.use_case_stub = use_case_stub
        self.idempotent_stub = idempotent_stub
        self.session_stub = session_stub

    @provide(scope=Scope.REQUEST)
    def get_use_case(self) -> HandleB2BEventUseCase:
        return self.use_case_stub  # type: ignore[return-value]

    @provide(scope=Scope.APP)
    def get_idempotent_handler(self) -> IdempotentHandler[ProcessedEvent]:
        return self.idempotent_stub  # type: ignore[return-value]

    @provide(scope=Scope.APP)
    def get_session_manager(self) -> SessionManager:
        return self.session_stub  # type: ignore[return-value]


@pytest.fixture
def stubs() -> tuple[StubHandleB2BEventUseCase, StubIdempotentHandler]:
    return StubHandleB2BEventUseCase(), StubIdempotentHandler()


@pytest.fixture
def client(stubs) -> TestClient:
    use_case_stub, idempotent_stub = stubs
    session_stub = StubSessionManager()

    app = FastAPI()
    app.include_router(events_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        EventsRouteProvider(use_case_stub, idempotent_stub, session_stub),
    )
    setup_dishka(container, app)
    return TestClient(app)


def _payload(event_type: str = 'PRODUCT_CREATED', idempotency_key: UUID | None = None) -> dict:
    return {
        'event_type': event_type,
        'idempotency_key': str(idempotency_key or uuid4()),
        'occurred_at': datetime.now(UTC).isoformat(),
        'payload': {
            'product_id': str(uuid4()),
            'seller_id': str(uuid4()),
            'json_after': {'title': 'X'},
        },
    }


def test_missing_service_key_returns_401(client: TestClient, stubs):
    use_case_stub, _ = stubs
    response = client.post('/api/v1/b2b/events', json=_payload())

    assert response.status_code == 401
    assert response.json()['code'] == 'INVALID_SERVICE_KEY'
    assert use_case_stub.calls == []


def test_wrong_service_key_returns_401(client: TestClient, stubs):
    use_case_stub, _ = stubs
    response = client.post(
        '/api/v1/b2b/events',
        json=_payload(),
        headers={'X-Service-Key': 'wrong-key'},
    )

    assert response.status_code == 401
    assert use_case_stub.calls == []


def test_valid_event_returns_202(client: TestClient, stubs):
    use_case_stub, _ = stubs
    response = client.post(
        '/api/v1/b2b/events',
        json=_payload(),
        headers={'X-Service-Key': settings.b2b_to_mod_key},
    )

    assert response.status_code == 202
    body = response.json()
    assert body['status'] == 'accepted'
    assert body['ticket_id'] == str(use_case_stub.response.ticket_id)
    assert len(use_case_stub.calls) == 1


def test_duplicate_idempotency_key_no_side_effects(client: TestClient, stubs):
    use_case_stub, idempotent_stub = stubs
    key = uuid4()
    payload = _payload(idempotency_key=key)

    first = client.post(
        '/api/v1/b2b/events',
        json=payload,
        headers={'X-Service-Key': settings.b2b_to_mod_key},
    )
    second = client.post(
        '/api/v1/b2b/events',
        json=payload,
        headers={'X-Service-Key': settings.b2b_to_mod_key},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json() == second.json()
    # Use-case дёрнулся ОДИН раз, второй — cached.
    assert len(use_case_stub.calls) == 1
    assert idempotent_stub.handler_calls == 1


def test_invalid_body_returns_400(client: TestClient):
    response = client.post(
        '/api/v1/b2b/events',
        json={'bogus': 'data'},
        headers={'X-Service-Key': settings.b2b_to_mod_key},
    )
    assert response.status_code == 400
    assert response.json()['code'] == 'INVALID_REQUEST'


def test_use_case_404_returns_404(client: TestClient, stubs):
    use_case_stub, _ = stubs
    use_case_stub.error = TicketNotFoundForEditError()
    response = client.post(
        '/api/v1/b2b/events',
        json=_payload(event_type='PRODUCT_EDITED'),
        headers={'X-Service-Key': settings.b2b_to_mod_key},
    )
    assert response.status_code == 404
    assert response.json()['code'] == 'TICKET_NOT_FOUND'
