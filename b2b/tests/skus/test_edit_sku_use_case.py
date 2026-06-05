"""Unit-тесты use-case'а редактирования SKU (US-B2B-03).

Definition of Done:
- test_reserves_preserved_after_sku_edit — reserved_quantity не меняется
- test_edit_hard_blocked_returns_403 — HARD_BLOCKED parent → 403

Дополнительные edge-cases:
- ownership (через parent product) — IDOR-protection
- MODERATED/BLOCKED parent → ON_MODERATION + outbox EDITED
- CREATED/ON_MODERATION parent → редактирование разрешено, событие НЕ отправляется
- images/characteristics — атомарная замена при передаче поля
- pустой images=[] → 400
- SKU не найден → 404
"""

from uuid import uuid4

import pytest

from apps.products.enums import ProductStatus
from apps.skus.errors import (
    SKUHardBlockedError,
    SKUImagesRequiredError,
    SKUNotFoundError,
    SKUNotOwnerError,
)
from apps.skus.schemas.request import (
    SKUCharacteristicRequestSchema,
    SKUEditRequestSchema,
    SKUImageCreateRequestSchema,
)
from apps.skus.use_cases.edit_sku import EditSKUUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from shared.types import ServiceName
from tests.skus.fakes import (
    FakeOutboxRepository,
    FakeProductCharacteristicRepository,
    FakeProductImageRepository,
    FakeProductRepositoryReadable,
    FakeSKUCharacteristicValueRepository,
    FakeSKUImageRepository,
    FakeSKURepository,
)


def make_user(user_id=None, role: UserRole = UserRole.SELLER) -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=user_id or uuid4(), role=role)


def make_request(
    *,
    name: str | None = None,
    price: int | None = None,
    cost_price: int | None = None,
    discount: int | None = None,
    article: str | None = None,
    images: list[SKUImageCreateRequestSchema] | None = None,
    characteristics: list[SKUCharacteristicRequestSchema] | None = None,
) -> SKUEditRequestSchema:
    return SKUEditRequestSchema(
        name=name,
        price=price,
        cost_price=cost_price,
        discount=discount,
        article=article,
        images=images,
        characteristics=characteristics,
    )


def make_use_case(
    *,
    skus: FakeSKURepository | None = None,
    sku_images: FakeSKUImageRepository | None = None,
    sku_characteristics: FakeSKUCharacteristicValueRepository | None = None,
    products: FakeProductRepositoryReadable | None = None,
    product_images: FakeProductImageRepository | None = None,
    product_characteristics: FakeProductCharacteristicRepository | None = None,
    outbox: FakeOutboxRepository | None = None,
) -> EditSKUUseCase:
    return EditSKUUseCase(
        sku_repository=skus or FakeSKURepository(),
        sku_image_repository=sku_images or FakeSKUImageRepository(),
        sku_characteristic_repository=sku_characteristics or FakeSKUCharacteristicValueRepository(),
        product_repository=products or FakeProductRepositoryReadable(),
        product_image_repository=product_images or FakeProductImageRepository(),
        product_characteristic_repository=product_characteristics or FakeProductCharacteristicRepository(),
        outbox_repository=outbox or FakeOutboxRepository(),
    )


# ============================================================================
# DoD: Required tests
# ============================================================================


@pytest.mark.anyio
async def test_reserves_preserved_after_sku_edit():
    """reserved_quantity не должно меняться после PUT — даже если request валидный."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    sku_id = skus.add(
        product_id=product_id,
        name='256GB Black',
        price=12_999_000,
        active_quantity=10,
        reserved_quantity=3,
    )

    use_case = make_use_case(products=products, skus=skus)

    response = await use_case(sku_id, make_request(price=14_999_000, name='New name'), user)

    # reserved_quantity сохранилось.
    assert response.reserved_quantity == 3
    assert skus.by_id[sku_id].reserved_quantity == 3
    # active_quantity тоже не меняется.
    assert skus.by_id[sku_id].active_quantity == 10
    # Поля, которые есть в SKUUpdate-DTO, отредактированы.
    assert skus.by_id[sku_id].price == 14_999_000
    assert skus.by_id[sku_id].name == 'New name'


@pytest.mark.anyio
async def test_edit_hard_blocked_returns_403():
    """parent product со статусом HARD_BLOCKED → SKUHardBlockedError (403, code=HARD_BLOCKED)."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.HARD_BLOCKED)
    sku_id = skus.add(product_id=product_id, reserved_quantity=0)

    use_case = make_use_case(products=products, skus=skus)

    with pytest.raises(SKUHardBlockedError) as exc_info:
        await use_case(sku_id, make_request(price=14_999_000), user)

    assert exc_info.value.code == 'HARD_BLOCKED'
    assert exc_info.value.status_code == 403
    # SKU не редактировался.
    assert skus.updated == []


# ============================================================================
# Edge cases — ownership, transitions, validation
# ============================================================================


@pytest.mark.anyio
async def test_edit_sku_with_moderated_parent_returns_to_on_moderation():
    """parent product со статусом MODERATED → product → ON_MODERATION + outbox EDITED."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    outbox = FakeOutboxRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    sku_id = skus.add(product_id=product_id)

    use_case = make_use_case(products=products, skus=skus, outbox=outbox)

    await use_case(sku_id, make_request(price=15_000_000), user)

    # Parent перешёл в ON_MODERATION.
    assert products.by_id[product_id].status == ProductStatus.ON_MODERATION
    # Outbox содержит EDITED событие.
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'EDITED'
    assert event.target_service == ServiceName.MODERATION
    assert event.payload['product_id'] == str(product_id)


@pytest.mark.anyio
async def test_edit_sku_with_blocked_parent_returns_to_on_moderation():
    """parent product со статусом BLOCKED → product → ON_MODERATION + outbox EDITED."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    outbox = FakeOutboxRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.BLOCKED)
    sku_id = skus.add(product_id=product_id)

    use_case = make_use_case(products=products, skus=skus, outbox=outbox)

    await use_case(sku_id, make_request(price=15_000_000), user)

    assert products.by_id[product_id].status == ProductStatus.ON_MODERATION
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].event_type == 'EDITED'


@pytest.mark.anyio
async def test_edit_sku_with_created_parent_no_event():
    """parent product в CREATED — событие не отправляется, статус не меняется."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    outbox = FakeOutboxRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED)
    sku_id = skus.add(product_id=product_id)

    use_case = make_use_case(products=products, skus=skus, outbox=outbox)

    await use_case(sku_id, make_request(price=15_000_000), user)

    assert products.by_id[product_id].status == ProductStatus.CREATED
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_edit_sku_with_on_moderation_parent_no_event():
    """parent product уже в ON_MODERATION — событие не отправляется, статус не меняется."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    outbox = FakeOutboxRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.ON_MODERATION)
    sku_id = skus.add(product_id=product_id)

    use_case = make_use_case(products=products, skus=skus, outbox=outbox)

    await use_case(sku_id, make_request(price=15_000_000), user)

    assert products.by_id[product_id].status == ProductStatus.ON_MODERATION
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_edit_sku_of_other_seller_returns_403():
    """parent product принадлежит другому seller → SKUNotOwnerError (IDOR)."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    user = make_user()
    other_seller_id = uuid4()
    product_id = products.add(seller_id=other_seller_id, status=ProductStatus.MODERATED)
    sku_id = skus.add(product_id=product_id)

    use_case = make_use_case(products=products, skus=skus)

    with pytest.raises(SKUNotOwnerError) as exc_info:
        await use_case(sku_id, make_request(price=15_000_000), user)

    assert exc_info.value.code == 'NOT_OWNER'
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_edit_sku_not_found_returns_404():
    """Несуществующий sku_id → SKUNotFoundError (404)."""
    user = make_user()
    use_case = make_use_case()

    with pytest.raises(SKUNotFoundError):
        await use_case(uuid4(), make_request(price=15_000_000), user)


@pytest.mark.anyio
async def test_edit_sku_with_images_replaces_atomically():
    """Если передан images=[...] — старые удаляются, новые создаются."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    sku_images = FakeSKUImageRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED)
    sku_id = skus.add(product_id=product_id)
    sku_images.add(sku_id=sku_id, url='/old1.jpg', ordering=0)
    sku_images.add(sku_id=sku_id, url='/old2.jpg', ordering=1)

    use_case = make_use_case(products=products, skus=skus, sku_images=sku_images)

    response = await use_case(
        sku_id,
        make_request(images=[SKUImageCreateRequestSchema(url='/new.jpg', ordering=0)]),
        user,
    )

    assert len(response.images) == 1
    assert response.images[0].url == '/new.jpg'
    # Старые исчезли.
    urls = {img.url for img in sku_images.by_id.values() if img.sku_id == sku_id}
    assert urls == {'/new.jpg'}


@pytest.mark.anyio
async def test_edit_sku_with_empty_images_returns_400():
    """images=[] → SKUImagesRequiredError."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED)
    sku_id = skus.add(product_id=product_id)

    use_case = make_use_case(products=products, skus=skus)

    with pytest.raises(SKUImagesRequiredError):
        await use_case(sku_id, make_request(images=[]), user)


@pytest.mark.anyio
async def test_edit_sku_with_characteristics_replaces_atomically():
    """characteristics=[...] → старые удаляются, новые создаются."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    sku_characteristics = FakeSKUCharacteristicValueRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED)
    sku_id = skus.add(product_id=product_id)
    sku_characteristics.add(sku_id=sku_id, name='Цвет', value='Серый')

    use_case = make_use_case(
        products=products,
        skus=skus,
        sku_characteristics=sku_characteristics,
    )

    response = await use_case(
        sku_id,
        make_request(
            characteristics=[
                SKUCharacteristicRequestSchema(name='Цвет', value='Чёрный титан'),
            ]
        ),
        user,
    )

    assert len(response.characteristics) == 1
    assert response.characteristics[0].name == 'Цвет'
    assert response.characteristics[0].value == 'Чёрный титан'


@pytest.mark.anyio
async def test_edit_sku_with_images_not_set_preserves_existing():
    """Если images=None в запросе — старые остаются."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    sku_images = FakeSKUImageRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED)
    sku_id = skus.add(product_id=product_id)
    sku_images.add(sku_id=sku_id, url='/keep.jpg', ordering=0)

    use_case = make_use_case(products=products, skus=skus, sku_images=sku_images)

    response = await use_case(sku_id, make_request(price=15_000_000), user)

    assert len(response.images) == 1
    assert response.images[0].url == '/keep.jpg'
