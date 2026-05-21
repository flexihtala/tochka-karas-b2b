"""Тесты router'а apps.events.routers — POST /api/v1/moderation/events."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.errors import setup_error_handlers
from apps.events.errors import BlockedReasonRequiredError, EventProductNotFoundError
from apps.events.routers import router as events_router
from apps.events.schemas.request import ModerationEventRequestSchema
from apps.events.schemas.response import ModerationEventResponseSchema
from apps.events.use_cases import ApplyModerationEventUseCase
from apps.products.enums import ProductStatus
from settings import settings


class StubApplyModerationEventUseCase:
    def __init__(self) -> None:
        self.calls: list[ModerationEventRequestSchema] = []
        self.error: Exception | None = None
        self.response = ModerationEventResponseSchema(
            product_id=uuid4(),
            status=ProductStatus.MODERATED,
        )

    async def __call__(self, data: ModerationEventRequestSchema) -> ModerationEventResponseSchema:
        self.calls.append(data)
        if self.error:
            raise self.error
        return self.response


class EventsRouteProvider(Provider):
    def __init__(self, stub: StubApplyModerationEventUseCase) -> None:
        super().__init__()
        self.stub = stub

    @provide(scope=Scope.REQUEST)
    def get_apply_moderation_use_case(self) -> ApplyModerationEventUseCase:
        return self.stub  # type: ignore[return-value]


def _make_app(stub: StubApplyModerationEventUseCase) -> FastAPI:
    app = FastAPI()
    app.include_router(events_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), EventsRouteProvider(stub))
    setup_dishka(container, app)
    return app


def _moderated_payload(product_id: UUID | None = None) -> dict[str, Any]:
    return {
        'idempotency_key': str(uuid4()),
        'product_id': str(product_id or uuid4()),
        'event_type': 'MODERATED',
        'occurred_at': datetime.now(UTC).isoformat(),
    }


def _blocked_payload(*, hard_block: bool = False) -> dict[str, Any]:
    return {
        'idempotency_key': str(uuid4()),
        'product_id': str(uuid4()),
        'event_type': 'BLOCKED',
        'blocking_reason_id': str(uuid4()),
        'moderator_comment': 'Несоответствие',
        'hard_block': hard_block,
        'field_reports': [
            {'field_name': 'description', 'sku_id': None, 'comment': 'скопировано'},
        ],
        'occurred_at': datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def stub() -> StubApplyModerationEventUseCase:
    return StubApplyModerationEventUseCase()


def test_apply_moderation_endpoint_returns_204(stub: StubApplyModerationEventUseCase):
    client = TestClient(_make_app(stub))

    response = client.post(
        '/api/v1/moderation/events',
        json=_moderated_payload(),
        headers={'X-Service-Key': settings.mod_to_b2b_key},
    )

    assert response.status_code == 204
    assert response.text == ''
    assert len(stub.calls) == 1
    assert stub.calls[0].event_type.value == 'MODERATED'


def test_apply_moderation_blocked_event(stub: StubApplyModerationEventUseCase):
    client = TestClient(_make_app(stub))

    response = client.post(
        '/api/v1/moderation/events',
        json=_blocked_payload(hard_block=False),
        headers={'X-Service-Key': settings.mod_to_b2b_key},
    )

    assert response.status_code == 204
    assert len(stub.calls) == 1
    assert stub.calls[0].event_type.value == 'BLOCKED'
    assert stub.calls[0].hard_block is False


def test_apply_moderation_missing_service_key_returns_401(stub: StubApplyModerationEventUseCase):
    client = TestClient(_make_app(stub))

    response = client.post('/api/v1/moderation/events', json=_moderated_payload())

    assert response.status_code == 401
    assert response.json()['code'] == 'INVALID_SERVICE_KEY'
    assert stub.calls == []


def test_apply_moderation_wrong_service_key_returns_401(stub: StubApplyModerationEventUseCase):
    client = TestClient(_make_app(stub))

    response = client.post(
        '/api/v1/moderation/events',
        json=_moderated_payload(),
        headers={'X-Service-Key': 'wrong-key'},
    )

    assert response.status_code == 401
    assert response.json()['code'] == 'INVALID_SERVICE_KEY'
    assert stub.calls == []


def test_apply_moderation_invalid_body_returns_400(stub: StubApplyModerationEventUseCase):
    client = TestClient(_make_app(stub))

    response = client.post(
        '/api/v1/moderation/events',
        json={},
        headers={'X-Service-Key': settings.mod_to_b2b_key},
    )

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}
    assert stub.calls == []


def test_apply_moderation_product_not_found_returns_404(stub: StubApplyModerationEventUseCase):
    stub.error = EventProductNotFoundError()
    client = TestClient(_make_app(stub))

    response = client.post(
        '/api/v1/moderation/events',
        json=_moderated_payload(),
        headers={'X-Service-Key': settings.mod_to_b2b_key},
    )

    assert response.status_code == 404
    body = response.json()
    assert body['code'] == 'NOT_FOUND'


def test_apply_moderation_blocked_without_reason_returns_400(stub: StubApplyModerationEventUseCase):
    stub.error = BlockedReasonRequiredError()
    client = TestClient(_make_app(stub))

    response = client.post(
        '/api/v1/moderation/events',
        json=_blocked_payload(),
        headers={'X-Service-Key': settings.mod_to_b2b_key},
    )

    assert response.status_code == 400
    body = response.json()
    assert body['code'] == 'INVALID_REQUEST'
