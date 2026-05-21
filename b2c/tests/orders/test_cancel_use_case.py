"""US-ORD-03: cancel order use-case tests."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.orders.enums import OrderStatus
from apps.orders.errors import CancelNotAllowedError, OrderNotFoundError
from apps.orders.models import OrderItem
from apps.orders.schemas.db import OrderReadSchema
from apps.orders.use_cases import CancelOrderUseCase
from apps.outbox.enums import OutboxEventType
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from shared.outbox import OutboxStatus
from shared.types import ServiceName
from tests.orders.fakes import (
    FakeB2BInventoryClient,
    FakeOrderItemRepository,
    FakeOrderRepository,
    FakeOutboxRepository,
)


def make_user() -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)


def make_order(user_id, *, status: str = OrderStatus.PAID.value) -> OrderReadSchema:
    now = datetime.now(UTC)
    return OrderReadSchema(
        id=uuid4(),
        user_id=user_id,
        status=status,
        total_amount=20_000,
        idempotency_key=uuid4(),
        delivery_address=None,
        address_id=None,
        payment_method_id=None,
        created_at=now,
        updated_at=now,
    )


def make_item(order_id, sku_id=None, quantity: int = 2, unit_price: int = 10_000) -> OrderItem:
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


def make_use_case():
    order_repo = FakeOrderRepository()
    item_repo = FakeOrderItemRepository(order_repo)
    b2b = FakeB2BInventoryClient()
    outbox = FakeOutboxRepository()
    use_case = CancelOrderUseCase(
        order_repository=order_repo,
        order_item_repository=item_repo,
        b2b_client=b2b,
        outbox_repository=outbox,
    )
    return use_case, order_repo, b2b, outbox


@pytest.mark.anyio
async def test_cancel_paid_order_transitions_to_cancelled():
    use_case, order_repo, b2b, outbox = make_use_case()
    user = make_user()
    order = make_order(user.id, status=OrderStatus.PAID.value)
    item = make_item(order.id, quantity=3, unit_price=5_000)
    order_repo.seed_order(order, [item])

    result = await use_case(order.id, user)

    assert result.status == OrderStatus.CANCELLED.value
    # unreserve вызван с правильным набором items
    assert len(b2b.unreserve_calls) == 1
    assert b2b.unreserve_calls[0]['idempotency_key'] == order.id
    assert b2b.unreserve_calls[0]['items'] == [{'sku_id': str(item.sku_id), 'quantity': 3}]
    # outbox пустой — на happy path не enqueue
    assert outbox.events == []
    # запись в БД обновлена
    saved = order_repo.by_id[order.id]
    assert saved.status == OrderStatus.CANCELLED.value


@pytest.mark.anyio
async def test_cancel_created_order_also_works():
    use_case, order_repo, b2b, _ = make_use_case()
    user = make_user()
    order = make_order(user.id, status=OrderStatus.CREATED.value)
    item = make_item(order.id)
    order_repo.seed_order(order, [item])

    result = await use_case(order.id, user)

    assert result.status == OrderStatus.CANCELLED.value


@pytest.mark.anyio
async def test_unreserve_failure_transitions_to_cancel_pending():
    use_case, order_repo, b2b, outbox = make_use_case()
    user = make_user()
    order = make_order(user.id, status=OrderStatus.PAID.value)
    item = make_item(order.id, quantity=2, unit_price=5_000)
    order_repo.seed_order(order, [item])
    b2b.unreserve_b2b_503 = True  # симуляция падения B2B

    result = await use_case(order.id, user)

    assert result.status == OrderStatus.CANCEL_PENDING.value
    # outbox содержит ровно одно событие UNRESERVE_ORDER → b2b
    assert len(outbox.events) == 1
    enqueued = outbox.events[0]
    assert enqueued.event_type == OutboxEventType.UNRESERVE_ORDER.value
    assert enqueued.target_service == ServiceName.B2B.value
    assert enqueued.status == OutboxStatus.PENDING
    assert enqueued.payload['order_id'] == str(order.id)
    assert enqueued.payload['items'] == [{'sku_id': str(item.sku_id), 'quantity': 2}]


@pytest.mark.anyio
async def test_cancel_assembling_order_succeeds_per_spec():
    """Per spec b2c openapi.yaml: cancel allowed in CREATED/PAID/ASSEMBLING."""
    use_case, order_repo, b2b_client, _ = make_use_case()
    user = make_user()
    order = make_order(user.id, status=OrderStatus.ASSEMBLING.value)
    order_repo.seed_order(order, [make_item(order.id)])

    response = await use_case(order.id, user)
    assert response.status == OrderStatus.CANCELLED.value
    assert len(b2b_client.unreserve_calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    'forbidden_status',
    [
        OrderStatus.DELIVERING.value,
        OrderStatus.DELIVERED.value,
        OrderStatus.CANCELLED.value,
        OrderStatus.CANCEL_PENDING.value,
    ],
)
async def test_cancel_non_cancelable_statuses_all_return_409(forbidden_status):
    use_case, order_repo, _, _ = make_use_case()
    user = make_user()
    order = make_order(user.id, status=forbidden_status)
    order_repo.seed_order(order, [make_item(order.id)])

    with pytest.raises(CancelNotAllowedError):
        await use_case(order.id, user)


@pytest.mark.anyio
async def test_other_user_order_returns_404():
    use_case, order_repo, _, _ = make_use_case()
    user = make_user()
    foreign = make_user()
    order = make_order(foreign.id, status=OrderStatus.PAID.value)
    order_repo.seed_order(order, [make_item(order.id)])

    with pytest.raises(OrderNotFoundError):
        await use_case(order.id, user)


@pytest.mark.anyio
async def test_cancel_nonexistent_order_returns_404():
    use_case, _, _, _ = make_use_case()
    user = make_user()

    with pytest.raises(OrderNotFoundError):
        await use_case(uuid4(), user)
