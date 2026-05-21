"""Тесты ReserveInventoryUseCase (US-B2B-08).

Покрытие:
- happy path multi-SKU,
- 409 RESERVE_FAILED при недостатке остатков (all-or-nothing, остальные SKU не списываются),
- идемпотентность по idempotency_key (повтор не списывает дважды),
- SKU_OUT_OF_STOCK event в outbox при active_quantity → 0,
- (см. test_unreserve_use_case.py для unreserve)
"""

from uuid import UUID, uuid4

import pytest

from apps.inventory.enums import InventoryEventType, ReserveFailureReason
from apps.inventory.errors import InventoryConflictError
from apps.inventory.schemas import (
    InventoryItemRequestSchema,
    ReserveRequestSchema,
)
from apps.inventory.use_cases import ReserveInventoryUseCase
from shared.types import ServiceName
from tests.inventory.fakes import (
    FakeInboxRepository,
    FakeInventoryRepository,
    FakeOutboxRepository,
    FakeSessionManager,
)


def make_use_case(
    *,
    inventory: FakeInventoryRepository | None = None,
    outbox: FakeOutboxRepository | None = None,
    inbox: FakeInboxRepository | None = None,
) -> tuple[ReserveInventoryUseCase, FakeInventoryRepository, FakeOutboxRepository, FakeInboxRepository]:
    inventory_repo = inventory or FakeInventoryRepository()
    outbox_repo = outbox or FakeOutboxRepository()
    inbox_repo = inbox or FakeInboxRepository()
    use_case = ReserveInventoryUseCase(
        inventory_repository=inventory_repo,  # type: ignore[arg-type]
        outbox_repository=outbox_repo,  # type: ignore[arg-type]
        inbox_repository=inbox_repo,  # type: ignore[arg-type]
        session_manager=FakeSessionManager(),  # type: ignore[arg-type]
    )
    return use_case, inventory_repo, outbox_repo, inbox_repo


def make_request(
    items: list[tuple[UUID, int]] | None = None,
    idempotency_key: UUID | None = None,
    order_id: UUID | None = None,
) -> ReserveRequestSchema:
    return ReserveRequestSchema(
        idempotency_key=idempotency_key or uuid4(),
        order_id=order_id or uuid4(),
        items=[InventoryItemRequestSchema(sku_id=sku_id, quantity=qty) for sku_id, qty in (items or [])],
    )


@pytest.mark.anyio
async def test_reserve_all_skus_succeeds():
    """Happy path: оба SKU имеют достаточно — резерв применяется атомарно."""
    use_case, inventory, outbox, inbox = make_use_case()
    sku_a, sku_b = uuid4(), uuid4()
    inventory.add_sku(sku_a, active=10, reserved=0)
    inventory.add_sku(sku_b, active=5, reserved=1)

    order_id = uuid4()
    response = await use_case(make_request([(sku_a, 3), (sku_b, 2)], order_id=order_id))

    # Ответ по спецификации: order_id, status='RESERVED', reserved_at
    assert response.order_id == order_id
    assert response.status == 'RESERVED'
    assert response.reserved_at is not None
    # Состояние SKU после reserve
    assert inventory.skus[sku_a] == {'active_quantity': 7, 'reserved_quantity': 3}
    assert inventory.skus[sku_b] == {'active_quantity': 3, 'reserved_quantity': 3}
    # active_quantity ни у одного не достиг 0 → нет outbox-событий
    assert outbox.enqueued == []
    # Записан processed_event для idempotency
    assert len(inbox.records) == 1


@pytest.mark.anyio
async def test_partial_insufficient_stock_returns_409_all_rollback():
    """Один SKU short → InventoryConflictError (409 RESERVE_FAILED).

    ALL-OR-NOTHING: остальные SKU остаются нетронутыми (никаких списаний).
    """
    use_case, inventory, outbox, inbox = make_use_case()
    sku_ok = uuid4()
    sku_short = uuid4()
    inventory.add_sku(sku_ok, active=10, reserved=0)
    inventory.add_sku(sku_short, active=1, reserved=0)

    with pytest.raises(InventoryConflictError) as exc_info:
        await use_case(make_request([(sku_ok, 5), (sku_short, 3)]))

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == 'RESERVE_FAILED'
    assert len(exc_info.value.failed_items) == 1
    failed = exc_info.value.failed_items[0]
    assert failed['sku_id'] == str(sku_short)
    assert failed['requested'] == 3
    assert failed['available'] == 1
    assert failed['reason'] == ReserveFailureReason.INSUFFICIENT_STOCK.value

    # ROLLBACK: остальные SKU нетронуты
    assert inventory.skus[sku_ok] == {'active_quantity': 10, 'reserved_quantity': 0}
    assert inventory.skus[sku_short] == {'active_quantity': 1, 'reserved_quantity': 0}
    # Outbox пустой
    assert outbox.enqueued == []
    # processed_event НЕ записан — операция провалилась, idempotency не кешируется на 409
    assert inbox.records == []


@pytest.mark.anyio
async def test_partial_out_of_stock_returns_409_with_reason():
    """Когда у SKU active_quantity = 0, причина OUT_OF_STOCK (не INSUFFICIENT_STOCK)."""
    use_case, inventory, _outbox, _inbox = make_use_case()
    sku_id = uuid4()
    inventory.add_sku(sku_id, active=0, reserved=0)

    with pytest.raises(InventoryConflictError) as exc_info:
        await use_case(make_request([(sku_id, 1)]))

    assert exc_info.value.failed_items[0]['reason'] == ReserveFailureReason.OUT_OF_STOCK.value
    assert exc_info.value.failed_items[0]['available'] == 0


@pytest.mark.anyio
async def test_idempotent_reserve_returns_200_without_double_deduction():
    """Повтор запроса с тем же idempotency_key → cached response, без дополнительного списания.

    Имитируем реальный сценарий: B2C ретраит запрос из-за таймаута (на стороне сети
    запрос дошёл и был обработан, но клиент ответ не получил). Use-case должен:
    1) обнаружить cached в processed_events,
    2) вернуть его без вызова reserve()/outbox.
    """
    use_case, inventory, outbox, inbox = make_use_case()
    sku_a = uuid4()
    inventory.add_sku(sku_a, active=10, reserved=0)

    idem_key = uuid4()
    order_id = uuid4()
    first = await use_case(make_request([(sku_a, 3)], idempotency_key=idem_key, order_id=order_id))
    assert first.status == 'RESERVED'
    assert first.order_id == order_id
    assert inventory.skus[sku_a] == {'active_quantity': 7, 'reserved_quantity': 3}

    # Повторный вызов с тем же ключом
    second = await use_case(make_request([(sku_a, 3)], idempotency_key=idem_key, order_id=order_id))
    # Ответ идентичен (cached)
    assert second.status == 'RESERVED'
    assert second.order_id == order_id
    assert second.reserved_at == first.reserved_at
    # Никакого второго списания
    assert inventory.skus[sku_a] == {'active_quantity': 7, 'reserved_quantity': 3}
    # reserve() вызван только один раз
    assert len(inventory.reserve_calls) == 1
    # outbox пустой (active не достиг 0)
    assert outbox.enqueued == []
    # processed_event записан один раз
    assert len(inbox.records) == 1


@pytest.mark.anyio
async def test_idempotent_reserve_with_different_items_returns_cached():
    """Если клиент по ошибке прислал тот же idempotency_key с другим телом — мы всё
    равно возвращаем cached (защита от двойного списания приоритетнее проверки тела
    запроса). Это соответствует канону: TTL 1 час."""
    use_case, inventory, _outbox, _inbox = make_use_case()
    sku_a = uuid4()
    inventory.add_sku(sku_a, active=10, reserved=0)

    idem_key = uuid4()
    order_id = uuid4()
    first = await use_case(make_request([(sku_a, 3)], idempotency_key=idem_key, order_id=order_id))
    # Второй вызов с тем же ключом, но другим quantity
    second = await use_case(make_request([(sku_a, 5)], idempotency_key=idem_key, order_id=order_id))

    # Возвращаем cached от первого вызова
    assert second.order_id == first.order_id
    assert second.status == first.status
    assert second.reserved_at == first.reserved_at
    # Состояние SKU соответствует первому вызову (никакого второго списания)
    assert inventory.skus[sku_a] == {'active_quantity': 7, 'reserved_quantity': 3}


@pytest.mark.anyio
async def test_sku_out_of_stock_event_emitted():
    """Reserve до active_quantity == 0 → outbox SKU_OUT_OF_STOCK с target=b2c."""
    use_case, inventory, outbox, _inbox = make_use_case()
    sku_id = uuid4()
    inventory.add_sku(sku_id, active=2, reserved=0)

    response = await use_case(make_request([(sku_id, 2)]))

    assert response.status == 'RESERVED'
    assert inventory.skus[sku_id]['active_quantity'] == 0
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == InventoryEventType.SKU_OUT_OF_STOCK.value
    assert event.target_service == ServiceName.B2C
    assert event.payload == {'sku_id': str(sku_id)}


@pytest.mark.anyio
async def test_sku_out_of_stock_event_only_for_zeroed_skus():
    """В одном reserve несколько SKU; событие SKU_OUT_OF_STOCK эмитится только
    для тех, у которых active стал 0."""
    use_case, inventory, outbox, _inbox = make_use_case()
    sku_zero = uuid4()  # активного 1 → после reserve станет 0
    sku_nonzero = uuid4()  # активного 5 → после reserve станет 3
    inventory.add_sku(sku_zero, active=1, reserved=0)
    inventory.add_sku(sku_nonzero, active=5, reserved=0)

    await use_case(make_request([(sku_zero, 1), (sku_nonzero, 2)]))

    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].payload == {'sku_id': str(sku_zero)}


@pytest.mark.anyio
async def test_reserve_with_nonexistent_sku_returns_409_not_found_reason():
    """SKU отсутствует в БД → failed_items с reason=NOT_FOUND."""
    use_case, inventory, _outbox, _inbox = make_use_case()
    real_sku = uuid4()
    fake_sku = uuid4()
    inventory.add_sku(real_sku, active=10, reserved=0)

    with pytest.raises(InventoryConflictError) as exc_info:
        await use_case(make_request([(real_sku, 1), (fake_sku, 1)]))

    failed_by_id = {item['sku_id']: item for item in exc_info.value.failed_items}
    assert str(fake_sku) in failed_by_id
    assert failed_by_id[str(fake_sku)]['reason'] == ReserveFailureReason.NOT_FOUND.value
    # real_sku не должен быть списан
    assert inventory.skus[real_sku] == {'active_quantity': 10, 'reserved_quantity': 0}
