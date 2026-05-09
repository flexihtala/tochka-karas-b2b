from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from apps.auth.enums import UserRole
from apps.auth.schemas import AuthenticatedUserSchema
from apps.products.enums import ProductStatus
from apps.products.errors import ProductNotFoundError
from apps.products.schemas import ProductReadSchema, ProductUpdateSchema
from apps.skus.errors import InvalidSKURequestError, SKUForbiddenError, SKUNotFoundError
from apps.skus.schemas import (
    SKUCharacteristicReadSchema,
    SKUCharacteristicSchema,
    SKUEditRequestSchema,
    SKUImageReadSchema,
    SKUImageSchema,
    SKUReadSchema,
    SKUUpdateSchema,
)
from apps.skus.schemas.moderation import ProductModerationEventSchema
from apps.skus.use_cases import EditSKUUseCase


class FakeProductRepository:
    def __init__(self, product: ProductReadSchema | None = None):
        self.product = product
        self.updated_products: list[ProductUpdateSchema] = []

    async def get_or_none(self, id_: UUID) -> ProductReadSchema | None:
        if self.product is None or self.product.id != id_:
            return None
        return self.product

    async def update(self, data: ProductUpdateSchema) -> ProductReadSchema | None:
        self.updated_products.append(data)
        if self.product is None or self.product.id != data.id:
            return None
        update_values = data.model_dump(exclude_unset=True, exclude={'id'})
        self.product = self.product.model_copy(update=update_values)
        return self.product


class FakeSKURepository:
    def __init__(self, sku: SKUReadSchema | None = None):
        self.sku = sku
        self.updated_skus: list[SKUUpdateSchema] = []

    async def get_or_none(self, id_: UUID) -> SKUReadSchema | None:
        if self.sku is None or self.sku.id != id_:
            return None
        return self.sku

    async def update(self, data: SKUUpdateSchema) -> SKUReadSchema | None:
        self.updated_skus.append(data)
        if self.sku is None or self.sku.id != data.id:
            return None
        update_values = data.model_dump(exclude_unset=True, exclude={'id'})
        self.sku = self.sku.model_copy(update=update_values)
        return self.sku


class FakeSKUImageRepository:
    def __init__(self):
        self.created_images: list[SKUImageReadSchema] = []
        self.deleted_for: list[UUID] = []

    async def create(self, data) -> SKUImageReadSchema:
        image = SKUImageReadSchema(
            id=data.id or uuid4(),
            sku_id=data.sku_id,
            url=data.url,
            ordering=data.ordering,
        )
        self.created_images.append(image)
        return image

    async def delete_by_sku_id(self, sku_id: UUID) -> None:
        self.deleted_for.append(sku_id)
        self.created_images = [image for image in self.created_images if image.sku_id != sku_id]


class FakeSKUCharacteristicRepository:
    def __init__(self):
        self.created_characteristics: list[SKUCharacteristicReadSchema] = []
        self.deleted_for: list[UUID] = []

    async def create(self, data) -> SKUCharacteristicReadSchema:
        characteristic = SKUCharacteristicReadSchema(
            id=data.id or uuid4(),
            sku_id=data.sku_id,
            name=data.name,
            value=data.value,
        )
        self.created_characteristics.append(characteristic)
        return characteristic

    async def delete_by_sku_id(self, sku_id: UUID) -> None:
        self.deleted_for.append(sku_id)
        self.created_characteristics = [
            characteristic for characteristic in self.created_characteristics if characteristic.sku_id != sku_id
        ]


class FakeModerationRepository:
    def __init__(self):
        self.events: list[ProductModerationEventSchema] = []

    async def send_product_event(self, event: ProductModerationEventSchema) -> None:
        self.events.append(event)


def make_product(status: ProductStatus = ProductStatus.MODERATED, seller_id=None) -> ProductReadSchema:
    now = datetime.now(UTC)
    return ProductReadSchema(
        id=uuid4(),
        seller_id=seller_id or uuid4(),
        title='iPhone 15 Pro Max',
        description='Флагманский смартфон Apple',
        status=status,
        deleted=False,
        blocked=False,
        category_id=uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_sku(product_id: UUID, reserved_quantity: int = 0) -> SKUReadSchema:
    now = datetime.now(UTC)
    return SKUReadSchema(
        id=uuid4(),
        product_id=product_id,
        name='256 GB Black',
        price=100_000,
        stock_quantity=10,
        reserved_quantity=reserved_quantity,
        article='IPH15PM-256-BLK',
        cost_price=80_000,
        discount=5,
        created_at=now,
        updated_at=now,
    )


def make_request(images: list[SKUImageSchema] | None = None) -> SKUEditRequestSchema:
    return SKUEditRequestSchema(
        name='256 GB Space Black',
        price=120_000,
        stock_quantity=15,
        article='IPH15PM-256-SBLK',
        cost_price=85_000,
        discount=10,
        images=images if images is not None else [SKUImageSchema(url='/s3/sku-front-fixed.jpg', ordering=0)],
        characteristics=[SKUCharacteristicSchema(name='Цвет', value='Чёрный')],
    )


def build_use_case(
    product: ProductReadSchema,
    sku: SKUReadSchema,
):
    products = FakeProductRepository(product)
    skus = FakeSKURepository(sku)
    images = FakeSKUImageRepository()
    characteristics = FakeSKUCharacteristicRepository()
    moderation = FakeModerationRepository()
    use_case = EditSKUUseCase(
        sku_repository=skus,
        sku_image_repository=images,
        sku_characteristic_repository=characteristics,
        product_repository=products,
        moderation_repository=moderation,
    )
    return use_case, products, skus, images, characteristics, moderation


@pytest.mark.anyio
async def test_reserves_preserved_after_sku_edit():
    product = make_product(status=ProductStatus.MODERATED)
    sku = make_sku(product.id, reserved_quantity=2)
    use_case, products, skus, _, _, moderation = build_use_case(product, sku)

    result = await use_case(
        sku.id,
        make_request(),
        AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
    )

    assert result.reserved_quantity == 2
    assert skus.sku.reserved_quantity == 2
    assert result.name == '256 GB Space Black'
    assert result.price == 120_000
    assert products.product.status == ProductStatus.ON_MODERATION
    assert len(moderation.events) == 1
    assert moderation.events[0].event == 'EDITED'
    assert moderation.events[0].product_id == product.id
    assert moderation.events[0].seller_id == product.seller_id
    update_payload = skus.updated_skus[0].model_dump(exclude_unset=True)
    assert 'reserved_quantity' not in update_payload


@pytest.mark.anyio
async def test_edit_blocked_product_returns_to_on_moderation():
    product = make_product(status=ProductStatus.BLOCKED)
    sku = make_sku(product.id, reserved_quantity=3)
    use_case, products, _, _, _, moderation = build_use_case(product, sku)

    await use_case(
        sku.id,
        make_request(),
        AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
    )

    assert products.product.status == ProductStatus.ON_MODERATION
    assert len(moderation.events) == 1
    assert moderation.events[0].event == 'EDITED'


@pytest.mark.anyio
async def test_edit_hard_blocked_returns_403():
    product = make_product(status=ProductStatus.HARD_BLOCKED)
    sku = make_sku(product.id)
    use_case, products, skus, images, characteristics, moderation = build_use_case(product, sku)

    with pytest.raises(SKUForbiddenError) as exc:
        await use_case(
            sku.id,
            make_request(),
            AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
        )

    assert exc.value.status_code == 403
    assert exc.value.code == 'FORBIDDEN'
    assert exc.value.message == 'Cannot edit SKU of hard-blocked product'
    assert products.product.status == ProductStatus.HARD_BLOCKED
    assert skus.updated_skus == []
    assert images.created_images == []
    assert characteristics.created_characteristics == []
    assert moderation.events == []


@pytest.mark.anyio
async def test_edit_others_product_returns_403():
    product = make_product(status=ProductStatus.MODERATED)
    sku = make_sku(product.id)
    use_case, products, skus, _, _, moderation = build_use_case(product, sku)
    other_seller_id = uuid4()
    assert other_seller_id != product.seller_id

    with pytest.raises(SKUForbiddenError) as exc:
        await use_case(
            sku.id,
            make_request(),
            AuthenticatedUserSchema(id=other_seller_id, role=UserRole.SELLER),
        )

    assert exc.value.status_code == 403
    assert exc.value.code == 'NOT_OWNER'
    assert exc.value.message == 'SKU does not belong to the authenticated seller'
    assert products.product.status == ProductStatus.MODERATED
    assert skus.updated_skus == []
    assert moderation.events == []


@pytest.mark.anyio
async def test_edit_sku_with_created_status_does_not_emit_event():
    product = make_product(status=ProductStatus.CREATED)
    sku = make_sku(product.id)
    use_case, products, _, _, _, moderation = build_use_case(product, sku)

    result = await use_case(
        sku.id,
        make_request(),
        AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
    )

    assert result.product_id == product.id
    assert products.product.status == ProductStatus.CREATED
    assert moderation.events == []


@pytest.mark.anyio
async def test_edit_missing_sku_returns_404():
    product = make_product(status=ProductStatus.MODERATED)
    products = FakeProductRepository(product)
    skus = FakeSKURepository()
    use_case = EditSKUUseCase(
        sku_repository=skus,
        sku_image_repository=FakeSKUImageRepository(),
        sku_characteristic_repository=FakeSKUCharacteristicRepository(),
        product_repository=products,
        moderation_repository=FakeModerationRepository(),
    )

    with pytest.raises(SKUNotFoundError) as exc:
        await use_case(
            uuid4(),
            make_request(),
            AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
        )

    assert exc.value.status_code == 404
    assert exc.value.code == 'NOT_FOUND'
    assert exc.value.message == 'SKU not found'


@pytest.mark.anyio
async def test_edit_orphan_sku_returns_404():
    sku = make_sku(uuid4())
    products = FakeProductRepository()
    skus = FakeSKURepository(sku)
    use_case = EditSKUUseCase(
        sku_repository=skus,
        sku_image_repository=FakeSKUImageRepository(),
        sku_characteristic_repository=FakeSKUCharacteristicRepository(),
        product_repository=products,
        moderation_repository=FakeModerationRepository(),
    )

    with pytest.raises(ProductNotFoundError):
        await use_case(
            sku.id,
            make_request(),
            AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER),
        )


@pytest.mark.anyio
async def test_edit_empty_images_returns_400():
    product = make_product(status=ProductStatus.MODERATED)
    sku = make_sku(product.id)
    use_case, _, _, images, characteristics, moderation = build_use_case(product, sku)

    with pytest.raises(InvalidSKURequestError) as exc:
        await use_case(
            sku.id,
            make_request(images=[]),
            AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
        )

    assert exc.value.status_code == 400
    assert exc.value.message == 'At least one image is required'
    assert images.created_images == []
    assert characteristics.created_characteristics == []
    assert moderation.events == []


@pytest.mark.anyio
async def test_edit_replaces_sku_images_and_characteristics():
    product = make_product(status=ProductStatus.MODERATED)
    sku = make_sku(product.id, reserved_quantity=1)
    use_case, _, skus, images, characteristics, _ = build_use_case(product, sku)

    request = SKUEditRequestSchema(
        name='Replaced name',
        price=200_000,
        stock_quantity=20,
        article='REP-ART',
        images=[
            SKUImageSchema(url='/s3/repl-1.jpg', ordering=0),
            SKUImageSchema(url='/s3/repl-2.jpg', ordering=1),
        ],
        characteristics=[
            SKUCharacteristicSchema(name='Цвет', value='Белый'),
            SKUCharacteristicSchema(name='Память', value='256 GB'),
        ],
    )
    await use_case(
        sku.id,
        request,
        AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
    )

    assert images.deleted_for == [sku.id]
    assert characteristics.deleted_for == [sku.id]
    assert [image.url for image in images.created_images] == ['/s3/repl-1.jpg', '/s3/repl-2.jpg']
    assert [c.name for c in characteristics.created_characteristics] == ['Цвет', 'Память']
    assert skus.sku.reserved_quantity == 1
