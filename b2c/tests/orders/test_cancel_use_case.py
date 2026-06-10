from uuid import uuid4

import pytest

from apps.orders.enums import OrderStatus
from apps.orders.errors import CancelNotAllowedError, OrderNotFoundError
from apps.orders.use_cases import CancelOrderUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.orders.fakes import (
    FakeAddressRepository,
    FakeB2BInventoryClient,
    FakeOrderItemRepository,
    FakeOrderRepository,
    FakePaymentMethodRepository,
    make_address,
    make_order,
    make_order_item,
    make_payment_method,
)


class _Harness:
    def __init__(self):
        self.order_repo = FakeOrderRepository()
        self.item_repo = FakeOrderItemRepository(self.order_repo)
        self.b2b = FakeB2BInventoryClient()
        self.address_repo = FakeAddressRepository()
        self.payment_repo = FakePaymentMethodRepository()
        self.use_case = CancelOrderUseCase(
            order_repository=self.order_repo,
            order_item_repository=self.item_repo,
            b2b_client=self.b2b,
            address_repository=self.address_repo,
            payment_method_repository=self.payment_repo,
        )
        self.buyer = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
        self.address = make_address(buyer_id=self.buyer.id)
        self.address_repo.seed(self.address)
        self.payment = make_payment_method(buyer_id=self.buyer.id)
        self.payment_repo.seed(self.payment)

    def seed_order(self, *, status: str, owner_id=None, cancel_reason=None, quantity: int = 2):
        owner = owner_id or self.buyer.id
        order = make_order(
            user_id=owner,
            status=status,
            address_id=self.address.id,
            payment_method_id=self.payment.id,
            cancel_reason=cancel_reason,
        )
        item = make_order_item(order_id=order.id, quantity=quantity, unit_price=10_000)
        self.order_repo.seed_order(order, [item])
        return order, item


@pytest.mark.anyio
async def test_cancel_paid_order_transitions_to_cancelled():
    h = _Harness()
    order, item = h.seed_order(status=OrderStatus.PAID.value, quantity=3)

    response = await h.use_case(order.id, h.buyer)

    assert response.status == OrderStatus.CANCELLED.value
    assert response.id == order.id
    # B2B unreserve called once with order_id + items snapshot.
    assert len(h.b2b.unreserve_calls) == 1
    call = h.b2b.unreserve_calls[0]
    assert call['order_id'] == order.id
    assert call['items'] == [{'sku_id': str(item.sku_id), 'quantity': 3}]
    # Persisted as CANCELLED.
    assert h.order_repo.by_id[order.id].status == OrderStatus.CANCELLED.value


@pytest.mark.anyio
async def test_unreserve_failure_transitions_to_cancel_pending():
    h = _Harness()
    order, _ = h.seed_order(status=OrderStatus.PAID.value)
    h.b2b.unreserve_503 = True  # B2B unavailable / 5xx / timeout

    response = await h.use_case(order.id, h.buyer)

    # 200 with CANCEL_PENDING — NOT an error.
    assert response.status == OrderStatus.CANCEL_PENDING.value
    assert len(h.b2b.unreserve_calls) == 1
    # Persisted as CANCEL_PENDING (scaffold: left for async retry).
    assert h.order_repo.by_id[order.id].status == OrderStatus.CANCEL_PENDING.value


@pytest.mark.anyio
async def test_cancel_assembling_order_returns_409():
    h = _Harness()
    order, _ = h.seed_order(status=OrderStatus.ASSEMBLING.value)

    with pytest.raises(CancelNotAllowedError) as err:
        await h.use_case(order.id, h.buyer)

    assert err.value.status_code == 409
    assert err.value.code == 'CANCEL_NOT_ALLOWED'
    assert err.value.current_status == 'ASSEMBLING'
    # B2B unreserve NOT called when status is not cancelable.
    assert len(h.b2b.unreserve_calls) == 0
    # Order untouched.
    assert h.order_repo.by_id[order.id].status == OrderStatus.ASSEMBLING.value


@pytest.mark.anyio
async def test_other_user_order_returns_404():
    h = _Harness()
    order, _ = h.seed_order(status=OrderStatus.PAID.value, owner_id=uuid4())  # owned by someone else

    with pytest.raises(OrderNotFoundError) as err:
        await h.use_case(order.id, h.buyer)

    assert err.value.status_code == 404
    assert err.value.code == 'ORDER_NOT_FOUND'
    # B2B not called for a foreign order.
    assert len(h.b2b.unreserve_calls) == 0


@pytest.mark.anyio
async def test_cancel_created_order_transitions_to_cancelled():
    h = _Harness()
    order, _ = h.seed_order(status=OrderStatus.CREATED.value)

    response = await h.use_case(order.id, h.buyer)

    assert response.status == OrderStatus.CANCELLED.value
    assert len(h.b2b.unreserve_calls) == 1
    assert h.order_repo.by_id[order.id].status == OrderStatus.CANCELLED.value


@pytest.mark.anyio
async def test_cancel_reason_persisted_and_surfaced_in_response():
    h = _Harness()
    order, _ = h.seed_order(status=OrderStatus.PAID.value)

    response = await h.use_case(order.id, h.buyer, reason='changed my mind')

    assert response.cancel_reason == 'changed my mind'
    # reason persisted on the order (survives in GET / replay).
    assert h.order_repo.by_id[order.id].cancel_reason == 'changed my mind'


@pytest.mark.anyio
async def test_cancel_reason_persisted_even_on_cancel_pending():
    h = _Harness()
    order, _ = h.seed_order(status=OrderStatus.PAID.value)
    h.b2b.unreserve_503 = True

    response = await h.use_case(order.id, h.buyer, reason='duplicate order')

    assert response.status == OrderStatus.CANCEL_PENDING.value
    assert response.cancel_reason == 'duplicate order'
    assert h.order_repo.by_id[order.id].cancel_reason == 'duplicate order'


@pytest.mark.anyio
async def test_missing_order_returns_404():
    h = _Harness()

    with pytest.raises(OrderNotFoundError):
        await h.use_case(uuid4(), h.buyer)

    assert len(h.b2b.unreserve_calls) == 0
