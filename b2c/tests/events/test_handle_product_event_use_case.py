"""Unit + router тесты US-ORD-04 POST /api/v1/events/product.

DoD-тесты (exact names — НЕ переименовывать):
- test_product_blocked_marks_cart_items_unavailable
- test_orders_not_affected_by_product_blocked
- test_idempotent_event_no_side_effects
- test_missing_service_key_returns_401
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.errors import setup_error_handlers
from apps.events.routers import router as events_router
from apps.events.schemas import (
    ProductEventRequestSchema,
    ProductEventResponseSchema,
    ProductEventType,
)
from apps.events.use_cases import HandleProductEventUseCase
from tests.events.fakes import (
    FakeIdempotentHandler,
    FakeSessionManager,
    FakeSkuUnavailabilityRepository,
)


def _make_payload(
    *,
    event: ProductEventType,
    product_id: UUID,
    sku_ids: list[UUID],
    idempotency_key: UUID | None = None,
    reason: str | None = None,
) -> ProductEventRequestSchema:
    return ProductEventRequestSchema(
        idempotency_key=idempotency_key or uuid4(),
        event=event,
        product_id=product_id,
        sku_ids=sku_ids,
        reason=reason,
        date=datetime.now(UTC),
    )


def _make_use_case() -> tuple[
    HandleProductEventUseCase,
    FakeSessionManager,
    FakeIdempotentHandler,
    FakeSkuUnavailabilityRepository,
]:
    session_manager = FakeSessionManager()
    idempotent_handler = FakeIdempotentHandler()
    repository = FakeSkuUnavailabilityRepository()
    use_case = HandleProductEventUseCase(
        session_manager=session_manager,  # type: ignore[arg-type]
        idempotent_handler=idempotent_handler,  # type: ignore[arg-type]
        unavailability_repository=repository,  # type: ignore[arg-type]
    )
    return use_case, session_manager, idempotent_handler, repository


# --------------- DoD: test_product_blocked_marks_cart_items_unavailable ---------------


@pytest.mark.anyio
async def test_product_blocked_marks_cart_items_unavailable():
    """PRODUCT_BLOCKED → SKU попадает в sku_unavailability с reason=BLOCKED.

    Cart_items в БД не модифицируются (ADR US-ORD-04: enrichment из B2B на GET /cart);
    "помеченность" — это наличие в sku_unavailability, наблюдаемое cart enrichment'ом.
    """
    use_case, _sm, _ih, repository = _make_use_case()

    product_id = uuid4()
    sku_a, sku_b = uuid4(), uuid4()
    payload = _make_payload(
        event=ProductEventType.PRODUCT_BLOCKED,
        product_id=product_id,
        sku_ids=[sku_a, sku_b],
        reason='Описание не соответствует товару',
    )

    response = await use_case(payload)

    assert isinstance(response, ProductEventResponseSchema)
    assert response.accepted is True

    # Каждый sku из payload теперь помечен как BLOCKED.
    assert set(repository.records.keys()) == {sku_a, sku_b}
    for sku_id in (sku_a, sku_b):
        assert repository.records[sku_id]['reason'] == 'BLOCKED'
        assert repository.records[sku_id]['product_id'] == product_id
        assert repository.records[sku_id]['event_idempotency_key'] == payload.idempotency_key

    # И ровно один upsert на событие (batch).
    assert len(repository.upsert_calls) == 1
    assert repository.upsert_calls[0]['sku_ids'] == [sku_a, sku_b]


@pytest.mark.anyio
async def test_product_deleted_marks_skus_with_deleted_reason():
    use_case, _, _, repository = _make_use_case()
    sku = uuid4()
    payload = _make_payload(
        event=ProductEventType.PRODUCT_DELETED,
        product_id=uuid4(),
        sku_ids=[sku],
    )

    await use_case(payload)

    assert repository.records[sku]['reason'] == 'DELETED'


@pytest.mark.anyio
async def test_sku_out_of_stock_marks_skus_with_out_of_stock_reason():
    use_case, _, _, repository = _make_use_case()
    sku = uuid4()
    payload = _make_payload(
        event=ProductEventType.SKU_OUT_OF_STOCK,
        product_id=uuid4(),
        sku_ids=[sku],
    )

    await use_case(payload)

    assert repository.records[sku]['reason'] == 'OUT_OF_STOCK'


# --------------- DoD: test_orders_not_affected_by_product_blocked ---------------


@pytest.mark.anyio
async def test_orders_not_affected_by_product_blocked():
    """Order-domain не упоминается в use case — проверяем границы.

    Per canon (Flow B2C-12): "Заказы НЕ трогать. Заказы с зафиксированными ценами
    продолжают обрабатываться." В US-ORD-04 нет order_repository, нет вызовов к
    order-таблицам — нет побочных эффектов на заказы.

    Тест ВЕРИФИЦИРУЕТ: после события use case использует только репозиторий
    sku_unavailability и idempotent_handler; ни одного дополнительного писателя.
    """
    use_case, session_manager, idempotent_handler, repository = _make_use_case()

    sku = uuid4()
    payload = _make_payload(
        event=ProductEventType.PRODUCT_BLOCKED,
        product_id=uuid4(),
        sku_ids=[sku],
    )

    await use_case(payload)

    # use case взаимодействует только с тремя зависимостями — никаких order-репов.
    assert hasattr(use_case, 'unavailability_repository')
    assert hasattr(use_case, 'idempotent_handler')
    assert hasattr(use_case, 'session_manager')
    public_attrs = {a for a in vars(use_case).keys() if not a.startswith('_')}
    assert public_attrs == {'session_manager', 'idempotent_handler', 'unavailability_repository'}, (
        f'HandleProductEventUseCase must not depend on order/cart repositories — unexpected attrs: {public_attrs}'
    )

    # И на уровне side effects: записан только SKU в unavailability.
    assert sku in repository.records
    assert idempotent_handler.handler_calls == 1
    assert session_manager.session_calls == 1


# --------------- DoD: test_idempotent_event_no_side_effects ---------------


@pytest.mark.anyio
async def test_idempotent_event_no_side_effects():
    """Повторный POST с тем же idempotency_key — handler не вызывается заново.

    Идемпотентность реализована через shared.inbox.IdempotentHandler:
    UNIQUE(sender_service, idempotency_key) в processed_events.
    """
    use_case, _, idempotent_handler, repository = _make_use_case()

    sku = uuid4()
    idempotency_key = uuid4()
    payload = _make_payload(
        event=ProductEventType.PRODUCT_BLOCKED,
        product_id=uuid4(),
        sku_ids=[sku],
        idempotency_key=idempotency_key,
    )

    first = await use_case(payload)
    assert first.accepted is True
    assert idempotent_handler.handler_calls == 1
    assert len(repository.upsert_calls) == 1

    # Повторяем с тем же ключом — handler НЕ вызывается, upsert НЕ дёргается.
    second = await use_case(payload)
    assert second.accepted is True
    assert idempotent_handler.handler_calls == 1, 'handler must run exactly once'
    assert len(repository.upsert_calls) == 1, 'unavailability repo must not be touched again'

    # Запись в кэше осталась прежней — никакого дублирования.
    assert len(repository.records) == 1


@pytest.mark.anyio
async def test_different_idempotency_keys_are_processed_separately():
    """Sanity: разные ключи проходят как разные события."""
    use_case, _, idempotent_handler, repository = _make_use_case()
    sku = uuid4()
    product_id = uuid4()

    await use_case(
        _make_payload(
            event=ProductEventType.PRODUCT_BLOCKED,
            product_id=product_id,
            sku_ids=[sku],
        )
    )
    await use_case(
        _make_payload(
            event=ProductEventType.PRODUCT_BLOCKED,
            product_id=product_id,
            sku_ids=[sku],
        )
    )

    assert idempotent_handler.handler_calls == 2
    assert len(repository.upsert_calls) == 2


# --------------- DoD: test_missing_service_key_returns_401 ---------------


class _StubHandleProductEvent:
    """Стаб use-case'а для router-теста — не должен дёргаться при 401."""

    def __init__(self):
        self.calls: list[ProductEventRequestSchema] = []

    async def __call__(self, payload: ProductEventRequestSchema) -> ProductEventResponseSchema:
        self.calls.append(payload)
        return ProductEventResponseSchema(accepted=True)


class _EventsRouteProvider(Provider):
    def __init__(self, stub: _StubHandleProductEvent):
        super().__init__()
        self.stub = stub

    @provide(scope=Scope.REQUEST)
    def get_use_case(self) -> HandleProductEventUseCase:
        return self.stub  # type: ignore[return-value]


def _make_app(stub: _StubHandleProductEvent) -> FastAPI:
    app = FastAPI()
    app.include_router(events_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), _EventsRouteProvider(stub))
    setup_dishka(container, app)
    return app


def _valid_body() -> dict:
    return {
        'idempotency_key': str(uuid4()),
        'event': 'PRODUCT_BLOCKED',
        'product_id': str(uuid4()),
        'sku_ids': [str(uuid4())],
        'reason': 'test',
        'date': datetime.now(UTC).isoformat(),
    }


def test_missing_service_key_returns_401():
    """Без X-Service-Key → 401, use case не дёргается."""
    stub = _StubHandleProductEvent()
    client = TestClient(_make_app(stub))

    response = client.post('/api/v1/events/product', json=_valid_body())

    assert response.status_code == 401
    assert response.json()['code'] == 'INVALID_SERVICE_KEY'
    assert stub.calls == []


def test_wrong_service_key_returns_401():
    """Неверный X-Service-Key → 401."""
    stub = _StubHandleProductEvent()
    client = TestClient(_make_app(stub))

    response = client.post(
        '/api/v1/events/product',
        json=_valid_body(),
        headers={'X-Service-Key': 'wrong-key'},
    )

    assert response.status_code == 401
    assert stub.calls == []


def test_valid_service_key_returns_200():
    """С правильным X-Service-Key — 200 и use case вызван."""
    from settings import settings  # импортируем здесь, чтобы не ловить порядок инициализации

    stub = _StubHandleProductEvent()
    client = TestClient(_make_app(stub))

    response = client.post(
        '/api/v1/events/product',
        json=_valid_body(),
        headers={'X-Service-Key': settings.b2b_to_b2c_key},
    )

    assert response.status_code == 200
    assert response.json() == {'accepted': True}
    assert len(stub.calls) == 1
