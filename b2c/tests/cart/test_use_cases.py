"""Unit-тесты cart use cases — bog-standard fakes без httpx.

DoD-тесты (exact names):
- test_add_sku_increments_quantity_if_already_in_cart
- test_get_cart_enriched_with_b2b_data
- test_unavailable_sku_shown_with_reason
- test_guest_cart_merged_on_login
"""

from typing import Any
from uuid import UUID, uuid4

import pytest

from apps.cart.enums import UnavailableReason
from apps.cart.errors import CartItemNotFoundError
from apps.cart.schemas.db import CartCreateSchema, CartItemCreateSchema
from apps.cart.schemas.request import CartItemAddRequestSchema, CartItemUpdateRequestSchema
from apps.cart.use_cases import (
    AddItemUseCase,
    GetCartUseCase,
    MergeCartUseCase,
    RemoveItemUseCase,
    UpdateItemUseCase,
)
from tests.cart.fakes import FakeCartItemRepository, FakeCartRepository


class StubB2BClient:
    """Заменяет shared.http_clients.ServiceClient в тестах.

    Возвращает фиксированный payload как из B2B GET /api/v1/skus?ids=...
    """

    def __init__(self, items: list[dict[str, Any]] | None = None):
        self.items = items or []
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((path, params))
        return {'items': self.items}


# --------------- ADD ITEM ---------------


@pytest.mark.anyio
async def test_add_sku_increments_quantity_if_already_in_cart():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    use_case = AddItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)

    user_id = uuid4()
    sku_id = uuid4()

    first = await use_case(
        CartItemAddRequestSchema(sku_id=sku_id, quantity=2),
        user_id=user_id,
        session_id=None,
    )
    assert first.created is True
    assert first.item.quantity == 2

    second = await use_case(
        CartItemAddRequestSchema(sku_id=sku_id, quantity=3),
        user_id=user_id,
        session_id=None,
    )

    assert second.created is False
    assert second.item.id == first.item.id
    assert second.item.quantity == 5  # 2 + 3
    # Корзина создавалась только один раз
    assert len(cart_repo.created) == 1
    # Один item в корзине, не два
    items = await item_repo.list_by_cart(first.item.cart_id)
    assert len(items) == 1


@pytest.mark.anyio
async def test_add_sku_creates_cart_for_guest_session():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    use_case = AddItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)

    session_id = str(uuid4())

    result = await use_case(
        CartItemAddRequestSchema(sku_id=uuid4(), quantity=1),
        user_id=None,
        session_id=session_id,
    )

    assert result.created is True
    assert cart_repo.created[0].session_id == session_id
    assert cart_repo.created[0].user_id is None


@pytest.mark.anyio
async def test_add_sku_reuses_existing_cart():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    existing = await cart_repo.create(_cart_create_schema(user_id=user_id))
    use_case = AddItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)

    result = await use_case(
        CartItemAddRequestSchema(sku_id=uuid4(), quantity=1),
        user_id=user_id,
        session_id=None,
    )

    assert result.item.cart_id == existing.id
    assert len(cart_repo.by_id) == 1


# --------------- UPDATE ITEM ---------------


@pytest.mark.anyio
async def test_update_item_changes_quantity():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))
    sku_id = uuid4()
    item = await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_id, quantity=2))

    use_case = UpdateItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)
    result = await use_case(
        sku_id,  # spec: path is sku_id, not item.id
        CartItemUpdateRequestSchema(quantity=5),
        user_id=user_id,
        session_id=None,
    )

    assert result.id == item.id
    assert result.quantity == 5


@pytest.mark.anyio
async def test_update_item_rejects_foreign_cart():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    foreign_user = uuid4()
    foreign_cart = await cart_repo.create(_cart_create_schema(user_id=foreign_user))
    foreign_sku = uuid4()
    await item_repo.create(CartItemCreateSchema(cart_id=foreign_cart.id, sku_id=foreign_sku, quantity=1))

    use_case = UpdateItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)

    with pytest.raises(CartItemNotFoundError):
        await use_case(
            foreign_sku,
            CartItemUpdateRequestSchema(quantity=5),
            user_id=uuid4(),  # другой user — нет своей корзины с этим sku
            session_id=None,
        )


# --------------- REMOVE ITEM ---------------


@pytest.mark.anyio
async def test_remove_item_deletes_owned_item():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))
    sku_id = uuid4()
    item = await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_id, quantity=1))

    use_case = RemoveItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)
    await use_case(sku_id, user_id=user_id, session_id=None)

    assert item.id not in item_repo.by_id


@pytest.mark.anyio
async def test_remove_item_rejects_foreign_cart():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    foreign_user = uuid4()
    foreign_cart = await cart_repo.create(_cart_create_schema(user_id=foreign_user))
    foreign_sku = uuid4()
    foreign_item = await item_repo.create(
        CartItemCreateSchema(cart_id=foreign_cart.id, sku_id=foreign_sku, quantity=1)
    )

    use_case = RemoveItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)

    with pytest.raises(CartItemNotFoundError):
        await use_case(foreign_sku, user_id=uuid4(), session_id=None)

    assert foreign_item.id in item_repo.by_id


# --------------- GET CART (B2B enrichment) ---------------


@pytest.mark.anyio
async def test_get_cart_enriched_with_b2b_data():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))

    sku_a = uuid4()
    sku_b = uuid4()
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_a, quantity=2))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_b, quantity=3))

    b2b_client = StubB2BClient(
        items=[
            {'id': str(sku_a), 'title': 'Nike Air Max 42', 'price': 1000, 'available_quantity': 10},
            {'id': str(sku_b), 'title': 'Adidas Boost L', 'price': 2500, 'available_quantity': 5},
        ]
    )

    use_case = GetCartUseCase(
        cart_repository=cart_repo,
        cart_item_repository=item_repo,
        b2b_client=b2b_client,
    )
    result = await use_case(user_id=user_id, session_id=None)

    by_sku = {item.sku_id: item for item in result.items}
    assert by_sku[sku_a].title == 'Nike Air Max 42'
    assert by_sku[sku_a].unit_price == 1000
    assert by_sku[sku_a].available_quantity == 10
    assert by_sku[sku_a].line_total == 2000  # 1000 * 2
    assert by_sku[sku_a].unavailable_reason is None

    assert by_sku[sku_b].line_total == 7500  # 2500 * 3
    assert result.items_count == 5  # 2 + 3
    assert result.total_amount == 9500  # 2000 + 7500
    # Дёрнули B2B один раз
    assert len(b2b_client.calls) == 1
    assert b2b_client.calls[0][0] == '/api/v1/skus'


@pytest.mark.anyio
async def test_unavailable_sku_shown_with_reason():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))

    sku_ok = uuid4()
    sku_blocked = uuid4()
    sku_out = uuid4()
    sku_deleted = uuid4()  # отсутствует в B2B-ответе → DELETED

    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_ok, quantity=2))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_blocked, quantity=1))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_out, quantity=1))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_deleted, quantity=4))

    b2b_client = StubB2BClient(
        items=[
            {'id': str(sku_ok), 'title': 'OK', 'price': 500, 'available_quantity': 10},
            {'id': str(sku_blocked), 'title': 'Blocked', 'price': 700, 'available_quantity': 5, 'blocked': True},
            {'id': str(sku_out), 'title': 'OutOfStock', 'price': 800, 'available_quantity': 0},
        ]
    )

    use_case = GetCartUseCase(
        cart_repository=cart_repo,
        cart_item_repository=item_repo,
        b2b_client=b2b_client,
    )
    result = await use_case(user_id=user_id, session_id=None)

    by_sku = {item.sku_id: item for item in result.items}
    assert by_sku[sku_ok].unavailable_reason is None
    assert by_sku[sku_blocked].unavailable_reason == UnavailableReason.BLOCKED
    assert by_sku[sku_out].unavailable_reason == UnavailableReason.OUT_OF_STOCK
    assert by_sku[sku_deleted].unavailable_reason == UnavailableReason.DELETED

    # Все 4 позиции вернулись, но total_amount = только available
    assert len(result.items) == 4
    assert by_sku[sku_blocked].line_total == 0
    assert by_sku[sku_out].line_total == 0
    assert by_sku[sku_deleted].line_total == 0
    assert result.total_amount == 1000  # 500 * 2


@pytest.mark.anyio
async def test_get_cart_returns_empty_when_no_cart():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    b2b_client = StubB2BClient()
    use_case = GetCartUseCase(
        cart_repository=cart_repo,
        cart_item_repository=item_repo,
        b2b_client=b2b_client,
    )

    result = await use_case(user_id=uuid4(), session_id=None)

    assert result.items == []
    assert result.total_amount == 0
    assert result.items_count == 0
    # Не дёргали B2B, ибо нет items
    assert b2b_client.calls == []


@pytest.mark.anyio
async def test_get_cart_does_not_call_b2b_for_empty_cart():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    await cart_repo.create(_cart_create_schema(user_id=user_id))
    b2b_client = StubB2BClient()

    use_case = GetCartUseCase(
        cart_repository=cart_repo,
        cart_item_repository=item_repo,
        b2b_client=b2b_client,
    )
    result = await use_case(user_id=user_id, session_id=None)

    assert result.items == []
    assert b2b_client.calls == []


# --------------- MERGE CART ---------------


@pytest.mark.anyio
async def test_guest_cart_merged_on_login():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()

    user_id = uuid4()
    session_id = str(uuid4())

    # Auth-корзина: SKU-1 c qty=2, SKU-2 c qty=5
    auth_cart = await cart_repo.create(_cart_create_schema(user_id=user_id))
    sku_shared = uuid4()
    sku_auth_only = uuid4()
    await item_repo.create(CartItemCreateSchema(cart_id=auth_cart.id, sku_id=sku_shared, quantity=2))
    await item_repo.create(CartItemCreateSchema(cart_id=auth_cart.id, sku_id=sku_auth_only, quantity=5))

    # Гостевая: SKU-1 c qty=7 (больше — выиграет), SKU-3 (нет в auth)
    guest_cart = await cart_repo.create(_cart_create_schema(session_id=session_id))
    sku_guest_only = uuid4()
    await item_repo.create(CartItemCreateSchema(cart_id=guest_cart.id, sku_id=sku_shared, quantity=7))
    await item_repo.create(CartItemCreateSchema(cart_id=guest_cart.id, sku_id=sku_guest_only, quantity=1))

    use_case = MergeCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)
    await use_case(user_id=user_id, session_id=session_id)

    # Гостевая корзина удалена
    assert await cart_repo.get_by_session(session_id) is None
    assert session_id in cart_repo.deleted_by_session

    # Auth-корзина теперь содержит 3 SKU
    auth_items = await item_repo.list_by_cart(auth_cart.id)
    by_sku = {item.sku_id: item.quantity for item in auth_items}
    assert by_sku[sku_shared] == 7  # MAX(2, 7)
    assert by_sku[sku_auth_only] == 5  # не тронут
    assert by_sku[sku_guest_only] == 1  # перенесён


@pytest.mark.anyio
async def test_merge_creates_auth_cart_if_missing():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    session_id = str(uuid4())

    guest_cart = await cart_repo.create(_cart_create_schema(session_id=session_id))
    sku = uuid4()
    await item_repo.create(CartItemCreateSchema(cart_id=guest_cart.id, sku_id=sku, quantity=3))

    use_case = MergeCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)
    await use_case(user_id=user_id, session_id=session_id)

    auth_cart = await cart_repo.get_by_user(user_id)
    assert auth_cart is not None
    items = await item_repo.list_by_cart(auth_cart.id)
    assert len(items) == 1
    assert items[0].sku_id == sku
    assert items[0].quantity == 3
    assert await cart_repo.get_by_session(session_id) is None


@pytest.mark.anyio
async def test_merge_noop_when_no_guest_cart():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    session_id = str(uuid4())

    use_case = MergeCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)
    await use_case(user_id=user_id, session_id=session_id)

    # Создалась пустая auth-корзина, гостевой никогда не существовало
    auth_cart = await cart_repo.get_by_user(user_id)
    assert auth_cart is not None
    items = await item_repo.list_by_cart(auth_cart.id)
    assert items == []


@pytest.mark.anyio
async def test_merge_picks_auth_quantity_when_higher():
    """MAX выигрывает у guest-корзины даже когда у auth больше."""
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    session_id = str(uuid4())

    auth_cart = await cart_repo.create(_cart_create_schema(user_id=user_id))
    sku = uuid4()
    await item_repo.create(CartItemCreateSchema(cart_id=auth_cart.id, sku_id=sku, quantity=10))

    guest_cart = await cart_repo.create(_cart_create_schema(session_id=session_id))
    await item_repo.create(CartItemCreateSchema(cart_id=guest_cart.id, sku_id=sku, quantity=2))

    use_case = MergeCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)
    await use_case(user_id=user_id, session_id=session_id)

    items = await item_repo.list_by_cart(auth_cart.id)
    assert len(items) == 1
    assert items[0].quantity == 10  # MAX(10, 2)


# --------------- helpers ---------------


def _cart_create_schema(user_id: UUID | None = None, session_id: str | None = None):
    return CartCreateSchema(user_id=user_id, session_id=session_id)
