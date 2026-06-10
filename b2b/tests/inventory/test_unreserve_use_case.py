"""Тесты UnreserveInventoryUseCase (US-B2B-08)."""

from uuid import UUID, uuid4

import pytest

from apps.inventory.schemas import (
    InventoryItemRequestSchema,
    UnreserveRequestSchema,
)
from apps.inventory.use_cases import UnreserveInventoryUseCase
from tests.inventory.fakes import (
    FakeInboxRepository,
    FakeInventoryRepository,
    FakeSessionManager,
)


def make_use_case(
    *,
    inventory: FakeInventoryRepository | None = None,
    inbox: FakeInboxRepository | None = None,
) -> tuple[UnreserveInventoryUseCase, FakeInventoryRepository, FakeInboxRepository]:
    inventory_repo = inventory or FakeInventoryRepository()
    inbox_repo = inbox or FakeInboxRepository()
    use_case = UnreserveInventoryUseCase(
        inventory_repository=inventory_repo,  # type: ignore[arg-type]
        inbox_repository=inbox_repo,  # type: ignore[arg-type]
        session_manager=FakeSessionManager(),  # type: ignore[arg-type]
    )
    return use_case, inventory_repo, inbox_repo


def make_request(
    items: list[tuple[UUID, int]] | None = None,
    order_id: UUID | None = None,
) -> UnreserveRequestSchema:
    return UnreserveRequestSchema(
        order_id=order_id or uuid4(),
        items=[InventoryItemRequestSchema(sku_id=sku_id, quantity=qty) for sku_id, qty in (items or [])],
    )


@pytest.mark.anyio
async def test_unreserve_restores_quantities():
    """Unreserve откатывает резервирование: reserved_quantity -= q, active_quantity += q."""
    use_case, inventory, _inbox = make_use_case()
    sku_a, sku_b = uuid4(), uuid4()
    # Имитируем уже зарезервированные SKU
    inventory.add_sku(sku_a, active=7, reserved=3)
    inventory.add_sku(sku_b, active=3, reserved=2)

    order_id = uuid4()
    response = await use_case(make_request([(sku_a, 3), (sku_b, 2)], order_id=order_id))

    # Ответ по спецификации: order_id, status='UNRESERVED', processed_at
    assert response.order_id == order_id
    assert response.status == 'UNRESERVED'
    assert response.processed_at is not None
    # Состояние полностью восстановлено
    assert inventory.skus[sku_a] == {'active_quantity': 10, 'reserved_quantity': 0}
    assert inventory.skus[sku_b] == {'active_quantity': 5, 'reserved_quantity': 0}


@pytest.mark.anyio
async def test_unreserve_idempotent_returns_cached():
    """Повторный unreserve с тем же order_id не повторяет операцию."""
    use_case, inventory, inbox = make_use_case()
    sku_id = uuid4()
    inventory.add_sku(sku_id, active=7, reserved=3)

    order_id = uuid4()
    first = await use_case(make_request([(sku_id, 3)], order_id=order_id))
    assert first.status == 'UNRESERVED'
    assert first.order_id == order_id
    assert inventory.skus[sku_id] == {'active_quantity': 10, 'reserved_quantity': 0}

    # Повторяем — состояние НЕ должно измениться
    second = await use_case(make_request([(sku_id, 3)], order_id=order_id))
    assert second.status == 'UNRESERVED'
    assert second.order_id == order_id
    assert second.processed_at == first.processed_at
    assert inventory.skus[sku_id] == {'active_quantity': 10, 'reserved_quantity': 0}
    # Реальный вызов unreserve был только один
    assert len(inventory.unreserve_calls) == 1
    # processed_event один
    assert len(inbox.records) == 1


@pytest.mark.anyio
async def test_unreserve_missing_sku_ignored():
    """Несуществующий SKU при unreserve — игнорируется (best-effort компенсация).

    Не должны крашиться: канон не требует ошибку для этого случая.
    """
    use_case, inventory, _inbox = make_use_case()
    existing = uuid4()
    missing = uuid4()
    inventory.add_sku(existing, active=7, reserved=3)

    response = await use_case(make_request([(existing, 3), (missing, 1)]))

    assert response.status == 'UNRESERVED'
    assert inventory.skus[existing] == {'active_quantity': 10, 'reserved_quantity': 0}
    assert missing not in inventory.skus
