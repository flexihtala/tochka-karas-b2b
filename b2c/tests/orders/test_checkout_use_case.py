from uuid import uuid4

import pytest

from apps.orders.enums import OrderStatus
from apps.orders.errors import B2BUnavailableError, ReserveFailedError
from apps.orders.schemas.request import CheckoutItemRequestSchema, CheckoutRequestSchema
from apps.orders.use_cases import CheckoutUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.orders.fakes import (
    FakeB2BInventoryClient,
    FakeOrderItemRepository,
    FakeOrderRepository,
    make_sku_payload,
)


def make_buyer() -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)


def make_use_case() -> tuple[CheckoutUseCase, FakeOrderRepository, FakeB2BInventoryClient]:
    order_repo = FakeOrderRepository()
    item_repo = FakeOrderItemRepository(order_repo)
    b2b = FakeB2BInventoryClient()
    use_case = CheckoutUseCase(order_repository=order_repo, order_item_repository=item_repo, b2b_client=b2b)
    return use_case, order_repo, b2b


@pytest.mark.anyio
async def test_checkout_creates_paid_order_with_fixed_prices():
    use_case, order_repo, b2b = make_use_case()
    sku_a, payload_a = make_sku_payload(product_title='Phone A', sku_name='128GB', price=10_000)
    sku_b, payload_b = make_sku_payload(product_title='Phone B', sku_name='256GB', price=25_000)
    b2b.sku_info = {sku_a: payload_a, sku_b: payload_b}

    buyer = make_buyer()
    request = CheckoutRequestSchema(
        idempotency_key=uuid4(),
        items=[
            CheckoutItemRequestSchema(sku_id=sku_a, quantity=2),
            CheckoutItemRequestSchema(sku_id=sku_b, quantity=1),
        ],
    )

    response, created = await use_case(request, buyer)

    assert created is True
    assert response.status == OrderStatus.PAID.value
    assert response.total_amount == 2 * 10_000 + 1 * 25_000
    assert len(response.items) == 2
    items_by_sku = {it.sku_id: it for it in response.items}
    assert items_by_sku[sku_a].unit_price == 10_000
    assert items_by_sku[sku_a].product_title == 'Phone A'
    assert items_by_sku[sku_a].sku_name == '128GB'
    assert items_by_sku[sku_a].line_total == 20_000
    assert items_by_sku[sku_b].unit_price == 25_000
    # reserve вызван ровно один раз с тем же idempotency_key
    assert len(b2b.reserve_calls) == 1
    assert b2b.reserve_calls[0]['idempotency_key'] == request.idempotency_key
    # сохранены под текущим user_id
    saved = list(order_repo.by_id.values())[0]
    assert saved.user_id == buyer.id


@pytest.mark.anyio
async def test_partial_reserve_failure_returns_409():
    use_case, _, b2b = make_use_case()
    sku, payload = make_sku_payload()
    b2b.sku_info = {sku: payload}
    b2b.reserve_failed_items = [
        {'sku_id': str(sku), 'requested': 5, 'available': 1, 'reason': 'INSUFFICIENT_STOCK'},
    ]

    buyer = make_buyer()
    request = CheckoutRequestSchema(
        idempotency_key=uuid4(),
        items=[CheckoutItemRequestSchema(sku_id=sku, quantity=5)],
    )

    with pytest.raises(ReserveFailedError) as err:
        await use_case(request, buyer)
    assert err.value.failed_items[0]['reason'] == 'INSUFFICIENT_STOCK'


@pytest.mark.anyio
async def test_idempotency_returns_existing_order():
    use_case, order_repo, b2b = make_use_case()
    sku, payload = make_sku_payload()
    b2b.sku_info = {sku: payload}

    buyer = make_buyer()
    request = CheckoutRequestSchema(
        idempotency_key=uuid4(),
        items=[CheckoutItemRequestSchema(sku_id=sku, quantity=1)],
    )

    response1, created1 = await use_case(request, buyer)
    response2, created2 = await use_case(request, buyer)

    assert created1 is True
    assert created2 is False
    assert response1.id == response2.id
    # reserve вызван ровно один раз — повторный checkout не дёргает B2B
    assert len(b2b.reserve_calls) == 1


@pytest.mark.anyio
async def test_b2b_unavailable_returns_503():
    use_case, _, b2b = make_use_case()
    sku, payload = make_sku_payload()
    b2b.sku_info = {sku: payload}
    b2b.b2b_503 = True

    buyer = make_buyer()
    request = CheckoutRequestSchema(
        idempotency_key=uuid4(),
        items=[CheckoutItemRequestSchema(sku_id=sku, quantity=1)],
    )

    with pytest.raises(B2BUnavailableError):
        await use_case(request, buyer)


@pytest.mark.anyio
async def test_missing_sku_returns_409_with_reason_sku_not_found():
    use_case, _, b2b = make_use_case()
    # b2b ничего не знает про этот sku — пустой sku_info
    buyer = make_buyer()
    sku = uuid4()
    request = CheckoutRequestSchema(
        idempotency_key=uuid4(),
        items=[CheckoutItemRequestSchema(sku_id=sku, quantity=1)],
    )

    with pytest.raises(ReserveFailedError) as err:
        await use_case(request, buyer)
    assert err.value.failed_items[0]['sku_id'] == str(sku)
    assert err.value.failed_items[0]['reason'] == 'SKU_NOT_FOUND'


@pytest.mark.anyio
async def test_checkout_user_id_from_jwt_not_request():
    """Проверяем защиту от IDOR: user_id берётся из current_user, не из тела/query."""
    use_case, order_repo, b2b = make_use_case()
    sku, payload = make_sku_payload()
    b2b.sku_info = {sku: payload}

    buyer = make_buyer()
    request = CheckoutRequestSchema(
        idempotency_key=uuid4(),
        items=[CheckoutItemRequestSchema(sku_id=sku, quantity=1)],
    )
    await use_case(request, buyer)

    saved = next(iter(order_repo.by_id.values()))
    assert saved.user_id == buyer.id
