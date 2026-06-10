"""US-ORD-02: тесты list_orders / get_order use-cases."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from apps.orders.enums import OrderStatus
from apps.orders.errors import OrderNotFoundError
from apps.orders.models import OrderItem
from apps.orders.schemas.db import OrderReadSchema
from apps.orders.use_cases import GetOrderUseCase, ListOrdersUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.orders.fakes import (
    FakeAddressRepository,
    FakeOrderItemRepository,
    FakeOrderRepository,
    FakePaymentMethodRepository,
)


def make_user() -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)


def make_order(
    user_id,
    *,
    status: str = OrderStatus.PAID.value,
    created_at: datetime | None = None,
    total_amount: int = 10_000,
) -> OrderReadSchema:
    now = created_at or datetime.now(UTC)
    return OrderReadSchema(
        id=uuid4(),
        user_id=user_id,
        status=status,
        total_amount=total_amount,
        idempotency_key=uuid4(),
        delivery_address=None,
        address_id=None,
        payment_method_id=None,
        comment=None,
        cancel_reason=None,
        created_at=now,
        updated_at=now,
    )


def make_item(order_id, sku_id=None) -> OrderItem:
    now = datetime.now(UTC)
    im = OrderItem(
        id=uuid4(),
        order_id=order_id,
        sku_id=sku_id or uuid4(),
        product_id=uuid4(),
        product_title='Phone',
        sku_name='128GB',
        quantity=2,
        unit_price=5_000,
        line_total=10_000,
    )
    im.created_at = now  # type: ignore[attr-defined]
    im.updated_at = now  # type: ignore[attr-defined]
    return im


@pytest.mark.anyio
async def test_orders_list_returns_own_orders_paginated():
    repo = FakeOrderRepository()
    user = make_user()
    other = make_user()
    # три собственных + один чужой
    own_orders = [make_order(user.id, created_at=datetime(2026, 5, i, tzinfo=UTC)) for i in (10, 11, 12)]
    foreign = make_order(other.id)
    for o in own_orders + [foreign]:
        repo.seed_order(o, [make_item(o.id)])

    use_case = ListOrdersUseCase(order_repository=repo)
    result = await use_case(user, limit=2, offset=0)

    # пагинация: 2 элемента, total — 3 (только собственные)
    assert result.total_count == 3
    assert len(result.items) == 2
    # сортировка DESC по created_at: первым самый свежий
    assert result.items[0].id == own_orders[2].id
    assert result.items[1].id == own_orders[1].id
    # items_count
    assert result.items[0].items_count == 1
    # offset
    page2 = await use_case(user, limit=2, offset=2)
    assert len(page2.items) == 1
    assert page2.items[0].id == own_orders[0].id


@pytest.mark.anyio
async def test_orders_list_filters_by_status():
    repo = FakeOrderRepository()
    user = make_user()
    paid = make_order(user.id, status=OrderStatus.PAID.value, created_at=datetime(2026, 1, 1, tzinfo=UTC))
    delivered = make_order(user.id, status=OrderStatus.DELIVERED.value, created_at=datetime(2026, 1, 2, tzinfo=UTC))
    repo.seed_order(paid, [])
    repo.seed_order(delivered, [])

    use_case = ListOrdersUseCase(order_repository=repo)
    result = await use_case(user, status=OrderStatus.DELIVERED.value)
    assert {o.id for o in result.items} == {delivered.id}
    assert result.total_count == 1


@pytest.mark.anyio
async def test_orders_list_excludes_other_users_orders():
    repo = FakeOrderRepository()
    user = make_user()
    foreign = make_order(make_user().id)
    repo.seed_order(foreign, [])

    use_case = ListOrdersUseCase(order_repository=repo)
    result = await use_case(user)
    assert result.items == []
    assert result.total_count == 0


@pytest.mark.anyio
async def test_order_detail_shows_fixed_prices():
    repo = FakeOrderRepository()
    user = make_user()
    order = make_order(user.id)
    item = make_item(order.id)
    repo.seed_order(order, [item])

    use_case = GetOrderUseCase(
        order_repository=repo,
        order_item_repository=FakeOrderItemRepository(repo),
        address_repository=FakeAddressRepository(),
        payment_method_repository=FakePaymentMethodRepository(),
    )
    result = await use_case(order.id, user)

    assert result.id == order.id
    assert len(result.items) == 1
    # фиксированные поля проброшены без обращения к B2B (снапшот, не текущий B2B)
    assert result.items[0].name == f'{item.product_title} {item.sku_name}'.strip()
    assert result.items[0].unit_price == item.unit_price
    assert result.items[0].line_total == item.line_total


@pytest.mark.anyio
async def test_other_user_order_returns_404_not_403():
    """IDOR-prevention: чужой заказ возвращает 404, не 403."""
    repo = FakeOrderRepository()
    user = make_user()
    foreign_user = make_user()
    foreign_order = make_order(foreign_user.id)
    repo.seed_order(foreign_order, [make_item(foreign_order.id)])

    use_case = GetOrderUseCase(
        order_repository=repo,
        order_item_repository=FakeOrderItemRepository(repo),
        address_repository=FakeAddressRepository(),
        payment_method_repository=FakePaymentMethodRepository(),
    )
    with pytest.raises(OrderNotFoundError):
        await use_case(foreign_order.id, user)


@pytest.mark.anyio
async def test_get_order_not_found_for_nonexistent_id():
    repo = FakeOrderRepository()
    user = make_user()

    use_case = GetOrderUseCase(
        order_repository=repo,
        order_item_repository=FakeOrderItemRepository(repo),
        address_repository=FakeAddressRepository(),
        payment_method_repository=FakePaymentMethodRepository(),
    )
    with pytest.raises(OrderNotFoundError):
        await use_case(uuid4(), user)


@pytest.mark.anyio
async def test_orders_list_default_limit_offset():
    repo = FakeOrderRepository()
    user = make_user()
    # 25 заказов
    base = datetime(2026, 5, 1, tzinfo=UTC)
    for i in range(25):
        order = make_order(user.id, created_at=base + timedelta(days=i))
        repo.seed_order(order, [make_item(order.id)])

    use_case = ListOrdersUseCase(order_repository=repo)
    result = await use_case(user)
    assert result.limit == 20
    assert result.offset == 0
    assert len(result.items) == 20
    assert result.total_count == 25
