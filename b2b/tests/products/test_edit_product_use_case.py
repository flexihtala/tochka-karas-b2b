"""Unit-тесты use-case'а редактирования товара (US-B2B-03).

Покрытые сценарии (Definition of Done):
- test_edit_moderated_product_returns_to_on_moderation — MODERATED → ON_MODERATION + outbox EDITED
- test_edit_blocked_product_returns_to_on_moderation — BLOCKED → ON_MODERATION + outbox EDITED
- test_edit_hard_blocked_returns_403 — HARD_BLOCKED → ForbiddenError (HARD_BLOCKED)
- test_edit_others_product_returns_403 — IDOR: чужой товар → 403 NOT_OWNER

Дополнительные edge-cases:
- На статусах CREATED / ON_MODERATION редактирование разрешено, но событие/смена статуса НЕ происходят.
- images/characteristics — атомарная замена (delete + bulk create) только если поле передано.
- Пустой массив images=[] → 400.
- Несуществующий product_id → 404.
- Несуществующая category_id (если поле передано) → 400.
"""

from uuid import uuid4

import pytest

from apps.products.enums import ProductStatus
from apps.products.errors import (
    CategoryNotFoundError,
    ImagesRequiredError,
    ProductHardBlockedError,
    ProductNotFoundError,
    ProductNotOwnerError,
)
from apps.products.schemas.request import (
    CharacteristicRequestSchema,
    ProductEditRequestSchema,
    ProductImageCreateRequestSchema,
)
from apps.products.use_cases.edit_product import EditProductUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from shared.types import ServiceName
from tests.products.fakes import (
    FakeCategoryRepository,
    FakeCharacteristicValueRepository,
    FakeOutboxRepository,
    FakeProductImageRepository,
    FakeProductRepository,
    FakeSKURepositoryForProducts,
)


def make_user(user_id=None, role: UserRole = UserRole.SELLER) -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=user_id or uuid4(), role=role)


def make_request(
    *,
    title: str | None = None,
    description: str | None = None,
    category_id=None,
    slug: str | None = None,
    images: list[ProductImageCreateRequestSchema] | None = None,
    characteristics: list[CharacteristicRequestSchema] | None = None,
) -> ProductEditRequestSchema:
    return ProductEditRequestSchema(
        title=title,
        description=description,
        category_id=category_id,
        slug=slug,
        images=images,
        characteristics=characteristics,
    )


def make_use_case(
    *,
    products: FakeProductRepository | None = None,
    images: FakeProductImageRepository | None = None,
    characteristics: FakeCharacteristicValueRepository | None = None,
    categories: FakeCategoryRepository | None = None,
    skus: FakeSKURepositoryForProducts | None = None,
    outbox: FakeOutboxRepository | None = None,
) -> EditProductUseCase:
    return EditProductUseCase(
        product_repository=products or FakeProductRepository(),
        image_repository=images or FakeProductImageRepository(),
        characteristic_repository=characteristics or FakeCharacteristicValueRepository(),
        category_repository=categories or FakeCategoryRepository(),
        sku_repository=skus or FakeSKURepositoryForProducts(),
        outbox_repository=outbox or FakeOutboxRepository(),
    )


# ============================================================================
# DoD: Required tests
# ============================================================================


@pytest.mark.anyio
async def test_edit_moderated_product_returns_to_on_moderation():
    """MODERATED product → status переводится в ON_MODERATION + outbox EDITED."""
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.MODERATED).id

    use_case = make_use_case(products=products, outbox=outbox)

    response = await use_case(product_id, make_request(title='Updated title'), user)

    # Статус перешёл в ON_MODERATION.
    assert response.status == ProductStatus.ON_MODERATION
    assert products.by_id[product_id].status == ProductStatus.ON_MODERATION

    # Outbox содержит ровно одно событие EDITED → MODERATION.
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'EDITED'
    assert event.target_service == ServiceName.MODERATION
    assert event.payload['product_id'] == str(product_id)
    assert event.payload['seller_id'] == str(user.id)
    assert event.payload['title'] == 'Updated title'


@pytest.mark.anyio
async def test_edit_blocked_product_returns_to_on_moderation():
    """BLOCKED product → status переводится в ON_MODERATION + outbox EDITED."""
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.BLOCKED).id

    use_case = make_use_case(products=products, outbox=outbox)

    response = await use_case(product_id, make_request(description='Updated description'), user)

    assert response.status == ProductStatus.ON_MODERATION
    assert products.by_id[product_id].status == ProductStatus.ON_MODERATION
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].event_type == 'EDITED'
    assert outbox.enqueued[0].target_service == ServiceName.MODERATION


@pytest.mark.anyio
async def test_edit_hard_blocked_returns_403():
    """HARD_BLOCKED product → ProductHardBlockedError (403, code=HARD_BLOCKED)."""
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.HARD_BLOCKED).id

    use_case = make_use_case(products=products, outbox=outbox)

    with pytest.raises(ProductHardBlockedError) as exc_info:
        await use_case(product_id, make_request(title='Updated title'), user)

    assert exc_info.value.code == 'HARD_BLOCKED'
    assert exc_info.value.status_code == 403
    # Ничего не изменилось — товар не редактировался, событие не отправлено.
    assert products.updated == []
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_edit_others_product_returns_403():
    """Чужой товар → ProductNotOwnerError (403 NOT_OWNER, защита от IDOR)."""
    products = FakeProductRepository()
    user = make_user()
    other_seller_id = uuid4()
    product_id = products.add(seller_id=other_seller_id, status=ProductStatus.MODERATED).id

    use_case = make_use_case(products=products)

    with pytest.raises(ProductNotOwnerError) as exc_info:
        await use_case(product_id, make_request(title='Hack'), user)

    assert exc_info.value.code == 'NOT_OWNER'
    assert exc_info.value.status_code == 403
    # Чужой товар не был тронут.
    assert products.updated == []
    assert products.by_id[product_id].title == 'iPhone 15 Pro Max'


# ============================================================================
# Edge cases
# ============================================================================


@pytest.mark.anyio
async def test_edit_created_product_no_status_transition_no_event():
    """На статусе CREATED редактирование разрешено, но событие/смена статуса не происходят."""
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED).id

    use_case = make_use_case(products=products, outbox=outbox)

    response = await use_case(product_id, make_request(title='Updated'), user)

    assert response.status == ProductStatus.CREATED
    assert products.by_id[product_id].status == ProductStatus.CREATED
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_edit_on_moderation_product_no_status_transition_no_event():
    """На статусе ON_MODERATION редактирование разрешено, но событие/смена статуса не происходят."""
    products = FakeProductRepository()
    outbox = FakeOutboxRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.ON_MODERATION).id

    use_case = make_use_case(products=products, outbox=outbox)

    response = await use_case(product_id, make_request(title='Updated'), user)

    assert response.status == ProductStatus.ON_MODERATION
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_edit_product_not_found_returns_404():
    """Несуществующий product_id → ProductNotFoundError (404)."""
    user = make_user()
    use_case = make_use_case()

    with pytest.raises(ProductNotFoundError) as exc_info:
        await use_case(uuid4(), make_request(title='Updated'), user)

    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_edit_with_images_replaces_atomically():
    """Если передан images=[...] — старые удаляются, новые создаются."""
    products = FakeProductRepository()
    images = FakeProductImageRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED).id
    # Старые изображения
    images.add(product_id=product_id, url='/old1.jpg', ordering=0)
    images.add(product_id=product_id, url='/old2.jpg', ordering=1)

    use_case = make_use_case(products=products, images=images)

    response = await use_case(
        product_id,
        make_request(images=[ProductImageCreateRequestSchema(url='/new.jpg', ordering=0)]),
        user,
    )

    assert len(response.images) == 1
    assert response.images[0].url == '/new.jpg'
    # Старые исчезли
    urls = {img.url for img in images.by_id.values() if img.product_id == product_id}
    assert urls == {'/new.jpg'}


@pytest.mark.anyio
async def test_edit_with_empty_images_returns_400():
    """images=[] → ImagesRequiredError (минимум одно изображение)."""
    products = FakeProductRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED).id

    use_case = make_use_case(products=products)

    with pytest.raises(ImagesRequiredError):
        await use_case(product_id, make_request(images=[]), user)


@pytest.mark.anyio
async def test_edit_with_images_not_set_preserves_existing():
    """Если images=None в запросе — старые изображения остаются."""
    products = FakeProductRepository()
    images = FakeProductImageRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED).id
    images.add(product_id=product_id, url='/keep.jpg', ordering=0)

    use_case = make_use_case(products=products, images=images)

    response = await use_case(product_id, make_request(title='Updated only title'), user)

    assert len(response.images) == 1
    assert response.images[0].url == '/keep.jpg'


@pytest.mark.anyio
async def test_edit_with_characteristics_replaces_atomically():
    """Если передан characteristics=[...] — старые удаляются, новые создаются."""
    products = FakeProductRepository()
    characteristics = FakeCharacteristicValueRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED).id
    characteristics.add(product_id=product_id, name='Бренд', value='Samsung')

    use_case = make_use_case(products=products, characteristics=characteristics)

    response = await use_case(
        product_id,
        make_request(characteristics=[CharacteristicRequestSchema(name='Бренд', value='Apple')]),
        user,
    )

    assert len(response.characteristics) == 1
    assert response.characteristics[0].name == 'Бренд'
    assert response.characteristics[0].value == 'Apple'


@pytest.mark.anyio
async def test_edit_with_invalid_category_returns_400():
    """category_id, которой нет в справочнике, → CategoryNotFoundError (400)."""
    products = FakeProductRepository()
    user = make_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED).id

    use_case = make_use_case(products=products)  # categories пустой

    with pytest.raises(CategoryNotFoundError):
        await use_case(product_id, make_request(category_id=uuid4()), user)


@pytest.mark.anyio
async def test_edit_outbox_event_payload_contains_full_product_snapshot():
    """EDITED-payload содержит свежий snapshot: title, description, images, characteristics."""
    products = FakeProductRepository()
    images = FakeProductImageRepository()
    characteristics = FakeCharacteristicValueRepository()
    skus = FakeSKURepositoryForProducts()
    outbox = FakeOutboxRepository()
    user = make_user()
    product_id = products.add(
        seller_id=user.id,
        status=ProductStatus.MODERATED,
        title='Old title',
        slug='iphone-15',
    ).id
    images.add(product_id=product_id, url='/old.jpg', ordering=0)
    characteristics.add(product_id=product_id, name='Бренд', value='Apple')
    skus.count_by_product_overrides[product_id] = 2

    use_case = make_use_case(
        products=products,
        images=images,
        characteristics=characteristics,
        skus=skus,
        outbox=outbox,
    )

    await use_case(
        product_id,
        make_request(
            title='New title',
            images=[ProductImageCreateRequestSchema(url='/new.jpg', ordering=0)],
        ),
        user,
    )

    assert len(outbox.enqueued) == 1
    payload = outbox.enqueued[0].payload
    assert payload['title'] == 'New title'
    assert payload['slug'] == 'iphone-15'
    assert payload['product_id'] == str(product_id)
    assert payload['seller_id'] == str(user.id)
    assert len(payload['images']) == 1
    assert payload['images'][0]['url'] == '/new.jpg'
    assert payload['sku_count'] == 2
