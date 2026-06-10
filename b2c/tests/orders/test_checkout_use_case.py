from uuid import uuid4

import pytest

from apps.orders.enums import OrderStatus
from apps.orders.errors import (
    B2BUnavailableError,
    CartInvalidError,
    InvalidAddressError,
    ReserveFailedError,
)
from apps.orders.schemas.request import OrderCreateRequestSchema, OrderItemSnapshotSchema
from apps.orders.use_cases import CheckoutUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.orders.fakes import (
    FakeAddressRepository,
    FakeB2BInventoryClient,
    FakeCartItemRepository,
    FakeCartRepository,
    FakeOrderItemRepository,
    FakeOrderRepository,
    FakePaymentMethodRepository,
    make_address,
    make_cart,
    make_cart_item,
    make_payment_method,
    make_sku_entry,
)


class _Harness:
    def __init__(self):
        self.order_repo = FakeOrderRepository()
        self.item_repo = FakeOrderItemRepository(self.order_repo)
        self.b2b = FakeB2BInventoryClient()
        self.cart_repo = FakeCartRepository()
        self.cart_item_repo = FakeCartItemRepository()
        self.address_repo = FakeAddressRepository()
        self.payment_repo = FakePaymentMethodRepository()
        self.use_case = CheckoutUseCase(
            order_repository=self.order_repo,
            order_item_repository=self.item_repo,
            b2b_client=self.b2b,
            cart_repository=self.cart_repo,
            cart_item_repository=self.cart_item_repo,
            address_repository=self.address_repo,
            payment_method_repository=self.payment_repo,
        )
        self.buyer = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
        self.cart = make_cart(user_id=self.buyer.id)
        self.cart_repo.seed(self.cart)
        self.address = make_address(buyer_id=self.buyer.id)
        self.address_repo.seed(self.address)
        self.payment = make_payment_method(buyer_id=self.buyer.id)
        self.payment_repo.seed(self.payment)

    def seed_cart_items(self, *entries):
        """entries: (sku_id, sku_raw, quantity). Seeds B2B index + cart items."""
        items = []
        for sku_id, raw, qty in entries:
            self.b2b.sku_index[sku_id] = raw
            items.append(
                make_cart_item(cart_id=self.cart.id, sku_id=sku_id, product_id=raw['product_id'], quantity=qty)
            )
        self.cart_item_repo.seed(self.cart.id, items)

    def request(self, **overrides) -> OrderCreateRequestSchema:
        base = {'address_id': self.address.id, 'payment_method_id': self.payment.id}
        base.update(overrides)
        return OrderCreateRequestSchema(**base)


@pytest.mark.anyio
async def test_checkout_creates_paid_order_with_fixed_prices():
    h = _Harness()
    sku_a, raw_a = make_sku_entry(product_title='Phone A', sku_name='128GB', price=10_000)
    sku_b, raw_b = make_sku_entry(product_title='Phone B', sku_name='256GB', price=25_000)
    h.seed_cart_items((sku_a, raw_a, 2), (sku_b, raw_b, 1))

    key = uuid4()
    response, created = await h.use_case(idempotency_key=key, data=h.request(), current_user=h.buyer)

    assert created is True
    assert response.status == OrderStatus.PAID.value
    assert response.subtotal == 2 * 10_000 + 1 * 25_000
    assert response.total == response.subtotal
    items_by_sku = {it.sku_id: it for it in response.items}
    assert items_by_sku[sku_a].unit_price == 10_000
    assert items_by_sku[sku_a].line_total == 20_000
    assert items_by_sku[sku_a].name == 'Phone A 128GB'
    assert items_by_sku[sku_b].unit_price == 25_000

    # OrderItem snapshot persisted: product_title / sku_name on the DB model.
    saved_items = h.order_repo.items_by_order[response.id]
    saved_by_sku = {it.sku_id: it for it in saved_items}
    assert saved_by_sku[sku_a].product_title == 'Phone A'
    assert saved_by_sku[sku_a].sku_name == '128GB'
    assert saved_by_sku[sku_a].unit_price == 10_000

    # reserve called exactly once with order_id == created order id.
    assert len(h.b2b.reserve_calls) == 1
    assert h.b2b.reserve_calls[0]['idempotency_key'] == key
    assert h.b2b.reserve_calls[0]['order_id'] == response.id
    saved = h.order_repo.by_id[response.id]
    assert saved.user_id == h.buyer.id


@pytest.mark.anyio
async def test_partial_reserve_failure_returns_409():
    h = _Harness()
    sku, raw = make_sku_entry()
    h.seed_cart_items((sku, raw, 5))
    h.b2b.reserve_failed_items = [
        {'sku_id': str(sku), 'requested': 5, 'available': 1, 'reason': 'INSUFFICIENT_STOCK'},
    ]

    with pytest.raises(ReserveFailedError) as err:
        await h.use_case(idempotency_key=uuid4(), data=h.request(), current_user=h.buyer)

    assert err.value.status_code == 409
    assert err.value.code == 'RESERVE_FAILED'
    assert err.value.failed_items[0]['reason'] == 'INSUFFICIENT_STOCK'
    # All-or-nothing: no order persisted.
    assert h.order_repo.by_id == {}
    assert h.order_repo.create_calls == []


@pytest.mark.anyio
async def test_idempotency_returns_existing_order():
    h = _Harness()
    sku, raw = make_sku_entry()
    h.seed_cart_items((sku, raw, 1))
    key = uuid4()

    response1, created1 = await h.use_case(idempotency_key=key, data=h.request(), current_user=h.buyer)
    response2, created2 = await h.use_case(idempotency_key=key, data=h.request(), current_user=h.buyer)

    assert created1 is True
    assert created2 is False
    assert response1.id == response2.id
    # reserve called exactly once — replay does not hit B2B again.
    assert len(h.b2b.reserve_calls) == 1
    # exactly one order in the repo.
    assert len(h.order_repo.by_id) == 1


@pytest.mark.anyio
async def test_b2b_unavailable_returns_503():
    h = _Harness()
    sku, raw = make_sku_entry()
    h.seed_cart_items((sku, raw, 1))
    h.b2b.b2b_503 = True

    with pytest.raises(B2BUnavailableError) as err:
        await h.use_case(idempotency_key=uuid4(), data=h.request(), current_user=h.buyer)
    assert err.value.status_code == 503
    assert h.order_repo.by_id == {}


@pytest.mark.anyio
async def test_empty_cart_returns_422():
    h = _Harness()  # no cart items seeded

    with pytest.raises(CartInvalidError) as err:
        await h.use_case(idempotency_key=uuid4(), data=h.request(), current_user=h.buyer)
    assert err.value.status_code == 422
    assert err.value.code == 'CART_INVALID'
    assert len(h.b2b.reserve_calls) == 0


@pytest.mark.anyio
async def test_unavailable_sku_returns_422_no_reserve():
    h = _Harness()
    sku, raw = make_sku_entry(active_quantity=1)
    h.seed_cart_items((sku, raw, 5))  # requested 5 > available 1

    with pytest.raises(CartInvalidError) as err:
        await h.use_case(idempotency_key=uuid4(), data=h.request(), current_user=h.buyer)
    assert err.value.status_code == 422
    assert err.value.issues[0]['sku_id'] == str(sku)
    # Validation happens before reserve.
    assert len(h.b2b.reserve_calls) == 0


@pytest.mark.anyio
async def test_missing_product_in_batch_returns_422():
    h = _Harness()
    sku = uuid4()
    product_id = uuid4()
    # Cart item exists but B2B batch returns nothing for it (deleted/invisible).
    items = [make_cart_item(cart_id=h.cart.id, sku_id=sku, product_id=product_id, quantity=1)]
    h.cart_item_repo.seed(h.cart.id, items)

    with pytest.raises(CartInvalidError) as err:
        await h.use_case(idempotency_key=uuid4(), data=h.request(), current_user=h.buyer)
    assert err.value.issues[0]['type'] == 'PRODUCT_DELETED'


@pytest.mark.anyio
async def test_foreign_address_returns_400_after_reserve():
    h = _Harness()
    sku, raw = make_sku_entry()
    h.seed_cart_items((sku, raw, 1))
    foreign_address = make_address(buyer_id=uuid4())  # owned by someone else
    h.address_repo.seed(foreign_address)

    with pytest.raises(InvalidAddressError) as err:
        await h.use_case(
            idempotency_key=uuid4(),
            data=h.request(address_id=foreign_address.id),
            current_user=h.buyer,
        )
    assert err.value.status_code == 400
    assert err.value.code == 'INVALID_ADDRESS'
    # No order persisted (address check fails before create).
    assert h.order_repo.by_id == {}


@pytest.mark.anyio
async def test_missing_address_returns_400():
    h = _Harness()
    sku, raw = make_sku_entry()
    h.seed_cart_items((sku, raw, 1))

    with pytest.raises(InvalidAddressError):
        await h.use_case(
            idempotency_key=uuid4(),
            data=h.request(address_id=uuid4()),  # unknown address
            current_user=h.buyer,
        )


@pytest.mark.anyio
async def test_items_snapshot_mismatch_returns_422():
    h = _Harness()
    sku, raw = make_sku_entry(price=10_000)
    h.seed_cart_items((sku, raw, 2))
    # Snapshot disagrees on unit_price → 422.
    snapshot = [OrderItemSnapshotSchema(sku_id=sku, quantity=2, unit_price=9_000)]

    with pytest.raises(CartInvalidError) as err:
        await h.use_case(
            idempotency_key=uuid4(),
            data=h.request(items_snapshot=snapshot),
            current_user=h.buyer,
        )
    assert err.value.status_code == 422
    assert len(h.b2b.reserve_calls) == 0


@pytest.mark.anyio
async def test_items_snapshot_match_succeeds():
    h = _Harness()
    sku, raw = make_sku_entry(price=10_000)
    h.seed_cart_items((sku, raw, 2))
    snapshot = [OrderItemSnapshotSchema(sku_id=sku, quantity=2, unit_price=10_000)]

    response, created = await h.use_case(
        idempotency_key=uuid4(),
        data=h.request(items_snapshot=snapshot),
        current_user=h.buyer,
    )
    assert created is True
    assert response.total == 20_000


@pytest.mark.anyio
async def test_checkout_user_id_from_jwt_not_request():
    """IDOR: user_id берётся из current_user, корзина — пользователя из JWT."""
    h = _Harness()
    sku, raw = make_sku_entry()
    h.seed_cart_items((sku, raw, 1))

    response, _ = await h.use_case(idempotency_key=uuid4(), data=h.request(), current_user=h.buyer)

    saved = h.order_repo.by_id[response.id]
    assert saved.user_id == h.buyer.id
    assert response.buyer_id == h.buyer.id
