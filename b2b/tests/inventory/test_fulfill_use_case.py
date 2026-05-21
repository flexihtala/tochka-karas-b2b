"""Тесты FulfillInventoryUseCase (US-B2B-10).

Покрытие (DoD):
- `test_fulfill_decreases_reserved_quantity` — счётчик резерва уменьшается на
  переданное количество.
- `test_active_quantity_unchanged` — `active_quantity` не меняется при fulfill
  (товар уже был исключён из активного остатка при reserve).
- `test_idempotent_fulfill_no_double_deduction` — повторный fulfill с тем же
  `order_id` не приводит к повторному списанию `reserved_quantity`.

Дополнительные кейсы:
- Частичная идемпотентность: повтор с тем же order_id, но другим набором items —
  списываются только новые пары.
- Игнорирование несуществующих SKU (best-effort).
"""

from uuid import UUID, uuid4

import pytest

from apps.inventory.schemas import FulfillRequestSchema, InventoryItemRequestSchema
from apps.inventory.use_cases import FulfillInventoryUseCase
from tests.inventory.fakes import (
    FakeFulfilledOrderRepository,
    FakeInventoryRepository,
    FakeSessionManager,
)


def make_use_case(
    *,
    inventory: FakeInventoryRepository | None = None,
    fulfilled_orders: FakeFulfilledOrderRepository | None = None,
) -> tuple[FulfillInventoryUseCase, FakeInventoryRepository, FakeFulfilledOrderRepository]:
    inventory_repo = inventory or FakeInventoryRepository()
    fulfilled_repo = fulfilled_orders or FakeFulfilledOrderRepository()
    use_case = FulfillInventoryUseCase(
        inventory_repository=inventory_repo,  # type: ignore[arg-type]
        fulfilled_order_repository=fulfilled_repo,  # type: ignore[arg-type]
        session_manager=FakeSessionManager(),  # type: ignore[arg-type]
    )
    return use_case, inventory_repo, fulfilled_repo


def make_request(
    items: list[tuple[UUID, int]] | None = None,
    order_id: UUID | None = None,
) -> FulfillRequestSchema:
    return FulfillRequestSchema(
        order_id=order_id or uuid4(),
        items=[InventoryItemRequestSchema(sku_id=sku_id, quantity=qty) for sku_id, qty in (items or [])],
    )


@pytest.mark.anyio
async def test_fulfill_decreases_reserved_quantity():
    """DoD: fulfill уменьшает `reserved_quantity` на переданное quantity."""
    use_case, inventory, fulfilled = make_use_case()
    sku_a, sku_b = uuid4(), uuid4()
    # Резерв уже сделан (имитируем состояние после reserve)
    inventory.add_sku(sku_a, active=7, reserved=3)
    inventory.add_sku(sku_b, active=3, reserved=2)

    response = await use_case(make_request([(sku_a, 3), (sku_b, 2)]))

    assert response.status == "FULFILLED"
    # reserved_quantity уменьшился ровно на quantity
    assert inventory.skus[sku_a]['reserved_quantity'] == 0
    assert inventory.skus[sku_b]['reserved_quantity'] == 0
    # fulfill вызван ровно один раз и со всеми items
    assert len(inventory.fulfill_calls) == 1
    # Журнал fulfilled_orders записан для каждой пары
    assert len(fulfilled.record_calls) == 2


@pytest.mark.anyio
async def test_active_quantity_unchanged():
    """DoD: при fulfill `active_quantity` НЕ меняется.

    Это отличает fulfill от unreserve: товар уже не в активном остатке (был
    исключён на reserve), fulfill — финальное снятие с резерва.
    """
    use_case, inventory, _fulfilled = make_use_case()
    sku_id = uuid4()
    inventory.add_sku(sku_id, active=7, reserved=3)

    response = await use_case(make_request([(sku_id, 3)]))

    assert response.status == "FULFILLED"
    # active_quantity — без изменений
    assert inventory.skus[sku_id]['active_quantity'] == 7
    # reserved_quantity — уменьшился
    assert inventory.skus[sku_id]['reserved_quantity'] == 0


@pytest.mark.anyio
async def test_idempotent_fulfill_no_double_deduction():
    """DoD: повторный fulfill с тем же order_id не списывает дважды.

    Сценарий: B2C ретраит запрос из-за таймаута. Use-case должен:
    1) увидеть запись в `fulfilled_orders` для этой пары (order_id, sku_id),
    2) пропустить items и вернуть {ok: true} без второго вызова inventory.fulfill().
    """
    use_case, inventory, fulfilled = make_use_case()
    sku_a, sku_b = uuid4(), uuid4()
    inventory.add_sku(sku_a, active=7, reserved=3)
    inventory.add_sku(sku_b, active=3, reserved=2)

    order_id = uuid4()
    first = await use_case(make_request([(sku_a, 3), (sku_b, 2)], order_id=order_id))
    assert first.status == "FULFILLED"
    # После первого fulfill — резерв снят
    assert inventory.skus[sku_a]['reserved_quantity'] == 0
    assert inventory.skus[sku_b]['reserved_quantity'] == 0

    # Повторный вызов с тем же order_id
    second = await use_case(make_request([(sku_a, 3), (sku_b, 2)], order_id=order_id))
    assert second.status == "FULFILLED"
    # Состояние не изменилось — никакого второго списания
    assert inventory.skus[sku_a]['reserved_quantity'] == 0
    assert inventory.skus[sku_b]['reserved_quantity'] == 0
    # inventory.fulfill вызван только один раз (на первом fulfill)
    assert len(inventory.fulfill_calls) == 1
    # Журнал fulfilled_orders.record вызван только дважды (sku_a + sku_b на первом fulfill,
    # на повторе — пропуск, так как пары уже есть)
    assert len(fulfilled.record_calls) == 2


@pytest.mark.anyio
async def test_partial_idempotency_records_only_new_pairs():
    """Если в повторе появился новый SKU (order_id тот же), списывается только новый.

    Реалистичный сценарий маловероятен (order_id обычно стабилен по составу),
    но это защита от рассинхронизации между B2C и B2B.
    """
    use_case, inventory, fulfilled = make_use_case()
    sku_a, sku_b = uuid4(), uuid4()
    inventory.add_sku(sku_a, active=7, reserved=3)
    inventory.add_sku(sku_b, active=3, reserved=2)

    order_id = uuid4()
    await use_case(make_request([(sku_a, 3)], order_id=order_id))
    assert inventory.skus[sku_a]['reserved_quantity'] == 0
    assert inventory.skus[sku_b]['reserved_quantity'] == 2

    # Повтор с расширенным набором items — sku_a уже зафиксирован, sku_b — нет
    response = await use_case(make_request([(sku_a, 3), (sku_b, 2)], order_id=order_id))
    assert response.status == "FULFILLED"
    # sku_a — без изменений
    assert inventory.skus[sku_a]['reserved_quantity'] == 0
    # sku_b — списан
    assert inventory.skus[sku_b]['reserved_quantity'] == 0
    # Журнал: 1 запись на первом fulfill + 1 на втором (только sku_b)
    assert len(fulfilled.record_calls) == 2
    # inventory.fulfill вызван дважды: оба раза с одним item
    assert len(inventory.fulfill_calls) == 2
    assert inventory.fulfill_calls[1] == [(sku_b, 2)]


@pytest.mark.anyio
async def test_fulfill_different_order_ids_are_independent():
    """Разные order_id — независимые fulfill'ы; UNIQUE(order_id, sku_id) их не ограничивает."""
    use_case, inventory, fulfilled = make_use_case()
    sku_id = uuid4()
    # Два независимых заказа на один и тот же SKU
    inventory.add_sku(sku_id, active=0, reserved=5)  # 5 единиц в резерве

    order_a, order_b = uuid4(), uuid4()
    await use_case(make_request([(sku_id, 2)], order_id=order_a))
    await use_case(make_request([(sku_id, 3)], order_id=order_b))

    # Оба fulfill применились: reserved_quantity 5 - 2 - 3 = 0
    assert inventory.skus[sku_id]['reserved_quantity'] == 0
    # Журнал содержит обе записи
    assert len(fulfilled.record_calls) == 2
    assert {call[0] for call in fulfilled.record_calls} == {order_a, order_b}


@pytest.mark.anyio
async def test_fulfill_missing_sku_ignored():
    """Несуществующий SKU при fulfill игнорируется (best-effort, аналогично unreserve)."""
    use_case, inventory, fulfilled = make_use_case()
    existing = uuid4()
    missing = uuid4()
    inventory.add_sku(existing, active=7, reserved=3)

    response = await use_case(make_request([(existing, 3), (missing, 1)]))

    assert response.status == "FULFILLED"
    assert inventory.skus[existing]['reserved_quantity'] == 0
    assert missing not in inventory.skus
    # В журнал попадают ОБЕ записи — журнал ведётся независимо от факта существования SKU,
    # это гарантирует идемпотентность повторов (повтор уйдёт мимо, даже если SKU не существует).
    assert len(fulfilled.record_calls) == 2
