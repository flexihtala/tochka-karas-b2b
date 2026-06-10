from uuid import UUID, uuid4

import pytest

from apps.products.enums import ProductStatus
from apps.skus.errors import (
    SKUHardBlockedError,
    SKUHasActiveReservesError,
    SKUNotFoundError,
    SKUNotOwnerError,
)
from apps.skus.use_cases.delete_sku import DeleteSKUUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from shared.types import ServiceName
from tests.skus.fakes import (
    FakeOutboxRepository,
    FakeProductRepositoryReadable,
    FakeSKURepository,
)


def make_authenticated_user(user_id: UUID | None = None, role: UserRole = UserRole.SELLER) -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=user_id or uuid4(), role=role)


def make_use_case(
    *,
    sku_repository: FakeSKURepository | None = None,
    product_repository: FakeProductRepositoryReadable | None = None,
    outbox_repository: FakeOutboxRepository | None = None,
) -> DeleteSKUUseCase:
    return DeleteSKUUseCase(
        sku_repository=sku_repository or FakeSKURepository(),
        product_repository=product_repository or FakeProductRepositoryReadable(),
        outbox_repository=outbox_repository or FakeOutboxRepository(),
    )


@pytest.mark.anyio
async def test_delete_sku_succeeds():
    """Удаление SKU с MODERATED-товара без active_quantity и без резервов: успех, побочки нет."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    outbox = FakeOutboxRepository()

    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    # Оставляем ещё один SKU, чтобы тест не триггерил DELETED-эффект.
    other_sku_id = skus.add(product_id=product_id, active_quantity=5, reserved_quantity=0)
    sku_id = skus.add(product_id=product_id, active_quantity=0, reserved_quantity=0)

    use_case = make_use_case(sku_repository=skus, product_repository=products, outbox_repository=outbox)

    await use_case(sku_id, user)

    # SKU физически удалён, остальные не тронуты.
    assert sku_id not in skus.by_id
    assert other_sku_id in skus.by_id
    assert skus.deleted_ids == [sku_id]
    # Статус продукта не меняется.
    assert products.by_id[product_id].status == ProductStatus.MODERATED
    assert products.updated == []
    # Побочных событий нет: active_quantity удалённого == 0, не последний SKU.
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_delete_sku_with_active_reserves_returns_409():
    """sku.reserved_quantity > 0 → 409 HAS_ACTIVE_RESERVES, ничего не удаляется."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    outbox = FakeOutboxRepository()

    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    sku_id = skus.add(product_id=product_id, active_quantity=10, reserved_quantity=3)

    use_case = make_use_case(sku_repository=skus, product_repository=products, outbox_repository=outbox)

    with pytest.raises(SKUHasActiveReservesError) as exc_info:
        await use_case(sku_id, user)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == 'HAS_ACTIVE_RESERVES'
    # SKU остался в БД, события не отправлены.
    assert sku_id in skus.by_id
    assert skus.deleted_ids == []
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_last_sku_on_moderation_transitions_product_to_created():
    """Последний SKU удалён + product.status == ON_MODERATION:
    → product.status → CREATED + outbox DELETED (target=moderation)."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    outbox = FakeOutboxRepository()

    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.ON_MODERATION)
    sku_id = skus.add(product_id=product_id, active_quantity=0, reserved_quantity=0)

    use_case = make_use_case(sku_repository=skus, product_repository=products, outbox_repository=outbox)

    await use_case(sku_id, user)

    # SKU удалён.
    assert sku_id not in skus.by_id
    # Статус продукта возвращён в CREATED.
    assert products.by_id[product_id].status == ProductStatus.CREATED
    assert len(products.updated) == 1
    assert products.updated[0].id == product_id
    assert products.updated[0].status == ProductStatus.CREATED
    # Outbox: DELETED в moderation.
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'DELETED'
    assert event.target_service == ServiceName.MODERATION
    assert event.payload['product_id'] == str(product_id)
    assert event.idempotency_key is not None


@pytest.mark.anyio
async def test_delete_sku_hard_blocked_product_returns_403():
    """product.status == HARD_BLOCKED → 403 HARD_BLOCKED, ничего не удаляется."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    outbox = FakeOutboxRepository()

    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.HARD_BLOCKED)
    sku_id = skus.add(product_id=product_id)

    use_case = make_use_case(sku_repository=skus, product_repository=products, outbox_repository=outbox)

    with pytest.raises(SKUHardBlockedError) as exc_info:
        await use_case(sku_id, user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == 'HARD_BLOCKED'
    assert sku_id in skus.by_id
    assert skus.deleted_ids == []
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_sku_out_of_stock_event_on_moderated_product():
    """SKU был на MODERATED-товаре, active_quantity > 0:
    → outbox SKU_OUT_OF_STOCK (target=b2c) с sku_id."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    outbox = FakeOutboxRepository()

    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    # Ещё один SKU, чтобы не триггерить DELETED.
    skus.add(product_id=product_id, active_quantity=5, reserved_quantity=0)
    sku_id = skus.add(product_id=product_id, active_quantity=7, reserved_quantity=0)

    use_case = make_use_case(sku_repository=skus, product_repository=products, outbox_repository=outbox)

    await use_case(sku_id, user)

    # SKU удалён.
    assert sku_id not in skus.by_id
    # Статус MODERATED-товара не меняется.
    assert products.by_id[product_id].status == ProductStatus.MODERATED
    assert products.updated == []
    # Outbox: SKU_OUT_OF_STOCK в b2c.
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'SKU_OUT_OF_STOCK'
    assert event.target_service == ServiceName.B2C
    assert event.payload['sku_id'] == str(sku_id)
    assert event.payload['product_id'] == str(product_id)
    assert event.idempotency_key is not None


# --- Дополнительные проверки гардов и порядка ---


@pytest.mark.anyio
async def test_delete_sku_not_found_returns_404():
    """SKU не существует → 404 NOT_FOUND."""
    use_case = make_use_case()
    user = make_authenticated_user()

    with pytest.raises(SKUNotFoundError) as exc_info:
        await use_case(uuid4(), user)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == 'NOT_FOUND'


@pytest.mark.anyio
async def test_delete_sku_not_owner_returns_403():
    """sku.product.seller_id != JWT.user_id → 403 NOT_OWNER (защита от IDOR)."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()

    user = make_authenticated_user()
    another_seller_id = uuid4()
    product_id = products.add(seller_id=another_seller_id, status=ProductStatus.MODERATED)
    sku_id = skus.add(product_id=product_id)

    use_case = make_use_case(sku_repository=skus, product_repository=products)

    with pytest.raises(SKUNotOwnerError) as exc_info:
        await use_case(sku_id, user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == 'NOT_OWNER'
    # SKU не удалён.
    assert sku_id in skus.by_id


@pytest.mark.anyio
async def test_hard_blocked_checked_before_reserves():
    """Порядок гардов: HARD_BLOCKED проверяется ДО reserved_quantity.
    Даже с активными резервами на HARD_BLOCKED-товаре → 403, не 409."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()

    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.HARD_BLOCKED)
    sku_id = skus.add(product_id=product_id, reserved_quantity=5)

    use_case = make_use_case(sku_repository=skus, product_repository=products)

    with pytest.raises(SKUHardBlockedError):
        await use_case(sku_id, user)


@pytest.mark.anyio
async def test_last_sku_on_created_product_no_side_effects():
    """Удаление последнего SKU при product.status == CREATED:
    статус не меняется (он уже CREATED), outbox-событие DELETED не отправляется."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    outbox = FakeOutboxRepository()

    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED)
    sku_id = skus.add(product_id=product_id, active_quantity=0, reserved_quantity=0)

    use_case = make_use_case(sku_repository=skus, product_repository=products, outbox_repository=outbox)

    await use_case(sku_id, user)

    assert sku_id not in skus.by_id
    assert products.by_id[product_id].status == ProductStatus.CREATED
    assert products.updated == []
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_delete_sku_on_moderated_with_zero_active_no_b2c_event():
    """SKU на MODERATED-товаре, но active_quantity == 0:
    SKU_OUT_OF_STOCK не отправляется."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    outbox = FakeOutboxRepository()

    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    skus.add(product_id=product_id, active_quantity=5, reserved_quantity=0)
    sku_id = skus.add(product_id=product_id, active_quantity=0, reserved_quantity=0)

    use_case = make_use_case(sku_repository=skus, product_repository=products, outbox_repository=outbox)

    await use_case(sku_id, user)

    assert outbox.enqueued == []
