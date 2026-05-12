from uuid import uuid4

import pytest

from apps.auth.enums import UserRole
from apps.auth.schemas.token import AuthenticatedUserSchema
from apps.products.enums import ProductStatus
from apps.products.errors import InvalidProductRequestError
from apps.products.schemas.category import CategoryReadSchema
from apps.products.schemas.request import (
    ProductCharacteristicRequestSchema,
    ProductCreateRequestSchema,
    ProductImageRequestSchema,
)
from apps.products.use_cases.create_product import CreateProductUseCase
from tests.products.fakes import (
    FakeCategoryRepository,
    FakeProductCharacteristicRepository,
    FakeProductImageRepository,
    FakeProductRepository,
)


def product_request(category_id: str) -> ProductCreateRequestSchema:
    return ProductCreateRequestSchema(
        title='iPhone 15 Pro Max',
        description='Флагманский смартфон Apple 2024 года с чипом A17 Pro',
        category_id=category_id,
        images=[ProductImageRequestSchema(url='/s3/iphone15-front.jpg', ordering=0)],
        characteristics=[ProductCharacteristicRequestSchema(name='Бренд', value='Apple')],
    )


def create_use_case(
    products: FakeProductRepository | None = None,
    categories: FakeCategoryRepository | None = None,
    images: FakeProductImageRepository | None = None,
    characteristics: FakeProductCharacteristicRepository | None = None,
) -> CreateProductUseCase:
    return CreateProductUseCase(
        product_repository=products or FakeProductRepository(),
        product_image_repository=images or FakeProductImageRepository(),
        product_characteristic_repository=characteristics or FakeProductCharacteristicRepository(),
        category_repository=categories or FakeCategoryRepository(),
    )


@pytest.mark.anyio
async def test_create_product_returns_201_with_created_status():
    seller_id = uuid4()
    category = CategoryReadSchema(id=uuid4(), name='iOS')
    categories = FakeCategoryRepository()
    categories.add(category)
    products = FakeProductRepository()
    images = FakeProductImageRepository()
    characteristics = FakeProductCharacteristicRepository()
    use_case = create_use_case(
        products=products,
        categories=categories,
        images=images,
        characteristics=characteristics,
    )

    result = await use_case(
        product_request(str(category.id)),
        AuthenticatedUserSchema(id=seller_id, role=UserRole.SELLER),
    )

    assert result.status == ProductStatus.CREATED
    assert result.seller_id == seller_id
    assert result.category_id == category.id
    assert result.skus == []
    assert result.images[0].url == '/s3/iphone15-front.jpg'
    assert result.images[0].ordering == 0
    assert result.characteristics[0].name == 'Бренд'
    assert images.created_images[0].product_id == result.id
    assert characteristics.created_characteristics[0].product_id == result.id
    assert result.created_at is not None
    assert result.updated_at is not None


@pytest.mark.anyio
async def test_seller_id_taken_from_jwt():
    seller_id_from_jwt = uuid4()
    seller_id_from_body = uuid4()
    category = CategoryReadSchema(id=uuid4(), name='iOS')
    categories = FakeCategoryRepository()
    categories.add(category)
    products = FakeProductRepository()
    use_case = create_use_case(products=products, categories=categories)
    request = product_request(str(category.id))
    request_data = request.model_dump()
    request_data['seller_id'] = str(seller_id_from_body)

    await use_case(
        ProductCreateRequestSchema.model_validate(request_data),
        AuthenticatedUserSchema(id=seller_id_from_jwt, role=UserRole.SELLER),
    )

    assert products.created_product is not None
    assert products.created_product.seller_id == seller_id_from_jwt
    assert products.created_product.seller_id != seller_id_from_body


@pytest.mark.anyio
async def test_missing_images_returns_400():
    category = CategoryReadSchema(id=uuid4(), name='iOS')
    categories = FakeCategoryRepository()
    categories.add(category)
    use_case = create_use_case(categories=categories)
    request = product_request(str(category.id))
    request.images = []

    with pytest.raises(InvalidProductRequestError) as exc:
        await use_case(request, AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER))

    assert exc.value.code == 'INVALID_REQUEST'
    assert exc.value.status_code == 400
    assert exc.value.message == 'At least one image is required'


@pytest.mark.anyio
async def test_missing_category_returns_400():
    use_case = create_use_case()
    request = product_request(str(uuid4()))
    request.category_id = None

    with pytest.raises(InvalidProductRequestError) as exc:
        await use_case(request, AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER))

    assert exc.value.code == 'INVALID_REQUEST'
    assert exc.value.status_code == 400
    assert exc.value.message == 'category_id is required'


@pytest.mark.anyio
async def test_invalid_category_id_returns_400():
    use_case = create_use_case()
    request = product_request('not-a-uuid')

    with pytest.raises(InvalidProductRequestError) as exc:
        await use_case(request, AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER))

    assert exc.value.code == 'INVALID_REQUEST'
    assert exc.value.status_code == 400
    assert exc.value.message == 'category_id must be a valid UUID'
