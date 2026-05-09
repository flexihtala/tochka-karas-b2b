from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.auth.enums import UserRole
from apps.auth.schemas.token import AuthenticatedUserSchema
from apps.products.enums import ProductStatus
from apps.products.errors import (
    InvalidProductRequestError,
    ProductForbiddenError,
    ProductNotFoundError,
)
from apps.products.schemas.category import CategoryReadSchema
from apps.products.schemas.product import ProductReadSchema
from apps.products.schemas.request import (
    ProductCharacteristicRequestSchema,
    ProductEditRequestSchema,
    ProductImageRequestSchema,
)
from apps.products.use_cases import EditProductUseCase
from apps.skus.schemas.moderation import ProductModerationEventSchema
from tests.products.fakes import (
    FakeCategoryRepository,
    FakeProductCharacteristicRepository,
    FakeProductImageRepository,
    FakeProductRepository,
)


class FakeModerationRepository:
    def __init__(self):
        self.events: list[ProductModerationEventSchema] = []

    async def send_product_event(self, event: ProductModerationEventSchema) -> None:
        self.events.append(event)


def make_product(
    seller_id=None,
    status: ProductStatus = ProductStatus.MODERATED,
    category_id=None,
) -> ProductReadSchema:
    now = datetime.now(UTC)
    return ProductReadSchema(
        id=uuid4(),
        seller_id=seller_id or uuid4(),
        title='iPhone 15 Pro Max',
        description='Флагманский смартфон Apple',
        status=status,
        deleted=False,
        blocked=False,
        category_id=category_id or uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_request(category_id) -> ProductEditRequestSchema:
    return ProductEditRequestSchema(
        title='iPhone 15 Pro Max — обновлённое название',
        description='Обновлённое описание после правок модератора',
        category_id=str(category_id),
        images=[ProductImageRequestSchema(url='/s3/iphone15-front-fixed.jpg', ordering=0)],
        characteristics=[ProductCharacteristicRequestSchema(name='Бренд', value='Apple')],
    )


def make_use_case(
    products: FakeProductRepository,
    categories: FakeCategoryRepository | None = None,
    images: FakeProductImageRepository | None = None,
    characteristics: FakeProductCharacteristicRepository | None = None,
    moderation: FakeModerationRepository | None = None,
):
    return (
        EditProductUseCase(
            product_repository=products,
            product_image_repository=images or FakeProductImageRepository(),
            product_characteristic_repository=characteristics or FakeProductCharacteristicRepository(),
            category_repository=categories or FakeCategoryRepository(),
            moderation_repository=moderation or FakeModerationRepository(),
        ),
        images,
        characteristics,
        moderation,
    )


def setup_product(status: ProductStatus, seller_id=None):
    product = make_product(seller_id=seller_id, status=status)
    products = FakeProductRepository()
    products.add(product)
    category = CategoryReadSchema(id=product.category_id, name='iOS')
    categories = FakeCategoryRepository()
    categories.add(category)
    return product, products, categories


@pytest.mark.anyio
async def test_edit_moderated_product_returns_to_on_moderation():
    product, products, categories = setup_product(ProductStatus.MODERATED)
    images = FakeProductImageRepository()
    characteristics = FakeProductCharacteristicRepository()
    moderation = FakeModerationRepository()
    use_case, _, _, _ = make_use_case(
        products=products,
        categories=categories,
        images=images,
        characteristics=characteristics,
        moderation=moderation,
    )

    result = await use_case(
        product.id,
        make_request(product.category_id),
        AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
    )

    assert result.status == ProductStatus.ON_MODERATION
    assert products.products[product.id].status == ProductStatus.ON_MODERATION
    assert len(moderation.events) == 1
    event = moderation.events[0]
    assert event.product_id == product.id
    assert event.seller_id == product.seller_id
    assert event.event == 'EDITED'
    assert event.idempotency_key
    assert event.date.endswith('Z')
    assert images.deleted_for == [product.id]
    assert characteristics.deleted_for == [product.id]


@pytest.mark.anyio
async def test_edit_blocked_product_returns_to_on_moderation():
    product, products, categories = setup_product(ProductStatus.BLOCKED)
    moderation = FakeModerationRepository()
    use_case, _, _, _ = make_use_case(
        products=products,
        categories=categories,
        moderation=moderation,
    )

    result = await use_case(
        product.id,
        make_request(product.category_id),
        AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
    )

    assert result.status == ProductStatus.ON_MODERATION
    assert products.products[product.id].status == ProductStatus.ON_MODERATION
    assert len(moderation.events) == 1
    assert moderation.events[0].event == 'EDITED'


@pytest.mark.anyio
async def test_edit_hard_blocked_returns_403():
    product, products, categories = setup_product(ProductStatus.HARD_BLOCKED)
    images = FakeProductImageRepository()
    characteristics = FakeProductCharacteristicRepository()
    moderation = FakeModerationRepository()
    use_case, _, _, _ = make_use_case(
        products=products,
        categories=categories,
        images=images,
        characteristics=characteristics,
        moderation=moderation,
    )

    with pytest.raises(ProductForbiddenError) as exc:
        await use_case(
            product.id,
            make_request(product.category_id),
            AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
        )

    assert exc.value.status_code == 403
    assert exc.value.code == 'FORBIDDEN'
    assert exc.value.message == 'Cannot edit hard-blocked product'
    assert products.products[product.id].status == ProductStatus.HARD_BLOCKED
    assert images.created_images == []
    assert characteristics.created_characteristics == []
    assert moderation.events == []


@pytest.mark.anyio
async def test_edit_others_product_returns_403():
    product, products, categories = setup_product(ProductStatus.MODERATED)
    moderation = FakeModerationRepository()
    use_case, _, _, _ = make_use_case(
        products=products,
        categories=categories,
        moderation=moderation,
    )
    other_seller_id = uuid4()
    assert other_seller_id != product.seller_id

    with pytest.raises(ProductForbiddenError) as exc:
        await use_case(
            product.id,
            make_request(product.category_id),
            AuthenticatedUserSchema(id=other_seller_id, role=UserRole.SELLER),
        )

    assert exc.value.status_code == 403
    assert exc.value.code == 'NOT_OWNER'
    assert exc.value.message == 'Product does not belong to the authenticated seller'
    assert products.products[product.id].status == ProductStatus.MODERATED
    assert moderation.events == []


@pytest.mark.anyio
async def test_edit_on_moderation_status_does_not_emit_event():
    product, products, categories = setup_product(ProductStatus.ON_MODERATION)
    moderation = FakeModerationRepository()
    use_case, _, _, _ = make_use_case(
        products=products,
        categories=categories,
        moderation=moderation,
    )

    result = await use_case(
        product.id,
        make_request(product.category_id),
        AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
    )

    assert result.status == ProductStatus.ON_MODERATION
    assert moderation.events == []


@pytest.mark.anyio
async def test_edit_created_status_does_not_emit_event():
    product, products, categories = setup_product(ProductStatus.CREATED)
    moderation = FakeModerationRepository()
    use_case, _, _, _ = make_use_case(
        products=products,
        categories=categories,
        moderation=moderation,
    )

    result = await use_case(
        product.id,
        make_request(product.category_id),
        AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
    )

    assert result.status == ProductStatus.CREATED
    assert moderation.events == []


@pytest.mark.anyio
async def test_edit_missing_product_returns_404():
    products = FakeProductRepository()
    categories = FakeCategoryRepository()
    use_case, _, _, _ = make_use_case(products=products, categories=categories)

    with pytest.raises(ProductNotFoundError) as exc:
        await use_case(
            uuid4(),
            make_request(uuid4()),
            AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER),
        )

    assert exc.value.status_code == 404
    assert exc.value.code == 'NOT_FOUND'
    assert exc.value.message == 'Product not found'


@pytest.mark.anyio
async def test_edit_replaces_images_and_characteristics():
    product, products, categories = setup_product(ProductStatus.CREATED)
    images = FakeProductImageRepository()
    characteristics = FakeProductCharacteristicRepository()
    use_case, _, _, _ = make_use_case(
        products=products,
        categories=categories,
        images=images,
        characteristics=characteristics,
    )

    request = ProductEditRequestSchema(
        title='New title',
        description='New long description for product',
        category_id=str(product.category_id),
        images=[
            ProductImageRequestSchema(url='/s3/new-1.jpg', ordering=0),
            ProductImageRequestSchema(url='/s3/new-2.jpg', ordering=1),
        ],
        characteristics=[
            ProductCharacteristicRequestSchema(name='Color', value='Black'),
            ProductCharacteristicRequestSchema(name='RAM', value='8 GB'),
        ],
    )
    await use_case(
        product.id,
        request,
        AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
    )

    assert images.deleted_for == [product.id]
    assert characteristics.deleted_for == [product.id]
    assert [image.url for image in images.created_images] == ['/s3/new-1.jpg', '/s3/new-2.jpg']
    assert [c.name for c in characteristics.created_characteristics] == ['Color', 'RAM']


@pytest.mark.anyio
async def test_edit_empty_images_returns_400():
    product, products, categories = setup_product(ProductStatus.MODERATED)
    use_case, _, _, _ = make_use_case(products=products, categories=categories)

    request = make_request(product.category_id)
    request.images = []

    with pytest.raises(InvalidProductRequestError) as exc:
        await use_case(
            product.id,
            request,
            AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
        )

    assert exc.value.message == 'At least one image is required'


@pytest.mark.anyio
async def test_edit_unknown_category_returns_400():
    product, products, _ = setup_product(ProductStatus.MODERATED)
    categories = FakeCategoryRepository()
    use_case, _, _, _ = make_use_case(products=products, categories=categories)

    with pytest.raises(InvalidProductRequestError) as exc:
        await use_case(
            product.id,
            make_request(uuid4()),
            AuthenticatedUserSchema(id=product.seller_id, role=UserRole.SELLER),
        )

    assert exc.value.message == 'Category not found'
