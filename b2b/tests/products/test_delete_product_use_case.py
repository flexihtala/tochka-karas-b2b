from uuid import UUID, uuid4

import pytest

from apps.products.enums import ProductStatus
from apps.products.errors import (
    ProductAlreadyDeletedError,
    ProductHardBlockedError,
    ProductNotFoundError,
    ProductNotOwnerError,
)
from apps.products.use_cases.delete_product import DeleteProductUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from shared.types import ServiceName
from tests.products.fakes import (
    FakeOutboxRepository,
    FakeProductRepository,
    FakeSKURepositoryForDelete,
)


def make_authenticated_user(user_id: UUID | None = None, role: UserRole = UserRole.SELLER) -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=user_id or uuid4(), role=role)


def make_use_case(
    *,
    product_repository: FakeProductRepository | None = None,
    sku_repository: FakeSKURepositoryForDelete | None = None,
    outbox_repository: FakeOutboxRepository | None = None,
) -> DeleteProductUseCase:
    return DeleteProductUseCase(
        product_repository=product_repository or FakeProductRepository(),
        sku_repository=sku_repository or FakeSKURepositoryForDelete(),
        outbox_repository=outbox_repository or FakeOutboxRepository(),
    )


@pytest.mark.anyio
async def test_delete_sets_deleted_true():
    """Удаление выставляет product.deleted = True (мягкое удаление, строка остаётся)."""
    products = FakeProductRepository()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED, deleted=False).id

    use_case = make_use_case(product_repository=products)

    await use_case(product_id, user)

    assert products.by_id[product_id].deleted is True
    # Строка не удалена физически
    assert product_id in products.by_id
    # Был вызов update с deleted=True
    assert len(products.updated) == 1
    assert products.updated[0].id == product_id
    assert products.updated[0].deleted is True


@pytest.mark.anyio
async def test_delete_emits_event_to_moderation():
    """Outbox.enqueue вызван с target_service=moderation, event_type=DELETED, payload содержит product_id + seller_id."""
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.MODERATED).id

    use_case = make_use_case(product_repository=products, outbox_repository=outbox)

    await use_case(product_id, user)

    moderation_events = [e for e in outbox.enqueued if e.target_service == ServiceName.MODERATION]
    assert len(moderation_events) == 1
    event = moderation_events[0]
    assert event.event_type == 'DELETED'
    assert event.idempotency_key is not None
    payload = event.payload
    assert payload['product_id'] == str(product_id)
    assert payload['seller_id'] == str(user.id)


@pytest.mark.anyio
async def test_delete_emits_product_deleted_to_b2c():
    """Outbox.enqueue вызван с target_service=b2c, event_type=PRODUCT_DELETED, payload содержит product_id + sku_ids."""
    products = FakeProductRepository()
    skus = FakeSKURepositoryForDelete()
    outbox = FakeOutboxRepository()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.MODERATED).id
    sku_id_1 = skus.add_sku(product_id)
    sku_id_2 = skus.add_sku(product_id)

    use_case = make_use_case(product_repository=products, sku_repository=skus, outbox_repository=outbox)

    await use_case(product_id, user)

    b2c_events = [e for e in outbox.enqueued if e.target_service == ServiceName.B2C]
    assert len(b2c_events) == 1
    event = b2c_events[0]
    assert event.event_type == 'PRODUCT_DELETED'
    assert event.idempotency_key is not None
    payload = event.payload
    assert payload['product_id'] == str(product_id)
    assert set(payload['sku_ids']) == {str(sku_id_1), str(sku_id_2)}


@pytest.mark.anyio
async def test_delete_emits_both_cascading_events():
    """Контрольный тест: один вызов use-case порождает ровно 2 outbox-события (moderation + b2c)."""
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED).id

    use_case = make_use_case(product_repository=products, outbox_repository=outbox)

    await use_case(product_id, user)

    targets = {e.target_service for e in outbox.enqueued}
    assert targets == {ServiceName.MODERATION, ServiceName.B2C}
    assert len(outbox.enqueued) == 2


@pytest.mark.anyio
async def test_delete_already_deleted_returns_400():
    """Повторное удаление уже мягко удалённого товара → 400 ALREADY_DELETED."""
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, deleted=True).id

    use_case = make_use_case(product_repository=products, outbox_repository=outbox)

    with pytest.raises(ProductAlreadyDeletedError) as exc_info:
        await use_case(product_id, user)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == 'ALREADY_DELETED'
    # Никаких update'ов и outbox-событий
    assert products.updated == []
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_deleted_product_not_in_seller_list():
    """После soft-delete товар не виден в seller list по умолчанию (include_deleted=False).

    Проверка через repository.list_by_seller — фильтрация по deleted=False.
    """
    products = FakeProductRepository()
    user = make_authenticated_user()
    visible_id = products.add(seller_id=user.id, status=ProductStatus.CREATED, deleted=False).id
    to_delete_id = products.add(seller_id=user.id, status=ProductStatus.CREATED, deleted=False).id

    use_case = make_use_case(product_repository=products)
    await use_case(to_delete_id, user)

    # default: include_deleted=False → удалённый товар скрыт
    visible_list = await products.list_by_seller(user.id)
    visible_ids = {p.id for p in visible_list}
    assert visible_ids == {visible_id}
    assert to_delete_id not in visible_ids

    # с include_deleted=True — оба видны (история сохранена)
    full_list = await products.list_by_seller(user.id, include_deleted=True)
    assert {p.id for p in full_list} == {visible_id, to_delete_id}


@pytest.mark.anyio
async def test_delete_others_product_returns_403():
    """Попытка удалить чужой товар (другой seller_id) → 403 NOT_OWNER (защита от IDOR)."""
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    user = make_authenticated_user()
    another_seller_id = uuid4()
    product_id = products.add(seller_id=another_seller_id, status=ProductStatus.CREATED).id

    use_case = make_use_case(product_repository=products, outbox_repository=outbox)

    with pytest.raises(ProductNotOwnerError) as exc_info:
        await use_case(product_id, user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == 'NOT_OWNER'
    # ничего не изменилось
    assert products.updated == []
    assert outbox.enqueued == []
    assert products.by_id[product_id].deleted is False


@pytest.mark.anyio
async def test_delete_hard_blocked_returns_403():
    """Удаление HARD_BLOCKED товара → 403 HARD_BLOCKED."""
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.HARD_BLOCKED).id

    use_case = make_use_case(product_repository=products, outbox_repository=outbox)

    with pytest.raises(ProductHardBlockedError) as exc_info:
        await use_case(product_id, user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == 'HARD_BLOCKED'
    assert products.updated == []
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_delete_nonexistent_product_returns_404():
    """Удаление несуществующего товара → 404 NOT_FOUND."""
    user = make_authenticated_user()
    use_case = make_use_case()

    with pytest.raises(ProductNotFoundError) as exc_info:
        await use_case(uuid4(), user)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == 'NOT_FOUND'


@pytest.mark.anyio
async def test_delete_with_no_skus_still_emits_b2c_event_with_empty_list():
    """Удаление товара без SKU → событие PRODUCT_DELETED всё равно отправляется, sku_ids = []."""
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED).id

    use_case = make_use_case(product_repository=products, outbox_repository=outbox)

    await use_case(product_id, user)

    b2c_events = [e for e in outbox.enqueued if e.target_service == ServiceName.B2C]
    assert len(b2c_events) == 1
    assert b2c_events[0].payload['sku_ids'] == []
