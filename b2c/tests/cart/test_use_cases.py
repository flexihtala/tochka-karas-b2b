"""Unit-тесты cart use cases на РЕАЛЬНОМ B2B-контракте через FakeB2BClient.

Мокается только HTTP-граница (get/post витрины), не бизнес-логика корзины.

DoD-тесты (exact names — reviewer greps):
- test_add_sku_increments_quantity_if_already_in_cart
- test_get_cart_enriched_with_b2b_data
- test_unavailable_sku_shown_with_reason
- test_guest_cart_merged_on_login
"""

from uuid import UUID, uuid4

import pytest

from apps.cart.enums import CartValidationIssueType, UnavailableReason
from apps.cart.errors import (
    CartItemNotFoundError,
    InsufficientStockError,
    SkuUnavailableError,
)
from apps.cart.schemas.db import CartCreateSchema, CartItemCreateSchema
from apps.cart.schemas.request import CartItemAddRequestSchema, CartItemUpdateRequestSchema
from apps.cart.use_cases import (
    AddItemUseCase,
    ClearCartUseCase,
    GetCartUseCase,
    MergeCartUseCase,
    RemoveItemUseCase,
    UpdateItemUseCase,
    ValidateCartUseCase,
)
from tests.cart.fakes import (
    FakeB2BClient,
    FakeCartItemRepository,
    FakeCartRepository,
    make_product,
    make_sku,
)


# --------------- ADD ITEM ---------------


@pytest.mark.anyio
async def test_add_sku_increments_quantity_if_already_in_cart():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    sku_id = uuid4()
    product_id = uuid4()
    b2b = FakeB2BClient(skus={sku_id: make_sku(sku_id=sku_id, product_id=product_id, active_quantity=100)})
    use_case = AddItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)

    first = await use_case(
        CartItemAddRequestSchema(sku_id=sku_id, quantity=2),
        user_id=user_id,
        session_id=None,
    )
    assert first.created is True
    assert first.item.quantity == 2
    assert first.item.product_id == product_id

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
    sku_id = uuid4()
    product_id = uuid4()
    b2b = FakeB2BClient(skus={sku_id: make_sku(sku_id=sku_id, product_id=product_id)})
    use_case = AddItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)

    session_id = str(uuid4())
    result = await use_case(
        CartItemAddRequestSchema(sku_id=sku_id, quantity=1),
        user_id=None,
        session_id=session_id,
    )

    assert result.created is True
    assert cart_repo.created[0].session_id == session_id
    assert cart_repo.created[0].user_id is None


@pytest.mark.anyio
async def test_add_sku_404_when_b2b_sku_missing():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    b2b = FakeB2BClient(skus={})  # любой sku → 404
    use_case = AddItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)

    with pytest.raises(SkuUnavailableError):
        await use_case(
            CartItemAddRequestSchema(sku_id=uuid4(), quantity=1),
            user_id=uuid4(),
            session_id=None,
        )


@pytest.mark.anyio
async def test_add_sku_409_when_insufficient_stock():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    sku_id = uuid4()
    product_id = uuid4()
    b2b = FakeB2BClient(skus={sku_id: make_sku(sku_id=sku_id, product_id=product_id, active_quantity=3)})
    use_case = AddItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)

    with pytest.raises(InsufficientStockError):
        await use_case(
            CartItemAddRequestSchema(sku_id=sku_id, quantity=5),
            user_id=uuid4(),
            session_id=None,
        )


# --------------- UPDATE ITEM ---------------


@pytest.mark.anyio
async def test_update_item_changes_quantity():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))
    sku_id = uuid4()
    product_id = uuid4()
    item = await item_repo.create(
        CartItemCreateSchema(cart_id=cart.id, sku_id=sku_id, product_id=product_id, quantity=2)
    )
    b2b = FakeB2BClient(skus={sku_id: make_sku(sku_id=sku_id, product_id=product_id, active_quantity=50)})

    use_case = UpdateItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)
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
    await item_repo.create(
        CartItemCreateSchema(cart_id=foreign_cart.id, sku_id=foreign_sku, product_id=uuid4(), quantity=1)
    )
    b2b = FakeB2BClient()

    use_case = UpdateItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)

    with pytest.raises(CartItemNotFoundError):
        await use_case(
            foreign_sku,
            CartItemUpdateRequestSchema(quantity=5),
            user_id=uuid4(),  # другой user — нет своей корзины с этим sku
            session_id=None,
        )


@pytest.mark.anyio
async def test_update_item_409_when_insufficient_stock():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))
    sku_id = uuid4()
    product_id = uuid4()
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_id, product_id=product_id, quantity=2))
    b2b = FakeB2BClient(skus={sku_id: make_sku(sku_id=sku_id, product_id=product_id, active_quantity=4)})

    use_case = UpdateItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)
    with pytest.raises(InsufficientStockError):
        await use_case(
            sku_id,
            CartItemUpdateRequestSchema(quantity=10),
            user_id=user_id,
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
    item = await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_id, product_id=uuid4(), quantity=1))

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
        CartItemCreateSchema(cart_id=foreign_cart.id, sku_id=foreign_sku, product_id=uuid4(), quantity=1)
    )

    use_case = RemoveItemUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)

    with pytest.raises(CartItemNotFoundError):
        await use_case(foreign_sku, user_id=uuid4(), session_id=None)

    assert foreign_item.id in item_repo.by_id


# --------------- CLEAR CART ---------------


@pytest.mark.anyio
async def test_clear_cart_empties_all_items():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=uuid4(), product_id=uuid4(), quantity=1))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=uuid4(), product_id=uuid4(), quantity=2))

    use_case = ClearCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)
    await use_case(user_id=user_id, session_id=None)

    assert await item_repo.list_by_cart(cart.id) == []
    assert cart.id in item_repo.deleted_by_cart
    # Сама корзина не удаляется — она пустая
    assert await cart_repo.get_by_user(user_id) is not None


@pytest.mark.anyio
async def test_clear_cart_noop_when_no_cart():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    use_case = ClearCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)
    # Не должно падать
    await use_case(user_id=uuid4(), session_id=None)
    assert item_repo.deleted_by_cart == []


# --------------- GET CART (B2B enrichment) ---------------


@pytest.mark.anyio
async def test_get_cart_enriched_with_b2b_data():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))

    sku_a = uuid4()
    sku_b = uuid4()
    product_a = uuid4()
    product_b = uuid4()
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_a, product_id=product_a, quantity=2))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_b, product_id=product_b, quantity=3))

    b2b = FakeB2BClient(
        products=[
            make_product(
                product_id=product_a,
                title='Nike Air Max',
                skus=[make_sku(sku_id=sku_a, product_id=product_a, name='42', price=1000, active_quantity=10)],
            ),
            make_product(
                product_id=product_b,
                title='Adidas Boost',
                skus=[make_sku(sku_id=sku_b, product_id=product_b, name='L', price=2500, active_quantity=5)],
            ),
        ]
    )

    use_case = GetCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)
    result = await use_case(user_id=user_id, session_id=None)

    by_sku = {item.sku_id: item for item in result.items}
    assert by_sku[sku_a].name == 'Nike Air Max 42'
    assert by_sku[sku_a].product_id == product_a
    assert by_sku[sku_a].unit_price == 1000
    assert by_sku[sku_a].available_quantity == 10
    assert by_sku[sku_a].line_total == 2000  # 1000 * 2
    assert by_sku[sku_a].is_available is True
    assert by_sku[sku_a].unavailable_reason is None

    assert by_sku[sku_b].line_total == 7500  # 2500 * 3
    assert result.items_count == 5  # 2 + 3
    assert result.subtotal == 9500  # 2000 + 7500
    assert result.is_valid is True
    # Один batch-вызов товаров (не по sku)
    assert len(b2b.post_calls) == 1
    assert b2b.post_calls[0][0] == '/api/v1/public/products/batch'
    assert set(b2b.post_calls[0][1]['product_ids']) == {str(product_a), str(product_b)}


@pytest.mark.anyio
async def test_unavailable_sku_shown_with_reason():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))

    sku_ok = uuid4()
    sku_out = uuid4()
    sku_deleted = uuid4()  # его товара нет в batch-ответе → PRODUCT_DELETED
    product_ok = uuid4()
    product_out = uuid4()
    product_deleted = uuid4()

    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_ok, product_id=product_ok, quantity=2))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_out, product_id=product_out, quantity=1))
    await item_repo.create(
        CartItemCreateSchema(cart_id=cart.id, sku_id=sku_deleted, product_id=product_deleted, quantity=4)
    )

    b2b = FakeB2BClient(
        products=[
            make_product(
                product_id=product_ok,
                title='OK',
                skus=[make_sku(sku_id=sku_ok, product_id=product_ok, price=500, active_quantity=10)],
            ),
            # product_out виден, но его SKU имеет active_quantity == 0 → OUT_OF_STOCK
            make_product(
                product_id=product_out,
                title='Out',
                skus=[make_sku(sku_id=sku_out, product_id=product_out, price=800, active_quantity=0)],
            ),
            # product_deleted НЕ возвращён B2B вовсе
        ]
    )

    use_case = GetCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)
    result = await use_case(user_id=user_id, session_id=None)

    by_sku = {item.sku_id: item for item in result.items}
    assert by_sku[sku_ok].is_available is True
    assert by_sku[sku_ok].unavailable_reason is None

    assert by_sku[sku_out].is_available is False
    assert by_sku[sku_out].unavailable_reason == UnavailableReason.OUT_OF_STOCK
    assert by_sku[sku_out].line_total == 0

    assert by_sku[sku_deleted].is_available is False
    assert by_sku[sku_deleted].unavailable_reason == UnavailableReason.PRODUCT_DELETED
    assert by_sku[sku_deleted].line_total == 0

    # Все 3 позиции присутствуют, но subtotal — только available
    assert len(result.items) == 3
    assert result.subtotal == 1000  # 500 * 2
    assert result.is_valid is False  # есть недоступные


@pytest.mark.anyio
async def test_get_cart_returns_empty_when_no_cart():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    b2b = FakeB2BClient()
    use_case = GetCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)

    result = await use_case(user_id=uuid4(), session_id=None)

    assert result.items == []
    assert result.subtotal == 0
    assert result.items_count == 0
    assert result.is_valid is True
    # Не дёргали B2B
    assert b2b.post_calls == []


@pytest.mark.anyio
async def test_get_cart_does_not_call_b2b_for_empty_cart():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    await cart_repo.create(_cart_create_schema(user_id=user_id))
    b2b = FakeB2BClient()

    use_case = GetCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)
    result = await use_case(user_id=user_id, session_id=None)

    assert result.items == []
    assert b2b.post_calls == []


@pytest.mark.anyio
async def test_get_cart_quantity_exceeds_stock_is_invalid_but_available():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))
    sku_id = uuid4()
    product_id = uuid4()
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_id, product_id=product_id, quantity=10))

    b2b = FakeB2BClient(
        products=[
            make_product(
                product_id=product_id,
                skus=[make_sku(sku_id=sku_id, product_id=product_id, price=100, active_quantity=3)],
            )
        ]
    )
    use_case = GetCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)
    result = await use_case(user_id=user_id, session_id=None)

    item = result.items[0]
    assert item.is_available is True
    assert item.available_quantity == 3
    # line_total на полную запрошенную quantity (available), но корзина невалидна
    assert item.line_total == 1000  # 100 * 10
    assert result.subtotal == 1000
    assert result.is_valid is False


# --------------- VALIDATE CART ---------------


@pytest.mark.anyio
async def test_validate_cart_flags_issues():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))

    sku_ok = uuid4()
    sku_reduced = uuid4()
    sku_deleted = uuid4()
    product_ok = uuid4()
    product_reduced = uuid4()
    product_deleted = uuid4()

    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_ok, product_id=product_ok, quantity=1))
    await item_repo.create(
        CartItemCreateSchema(cart_id=cart.id, sku_id=sku_reduced, product_id=product_reduced, quantity=9)
    )
    await item_repo.create(
        CartItemCreateSchema(cart_id=cart.id, sku_id=sku_deleted, product_id=product_deleted, quantity=1)
    )

    b2b = FakeB2BClient(
        products=[
            make_product(
                product_id=product_ok,
                skus=[make_sku(sku_id=sku_ok, product_id=product_ok, active_quantity=10)],
            ),
            make_product(
                product_id=product_reduced,
                skus=[make_sku(sku_id=sku_reduced, product_id=product_reduced, active_quantity=2)],
            ),
        ]
    )

    get_use_case = GetCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)
    use_case = ValidateCartUseCase(get_cart_use_case=get_use_case)
    result = await use_case(user_id=user_id, session_id=None)

    assert result.is_valid is False
    by_sku = {issue.sku_id: issue for issue in result.issues}
    assert sku_ok not in by_sku
    assert by_sku[sku_reduced].type == CartValidationIssueType.QUANTITY_REDUCED
    assert by_sku[sku_reduced].new_value == 2
    assert by_sku[sku_deleted].type == CartValidationIssueType.PRODUCT_DELETED


@pytest.mark.anyio
async def test_validate_cart_valid_when_all_available():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))
    sku_id = uuid4()
    product_id = uuid4()
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_id, product_id=product_id, quantity=2))
    b2b = FakeB2BClient(
        products=[
            make_product(
                product_id=product_id,
                skus=[make_sku(sku_id=sku_id, product_id=product_id, active_quantity=10)],
            )
        ]
    )

    get_use_case = GetCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=b2b)
    use_case = ValidateCartUseCase(get_cart_use_case=get_use_case)
    result = await use_case(user_id=user_id, session_id=None)

    assert result.is_valid is True
    assert result.issues == []
    assert result.cart.subtotal > 0


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
    await item_repo.create(
        CartItemCreateSchema(cart_id=auth_cart.id, sku_id=sku_shared, product_id=uuid4(), quantity=2)
    )
    await item_repo.create(
        CartItemCreateSchema(cart_id=auth_cart.id, sku_id=sku_auth_only, product_id=uuid4(), quantity=5)
    )

    # Гостевая: SKU-1 c qty=7 (больше — выиграет), SKU-3 (нет в auth)
    guest_cart = await cart_repo.create(_cart_create_schema(session_id=session_id))
    sku_guest_only = uuid4()
    await item_repo.create(
        CartItemCreateSchema(cart_id=guest_cart.id, sku_id=sku_shared, product_id=uuid4(), quantity=7)
    )
    await item_repo.create(
        CartItemCreateSchema(cart_id=guest_cart.id, sku_id=sku_guest_only, product_id=uuid4(), quantity=1)
    )

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
    await item_repo.create(CartItemCreateSchema(cart_id=guest_cart.id, sku_id=sku, product_id=uuid4(), quantity=3))

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
    await item_repo.create(CartItemCreateSchema(cart_id=auth_cart.id, sku_id=sku, product_id=uuid4(), quantity=10))

    guest_cart = await cart_repo.create(_cart_create_schema(session_id=session_id))
    await item_repo.create(CartItemCreateSchema(cart_id=guest_cart.id, sku_id=sku, product_id=uuid4(), quantity=2))

    use_case = MergeCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo)
    await use_case(user_id=user_id, session_id=session_id)

    items = await item_repo.list_by_cart(auth_cart.id)
    assert len(items) == 1
    assert items[0].quantity == 10  # MAX(10, 2)


# --------------- helpers ---------------


def _cart_create_schema(user_id: UUID | None = None, session_id: str | None = None):
    return CartCreateSchema(user_id=user_id, session_id=session_id)
