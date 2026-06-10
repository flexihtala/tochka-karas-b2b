"""US-ORD-05: mark-delivered use-case tests.

Покрытие DoD:

- test_delivered_status_triggers_fulfill_to_b2b — happy-path: переход
  DELIVERING -> DELIVERED + ровно одно событие FULFILL_ORDER (target=b2b) в outbox
  с payload {order_id, items: [{sku_id, quantity}]}.
- test_fulfill_failure_retried_asynchronously — семантика воркера: при сбое
  dispatch воркер планирует ретрай через mark_retry с увеличенным next_retry_at
  и счётчиком retry_count. Использует shared.outbox.OutboxWorker напрямую
  поверх in-memory репозитория.
- test_repeated_fulfill_idempotent — повторный вызов use-case на уже DELIVERED
  заказе не enqueue дубликат, статус остаётся DELIVERED, события не растут.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from apps.orders.enums import OrderStatus
from apps.orders.errors import DeliverNotAllowedError, OrderNotFoundError
from apps.orders.models import OrderItem
from apps.orders.schemas.db import OrderReadSchema
from apps.orders.use_cases import MarkDeliveredUseCase
from apps.outbox.enums import OutboxEventType
from shared.outbox import OutboxStatus
from shared.outbox.worker import DEFAULT_BACKOFF_SECONDS, OutboxWorker
from shared.types import ServiceName
from tests.orders.fakes import (
    FakeOrderItemRepository,
    FakeOrderRepository,
    FakeOutboxRepository,
)


def make_order(*, status: str = OrderStatus.DELIVERING.value, user_id: UUID | None = None) -> OrderReadSchema:
    now = datetime.now(UTC)
    return OrderReadSchema(
        id=uuid4(),
        user_id=user_id or uuid4(),
        status=status,
        total_amount=20_000,
        idempotency_key=uuid4(),
        delivery_address=None,
        address_id=None,
        payment_method_id=None,
        comment=None,
        cancel_reason=None,
        created_at=now,
        updated_at=now,
    )


def make_item(order_id: UUID, sku_id: UUID | None = None, quantity: int = 2, unit_price: int = 10_000) -> OrderItem:
    now = datetime.now(UTC)
    im = OrderItem(
        id=uuid4(),
        order_id=order_id,
        sku_id=sku_id or uuid4(),
        product_id=uuid4(),
        product_title='Phone',
        sku_name='128GB',
        quantity=quantity,
        unit_price=unit_price,
        line_total=quantity * unit_price,
    )
    im.created_at = now  # type: ignore[attr-defined]
    im.updated_at = now  # type: ignore[attr-defined]
    return im


def make_use_case() -> tuple[MarkDeliveredUseCase, FakeOrderRepository, FakeOutboxRepository]:
    order_repo = FakeOrderRepository()
    item_repo = FakeOrderItemRepository(order_repo)
    outbox = FakeOutboxRepository()
    use_case = MarkDeliveredUseCase(
        order_repository=order_repo,
        order_item_repository=item_repo,
        outbox_repository=outbox,
    )
    return use_case, order_repo, outbox


@pytest.mark.anyio
async def test_delivered_status_triggers_fulfill_to_b2b():
    """Happy-path: DELIVERING -> DELIVERED, ровно одно FULFILL_ORDER в outbox к B2B."""
    use_case, order_repo, outbox = make_use_case()
    order = make_order(status=OrderStatus.DELIVERING.value)
    item_a = make_item(order.id, quantity=2)
    item_b = make_item(order.id, quantity=1, unit_price=5_000)
    order_repo.seed_order(order, [item_a, item_b])

    result = await use_case(order.id)

    assert result.status == OrderStatus.DELIVERED.value
    # Order в БД действительно обновлён.
    assert order_repo.by_id[order.id].status == OrderStatus.DELIVERED.value

    # Outbox содержит ровно одно событие FULFILL_ORDER -> b2b.
    assert len(outbox.events) == 1
    event = outbox.events[0]
    assert event.event_type == OutboxEventType.FULFILL_ORDER.value
    assert event.target_service == ServiceName.B2B.value
    assert event.status == OutboxStatus.PENDING

    # Payload по канону b2c-orders-flows.md#b2c-13-fulfill.
    assert event.payload['order_id'] == str(order.id)
    assert event.payload['items'] == [
        {'sku_id': str(item_a.sku_id), 'quantity': 2},
        {'sku_id': str(item_b.sku_id), 'quantity': 1},
    ]


@pytest.mark.anyio
async def test_repeated_fulfill_idempotent():
    """Повторный mark_delivered на DELIVERED-заказе не enqueue дубликат."""
    use_case, order_repo, outbox = make_use_case()
    order = make_order(status=OrderStatus.DELIVERING.value)
    item = make_item(order.id, quantity=4)
    order_repo.seed_order(order, [item])

    # Первый вызов — реальный переход.
    first = await use_case(order.id)
    assert first.status == OrderStatus.DELIVERED.value
    assert len(outbox.events) == 1

    # Второй вызов — должен быть no-op: статус остаётся DELIVERED, outbox
    # не пополняется.
    second = await use_case(order.id)
    assert second.status == OrderStatus.DELIVERED.value
    assert order_repo.by_id[order.id].status == OrderStatus.DELIVERED.value
    assert len(outbox.events) == 1, 'Повторный вызов не должен дублировать outbox-событие'
    assert len(outbox.enqueue_calls) == 1, 'enqueue_in_new_transaction не должен повторно вызываться'


@pytest.mark.anyio
async def test_mark_delivered_from_invalid_status_raises_409():
    """Из любого статуса кроме DELIVERING/DELIVERED — DeliverNotAllowedError 409."""
    for forbidden in (
        OrderStatus.CREATED.value,
        OrderStatus.PAID.value,
        OrderStatus.ASSEMBLING.value,
        OrderStatus.CANCELLED.value,
        OrderStatus.CANCEL_PENDING.value,
    ):
        use_case, order_repo, outbox = make_use_case()
        order = make_order(status=forbidden)
        order_repo.seed_order(order, [make_item(order.id)])

        with pytest.raises(DeliverNotAllowedError) as err:
            await use_case(order.id)
        assert err.value.current_status == forbidden
        assert outbox.events == []


@pytest.mark.anyio
async def test_mark_delivered_nonexistent_order_raises_404():
    use_case, _, _ = make_use_case()
    with pytest.raises(OrderNotFoundError):
        await use_case(uuid4())


# ---------------------------------------------------------------------------
# Worker retry-semantics
# ---------------------------------------------------------------------------


class _InMemoryOutboxRepo:
    """Минимальный async-репозиторий, реализующий контракт OutboxRepository,
    который дёргает OutboxWorker (claim_batch / mark_sent / mark_retry / mark_failed).

    Используется только для проверки семантики ретрая воркера, без Postgres.
    """

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.mark_sent_calls: list[UUID] = []
        self.mark_retry_calls: list[dict[str, Any]] = []
        self.mark_failed_calls: list[dict[str, Any]] = []

    def add(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    async def claim_batch(self, session: Any, batch_size: int = 10) -> list[Any]:
        now = datetime.now(UTC)
        ready: list[Any] = []
        for ev in self.events:
            if ev['status'] != OutboxStatus.PENDING.value:
                continue
            nra = ev.get('next_retry_at')
            if nra is not None and nra > now:
                continue
            ready.append(_EventView(ev))
            if len(ready) >= batch_size:
                break
        return ready

    async def mark_sent(self, session: Any, event_id: UUID) -> None:
        for ev in self.events:
            if ev['id'] == event_id:
                ev['status'] = OutboxStatus.SENT.value
                ev['sent_at'] = datetime.now(UTC)
                self.mark_sent_calls.append(event_id)
                return

    async def mark_retry(self, session: Any, event_id: UUID, next_retry_at: datetime, error: str) -> None:
        for ev in self.events:
            if ev['id'] == event_id:
                ev['retry_count'] = ev.get('retry_count', 0) + 1
                ev['next_retry_at'] = next_retry_at
                ev['last_error'] = error
                self.mark_retry_calls.append(
                    {
                        'event_id': event_id,
                        'next_retry_at': next_retry_at,
                        'error': error,
                        'retry_count_after': ev['retry_count'],
                    }
                )
                return

    async def mark_failed(self, session: Any, event_id: UUID, error: str) -> None:
        for ev in self.events:
            if ev['id'] == event_id:
                ev['status'] = OutboxStatus.FAILED.value
                ev['last_error'] = error
                self.mark_failed_calls.append({'event_id': event_id, 'error': error})
                return


class _EventView:
    """Тонкий объект-обёртка над dict — даёт worker'у атрибутный доступ (event.id и пр.)."""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _NullSessionManager:
    """Замещает SessionManager для OutboxWorker: воркер открывает 'сессию' и
    передаёт её в репозиторий. Нам сессия не нужна — отдадим объект-заглушку.
    """

    class _Ctx:
        async def __aenter__(self) -> Any:
            return None

        async def __aexit__(self, *exc_info: Any) -> None:
            return None

    def get_session(self) -> _Ctx:
        return self._Ctx()


@pytest.mark.anyio
async def test_fulfill_failure_retried_asynchronously():
    """Симулируем воркер: dispatch падает 5xx → mark_retry с next_retry_at в будущем
    и инкрементом retry_count. Это и есть гарантия "async retry" для FULFILL.
    """
    repo = _InMemoryOutboxRepo()
    event_id = uuid4()
    repo.add(
        {
            'id': event_id,
            'idempotency_key': uuid4(),
            'event_type': OutboxEventType.FULFILL_ORDER.value,
            'target_service': ServiceName.B2B.value,
            'payload': {'order_id': str(uuid4()), 'items': []},
            'status': OutboxStatus.PENDING.value,
            'retry_count': 0,
            'next_retry_at': None,
            'sent_at': None,
            'last_error': None,
        }
    )

    async def failing_dispatch(_event: Any) -> None:
        raise RuntimeError('b2b 503: connection refused')

    worker = OutboxWorker(
        session_manager=_NullSessionManager(),  # type: ignore[arg-type]
        repository=repo,  # type: ignore[arg-type]
        dispatch=failing_dispatch,
        poll_interval=0.0,
        batch_size=10,
    )

    before = datetime.now(UTC)
    processed = await worker._tick()
    after = datetime.now(UTC)

    assert processed == 1
    # Не помечен SENT — dispatch упал.
    assert repo.mark_sent_calls == []
    # Не помечен FAILED — это первая попытка, до MAX_RETRIES далеко.
    assert repo.mark_failed_calls == []

    # mark_retry вызван ровно один раз.
    assert len(repo.mark_retry_calls) == 1
    call = repo.mark_retry_calls[0]
    assert call['event_id'] == event_id
    assert 'b2b 503' in call['error']
    assert call['retry_count_after'] == 1
    # next_retry_at установлен в будущее, в районе DEFAULT_BACKOFF_SECONDS[0].
    expected_delay = DEFAULT_BACKOFF_SECONDS[0]
    delay_low = before + timedelta(seconds=expected_delay - 1)
    delay_high = after + timedelta(seconds=expected_delay + 1)
    assert delay_low <= call['next_retry_at'] <= delay_high

    # Состояние события: PENDING (готов к следующей попытке), retry_count == 1,
    # next_retry_at в будущем.
    stored = repo.events[0]
    assert stored['status'] == OutboxStatus.PENDING.value
    assert stored['retry_count'] == 1
    assert stored['next_retry_at'] is not None
    assert stored['next_retry_at'] > after, 'next_retry_at должен быть в будущем'

    # Сразу же повторный tick не должен забрать событие — ещё не время.
    second_processed = await worker._tick()
    assert second_processed == 0
    assert len(repo.mark_retry_calls) == 1
