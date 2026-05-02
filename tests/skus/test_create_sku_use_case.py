from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from apps.auth.enums import UserRole
from apps.auth.schemas import AuthenticatedUserSchema
from apps.products.enums import ProductStatus
from apps.products.schemas import ProductReadSchema, ProductUpdateSchema
from apps.skus.errors import InvalidSKURequestError, SKUForbiddenError
from apps.skus.schemas import (
    SKUCharacteristicReadSchema,
    SKUCreateRequestSchema,
    SKUImageReadSchema,
    SKUImageSchema,
    SKUReadSchema,
)
from apps.skus.schemas.moderation import ProductModerationEventSchema
from apps.skus.use_cases import CreateSKUUseCase


class FakeProductRepository:
    def __init__(self, product: ProductReadSchema):
        self.product = product
        self.updated_products: list[ProductUpdateSchema] = []

    async def get_or_none(self, id_: UUID) -> ProductReadSchema | None:
        return self.product if self.product.id == id_ else None

    async def update(self, data: ProductUpdateSchema) -> ProductReadSchema:
        self.updated_products.append(data)
        self.product = self.product.model_copy(update={'status': data.status})
        return self.product


class FakeSKURepository:
    def __init__(self, existing_count: int = 0):
        self.existing_count = existing_count
        self.created_skus: list[SKUReadSchema] = []

    async def count_by_product_id(self, product_id: UUID) -> int:
        return self.existing_count

    async def create(self, data) -> SKUReadSchema:
        now = datetime.now(UTC)
        sku = SKUReadSchema(
            id=data.id or uuid4(),
            product_id=data.product_id,
            name=data.name,
            price=data.price,
            stock_quantity=data.stock_quantity,
            article=data.article,
            cost_price=data.cost_price,
            discount=data.discount,
            created_at=now,
            updated_at=now,
        )
        self.created_skus.append(sku)
        return sku


class FakeSKUImageRepository:
    def __init__(self):
        self.created_images: list[SKUImageReadSchema] = []

    async def create(self, data) -> SKUImageReadSchema:
        image = SKUImageReadSchema(
            id=data.id or uuid4(),
            sku_id=data.sku_id,
            url=data.url,
            ordering=data.ordering,
        )
        self.created_images.append(image)
        return image


class FakeSKUCharacteristicRepository:
    def __init__(self):
        self.created_characteristics: list[SKUCharacteristicReadSchema] = []

    async def create(self, data) -> SKUCharacteristicReadSchema:
        characteristic = SKUCharacteristicReadSchema(
            id=data.id or uuid4(),
            sku_id=data.sku_id,
            name=data.name,
            value=data.value,
        )
        self.created_characteristics.append(characteristic)
        return characteristic


class FakeModerationRepository:
    def __init__(self):
        self.events: list[ProductModerationEventSchema] = []

    async def send_product_event(self, event: ProductModerationEventSchema) -> None:
        self.events.append(event)


def make_product(status: ProductStatus = ProductStatus.CREATED) -> ProductReadSchema:
    now = datetime.now(UTC)
    return ProductReadSchema(
        id=uuid4(),
        seller_id=uuid4(),
        title='iPhone 15 Pro Max',
        description='Флагманский смартфон Apple',
        status=status,
        deleted=False,
        blocked=False,
        category_id=uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_request(product_id: UUID, images: list[SKUImageSchema] | None = None) -> SKUCreateRequestSchema:
    return SKUCreateRequestSchema(
        product_id=product_id,
        name='256 GB Black',
        price=100_000,
        stock_quantity=5,
        article='IPH15PM-256-BLK',
        cost_price=80_000,
        discount=5,
        images=images if images is not None else [SKUImageSchema(url='/s3/sku-front.jpg', ordering=0)],
        characteristics=[],
    )


def make_use_case(
    product_repository: FakeProductRepository,
    sku_repository: FakeSKURepository | None = None,
    sku_image_repository: FakeSKUImageRepository | None = None,
    sku_characteristic_repository: FakeSKUCharacteristicRepository | None = None,
    moderation_repository: FakeModerationRepository | None = None,
) -> tuple[
    CreateSKUUseCase,
    FakeSKURepository,
    FakeSKUImageRepository,
    FakeSKUCharacteristicRepository,
    FakeModerationRepository,
]:
    skus = sku_repository or FakeSKURepository()
    images = sku_image_repository or FakeSKUImageRepository()
    characteristics = sku_characteristic_repository or FakeSKUCharacteristicRepository()
    moderation = moderation_repository or FakeModerationRepository()
    return (
        CreateSKUUseCase(
            sku_repository=skus,
            sku_image_repository=images,
            sku_characteristic_repository=characteristics,
            product_repository=product_repository,
            moderation_repository=moderation,
        ),
        skus,
        images,
        characteristics,
        moderation,
    )


@pytest.mark.anyio
async def test_first_sku_transitions_product_to_on_moderation():
    product = make_product()
    products = FakeProductRepository(product)
    use_case, skus, images, _, _ = make_use_case(products)

    result = await use_case(
        make_request(product.id),
        AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
    )

    assert result.product_id == product.id
    assert result.images[0].id == images.created_images[0].id
    assert images.created_images[0].sku_id == skus.created_skus[0].id
    assert products.updated_products[0].status == ProductStatus.ON_MODERATION
    assert products.product.status == ProductStatus.ON_MODERATION


@pytest.mark.anyio
async def test_first_sku_emits_created_event_to_moderation():
    product = make_product()
    products = FakeProductRepository(product)
    use_case, _, _, _, moderation = make_use_case(products)

    await use_case(
        make_request(product.id),
        AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
    )

    assert len(moderation.events) == 1
    event = moderation.events[0]
    assert event.product_id == product.id
    assert event.seller_id == product.seller_id
    assert event.event == 'CREATED'
    assert event.idempotency_key
    assert event.date.endswith('Z')


@pytest.mark.anyio
async def test_second_sku_no_state_change():
    product = make_product(status=ProductStatus.ON_MODERATION)
    products = FakeProductRepository(product)
    use_case, _, _, _, moderation = make_use_case(products, sku_repository=FakeSKURepository(existing_count=1))

    await use_case(
        make_request(product.id),
        AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
    )

    assert products.updated_products == []
    assert moderation.events == []
    assert products.product.status == ProductStatus.ON_MODERATION


@pytest.mark.anyio
async def test_add_sku_to_hard_blocked_returns_403():
    product = make_product(status=ProductStatus.HARD_BLOCKED)
    products = FakeProductRepository(product)
    use_case, skus, images, characteristics, moderation = make_use_case(products)

    with pytest.raises(SKUForbiddenError) as exc:
        await use_case(
            make_request(product.id),
            AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
        )

    assert exc.value.status_code == 403
    assert skus.created_skus == []
    assert images.created_images == []
    assert characteristics.created_characteristics == []
    assert moderation.events == []


@pytest.mark.anyio
async def test_missing_image_returns_400():
    product = make_product()
    products = FakeProductRepository(product)
    use_case, skus, images, characteristics, moderation = make_use_case(products)

    with pytest.raises(InvalidSKURequestError) as exc:
        await use_case(
            make_request(product.id, images=[]),
            AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
        )

    assert exc.value.status_code == 400
    assert exc.value.message == 'At least one image is required'
    assert skus.created_skus == []
    assert images.created_images == []
    assert characteristics.created_characteristics == []
    assert moderation.events == []
