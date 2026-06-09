from uuid import UUID, uuid4

import pytest

from apps.products.enums import ProductStatus
from apps.skus.errors import (
    ProductNotFoundError,
    SKUForbiddenError,
    SKUHardBlockedError,
    SKUImagesRequiredError,
    SKUNotOwnerError,
)
from apps.skus.schemas.request import (
    SKUCharacteristicRequestSchema,
    SKUCreateRequestSchema,
    SKUImageCreateRequestSchema,
)
from apps.skus.use_cases.create_sku import CreateSKUUseCase
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


def make_authenticated_user(user_id: UUID | None = None, role: UserRole = UserRole.SELLER) -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=user_id or uuid4(), role=role)


def make_request(
    *,
    product_id: UUID,
    name: str = '256GB Black',
    price: int = 12_999_000,
    cost_price: int | None = 9_500_000,
    discount: int = 0,
    article: str | None = None,
    images: list[SKUImageCreateRequestSchema] | None = None,
    characteristics: list[SKUCharacteristicRequestSchema] | None = None,
) -> SKUCreateRequestSchema:
    return SKUCreateRequestSchema(
        product_id=product_id,
        name=name,
        price=price,
        cost_price=cost_price,
        discount=discount,
        article=article,
        images=images
        if images is not None
        else [SKUImageCreateRequestSchema(url='/s3/iphone15-black-256.jpg', ordering=0)],
        characteristics=characteristics
        if characteristics is not None
        else [
            SKUCharacteristicRequestSchema(name='Цвет', value='Чёрный'),
            SKUCharacteristicRequestSchema(name='Объём памяти', value='256 ГБ'),
        ],
    )


def make_use_case(
    *,
    sku_repository: FakeSKURepository | None = None,
    sku_image_repository: FakeSKUImageRepository | None = None,
    sku_characteristic_repository: FakeSKUCharacteristicValueRepository | None = None,
    product_repository: FakeProductRepositoryReadable | None = None,
    product_image_repository: FakeProductImageRepository | None = None,
    product_characteristic_repository: FakeProductCharacteristicRepository | None = None,
    outbox_repository: FakeOutboxRepository | None = None,
) -> CreateSKUUseCase:
    return CreateSKUUseCase(
        sku_repository=sku_repository or FakeSKURepository(),
        sku_image_repository=sku_image_repository or FakeSKUImageRepository(),
        sku_characteristic_repository=sku_characteristic_repository or FakeSKUCharacteristicValueRepository(),
        product_repository=product_repository or FakeProductRepositoryReadable(),
        product_image_repository=product_image_repository or FakeProductImageRepository(),
        product_characteristic_repository=product_characteristic_repository or FakeProductCharacteristicRepository(),
        outbox_repository=outbox_repository or FakeOutboxRepository(),
    )


@pytest.mark.anyio
async def test_first_sku_transitions_product_to_on_moderation():
    """Первый SKU для товара со статусом CREATED → товар переходит в ON_MODERATION."""
    products = FakeProductRepositoryReadable()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED)

    use_case = make_use_case(product_repository=products)

    response = await use_case(make_request(product_id=product_id), user)

    assert response.product_id == product_id
    assert products.by_id[product_id].status == ProductStatus.ON_MODERATION
    # Был вызов update со status=ON_MODERATION
    assert len(products.updated) == 1
    assert products.updated[0].status == ProductStatus.ON_MODERATION


@pytest.mark.anyio
async def test_first_sku_emits_created_event_to_moderation():
    """Outbox.enqueue вызван с target_service=moderation, event_type=CREATED, payload содержит product_id + другие поля продукта."""
    products = FakeProductRepositoryReadable()
    product_images = FakeProductImageRepository()
    product_characteristics = FakeProductCharacteristicRepository()
    outbox = FakeOutboxRepository()

    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED, title='iPhone 15', slug='iphone-15')
    product_images.add(product_id=product_id, url='/s3/p1.jpg', ordering=0)
    product_images.add(product_id=product_id, url='/s3/p2.jpg', ordering=1)
    product_characteristics.add(product_id=product_id, name='Бренд', value='Apple')

    use_case = make_use_case(
        product_repository=products,
        product_image_repository=product_images,
        product_characteristic_repository=product_characteristics,
        outbox_repository=outbox,
    )

    response = await use_case(make_request(product_id=product_id), user)

    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'CREATED'
    assert event.target_service == ServiceName.MODERATION
    assert event.idempotency_key is not None
    payload = event.payload
    assert payload['product_id'] == str(product_id)
    assert payload['seller_id'] == str(user.id)
    assert payload['title'] == 'iPhone 15'
    assert payload['slug'] == 'iphone-15'
    assert payload['category_id'] == str(products.by_id[product_id].category_id)
    assert len(payload['images']) == 2
    assert {img['url'] for img in payload['images']} == {'/s3/p1.jpg', '/s3/p2.jpg'}
    assert len(payload['characteristics']) == 1
    assert payload['characteristics'][0]['name'] == 'Бренд'
    # skus содержит только что созданный SKU
    assert len(payload['skus']) == 1
    sku_snapshot = payload['skus'][0]
    assert sku_snapshot['id'] == str(response.id)
    assert sku_snapshot['name'] == '256GB Black'
    assert sku_snapshot['price'] == 12_999_000
    # stock_quantity per canon: active_quantity + reserved_quantity.
    assert sku_snapshot['stock_quantity'] == sku_snapshot['active_quantity'] + sku_snapshot['reserved_quantity']


@pytest.mark.anyio
async def test_second_sku_no_state_change():
    """При добавлении второго SKU товар уже в ON_MODERATION — статус не меняется, событие в outbox не отправляется."""
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepository()
    outbox = FakeOutboxRepository()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.ON_MODERATION)

    # Симулируем, что уже есть один SKU у этого товара.
    skus.count_by_product_overrides[product_id] = 2  # после insert будет count == 2 → не первый

    use_case = make_use_case(
        sku_repository=skus,
        product_repository=products,
        outbox_repository=outbox,
    )

    await use_case(make_request(product_id=product_id), user)

    assert products.by_id[product_id].status == ProductStatus.ON_MODERATION
    assert products.updated == []  # update не вызывался
    assert outbox.enqueued == []  # событие не отправлялось


@pytest.mark.anyio
async def test_add_sku_to_moderated_product_returns_to_on_moderation():
    """Canon B2B-2 (2026-05-27): SKU добавлен к MODERATED товару → ON_MODERATION + событие EDITED.

    Иначе новый непроверенный вариант попал бы на витрину мимо модерации.
    """
    products = FakeProductRepositoryReadable()
    product_images = FakeProductImageRepository()
    product_characteristics = FakeProductCharacteristicRepository()
    outbox = FakeOutboxRepository()

    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.MODERATED, title='iPhone 15', slug='iphone-15')
    product_images.add(product_id=product_id, url='/s3/p1.jpg', ordering=0)
    product_characteristics.add(product_id=product_id, name='Бренд', value='Apple')

    use_case = make_use_case(
        product_repository=products,
        product_image_repository=product_images,
        product_characteristic_repository=product_characteristics,
        outbox_repository=outbox,
    )

    response = await use_case(make_request(product_id=product_id), user)

    # Статус вернулся на повторную модерацию.
    assert products.by_id[product_id].status == ProductStatus.ON_MODERATION
    assert len(products.updated) == 1
    assert products.updated[0].status == ProductStatus.ON_MODERATION

    # Событие EDITED в moderation с полным снимком продукта + новый SKU.
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'EDITED'
    assert event.target_service == ServiceName.MODERATION
    assert event.idempotency_key is not None
    payload = event.payload
    assert payload['product_id'] == str(product_id)
    assert payload['seller_id'] == str(user.id)
    assert payload['title'] == 'iPhone 15'
    assert payload['slug'] == 'iphone-15'
    assert payload['category_id'] == str(products.by_id[product_id].category_id)
    assert len(payload['images']) == 1
    assert payload['images'][0]['url'] == '/s3/p1.jpg'
    assert len(payload['characteristics']) == 1
    assert payload['characteristics'][0]['name'] == 'Бренд'
    # skus содержит только что созданный SKU.
    assert len(payload['skus']) == 1
    assert payload['skus'][0]['id'] == str(response.id)
    assert payload['skus'][0]['name'] == '256GB Black'


@pytest.mark.anyio
async def test_add_sku_to_blocked_product_returns_to_on_moderation():
    """Canon B2B-2 (2026-05-27): SKU добавлен к BLOCKED товару → ON_MODERATION + событие EDITED."""
    products = FakeProductRepositoryReadable()
    product_images = FakeProductImageRepository()
    product_characteristics = FakeProductCharacteristicRepository()
    outbox = FakeOutboxRepository()

    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.BLOCKED, title='Levis 501', slug='levis-501')
    product_images.add(product_id=product_id, url='/s3/levis.jpg', ordering=0)

    use_case = make_use_case(
        product_repository=products,
        product_image_repository=product_images,
        product_characteristic_repository=product_characteristics,
        outbox_repository=outbox,
    )

    response = await use_case(make_request(product_id=product_id), user)

    # Статус вернулся на повторную модерацию (исправление после блокировки).
    assert products.by_id[product_id].status == ProductStatus.ON_MODERATION
    assert len(products.updated) == 1
    assert products.updated[0].status == ProductStatus.ON_MODERATION

    # Событие EDITED в moderation.
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'EDITED'
    assert event.target_service == ServiceName.MODERATION
    assert event.idempotency_key is not None
    payload = event.payload
    assert payload['product_id'] == str(product_id)
    assert payload['seller_id'] == str(user.id)
    assert payload['title'] == 'Levis 501'
    assert len(payload['skus']) == 1
    assert payload['skus'][0]['id'] == str(response.id)


@pytest.mark.anyio
async def test_add_sku_to_hard_blocked_returns_403():
    """Добавление SKU к товару со статусом HARD_BLOCKED → SKUForbiddenError (HARD_BLOCKED код)."""
    products = FakeProductRepositoryReadable()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.HARD_BLOCKED)

    use_case = make_use_case(product_repository=products)

    with pytest.raises(SKUForbiddenError) as exc_info:
        await use_case(make_request(product_id=product_id), user)

    # Более конкретный subclass — SKUHardBlockedError
    assert isinstance(exc_info.value, SKUHardBlockedError)
    assert exc_info.value.code == 'HARD_BLOCKED'
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_missing_image_returns_400():
    """Запрос с пустым images → SKUInvalidRequestError на уровне use-case."""
    products = FakeProductRepositoryReadable()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED)

    use_case = make_use_case(product_repository=products)

    with pytest.raises(SKUImagesRequiredError):
        await use_case(make_request(product_id=product_id, images=[]), user)


@pytest.mark.anyio
async def test_product_not_found_returns_404():
    """product_id не существует → ProductNotFoundError (404)."""
    user = make_authenticated_user()
    use_case = make_use_case()

    with pytest.raises(ProductNotFoundError) as exc_info:
        await use_case(make_request(product_id=uuid4()), user)

    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_product_owned_by_another_seller_returns_403():
    """product принадлежит другому seller → 403 NOT_OWNER (защита от IDOR)."""
    products = FakeProductRepositoryReadable()
    user = make_authenticated_user()
    another_seller_id = uuid4()
    product_id = products.add(seller_id=another_seller_id, status=ProductStatus.CREATED)

    use_case = make_use_case(product_repository=products)

    with pytest.raises(SKUNotOwnerError) as exc_info:
        await use_case(make_request(product_id=product_id), user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == 'NOT_OWNER'


@pytest.mark.anyio
async def test_response_contains_active_quantity_zero_and_zero_reserved():
    """New SKU is created with active_quantity = 0 and reserved_quantity = 0."""
    products = FakeProductRepositoryReadable()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED)

    use_case = make_use_case(product_repository=products)

    response = await use_case(make_request(product_id=product_id), user)

    assert response.active_quantity == 0
    assert response.reserved_quantity == 0


@pytest.mark.anyio
async def test_sku_response_includes_stock_quantity():
    """SKUResponse contains stock_quantity = active_quantity + reserved_quantity (canon)."""
    products = FakeProductRepositoryReadable()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED)

    use_case = make_use_case(product_repository=products)

    response = await use_case(make_request(product_id=product_id), user)

    assert response.stock_quantity == 0
    assert response.stock_quantity == response.active_quantity + response.reserved_quantity


@pytest.mark.anyio
async def test_create_sku_without_cost_price_succeeds():
    """Omitting cost_price (per OpenAPI it's optional) must NOT 422 — stored as None."""
    products = FakeProductRepositoryReadable()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED)

    use_case = make_use_case(product_repository=products)

    request = SKUCreateRequestSchema(
        product_id=product_id,
        name='256GB Black',
        price=12_999_000,
        # cost_price omitted entirely
        images=[SKUImageCreateRequestSchema(url='/s3/iphone15-black-256.jpg', ordering=0)],
    )

    response = await use_case(request, user)

    assert response.cost_price is None


@pytest.mark.anyio
async def test_create_sku_with_null_cost_price_succeeds():
    """Explicit null cost_price (per OpenAPI nullable: true) must NOT 422 — stored as None."""
    products = FakeProductRepositoryReadable()
    user = make_authenticated_user()
    product_id = products.add(seller_id=user.id, status=ProductStatus.CREATED)

    use_case = make_use_case(product_repository=products)

    response = await use_case(make_request(product_id=product_id, cost_price=None), user)

    assert response.cost_price is None
