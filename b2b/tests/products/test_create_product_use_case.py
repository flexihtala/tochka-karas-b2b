from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.products.enums import ProductStatus
from apps.products.errors import CategoryNotFoundError, ImagesRequiredError
from apps.products.schemas.request import (
    CharacteristicRequestSchema,
    ProductCreateRequestSchema,
    ProductImageCreateRequestSchema,
)
from apps.products.use_cases.create_product import CreateProductUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.products.fakes import (
    FakeCategoryRepository,
    FakeCharacteristicValueRepository,
    FakeProductImageRepository,
    FakeProductRepository,
)


def make_authenticated_user(role: UserRole = UserRole.SELLER) -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=role)


def make_request(
    *,
    category_id,
    title: str = 'iPhone 15 Pro Max',
    description: str = 'Флагман Apple',
    slug: str | None = None,
    images: list[ProductImageCreateRequestSchema] | None = None,
    characteristics: list[CharacteristicRequestSchema] | None = None,
) -> ProductCreateRequestSchema:
    return ProductCreateRequestSchema(
        title=title,
        description=description,
        category_id=category_id,
        slug=slug,
        images=images
        if images is not None
        else [
            ProductImageCreateRequestSchema(url='/s3/iphone15-front.jpg', ordering=0),
            ProductImageCreateRequestSchema(url='/s3/iphone15-back.jpg', ordering=1),
        ],
        characteristics=characteristics
        if characteristics is not None
        else [CharacteristicRequestSchema(name='Бренд', value='Apple')],
    )


def make_use_case(category_repo: FakeCategoryRepository | None = None) -> CreateProductUseCase:
    return CreateProductUseCase(
        product_repository=FakeProductRepository(),
        image_repository=FakeProductImageRepository(),
        characteristic_repository=FakeCharacteristicValueRepository(),
        category_repository=category_repo or FakeCategoryRepository(),
    )


@pytest.mark.anyio
async def test_create_product_returns_201_with_created_status():
    categories = FakeCategoryRepository()
    category_id = categories.add()
    use_case = make_use_case(categories)
    user = make_authenticated_user()

    response = await use_case(make_request(category_id=category_id), user)

    assert response.status == ProductStatus.CREATED
    assert response.skus == []
    assert response.deleted is False
    assert response.blocking_reason_id is None
    assert response.moderator_comment is None
    assert len(response.images) == 2
    assert {image.url for image in response.images} == {'/s3/iphone15-front.jpg', '/s3/iphone15-back.jpg'}
    assert len(response.characteristics) == 1
    assert response.characteristics[0].name == 'Бренд'
    assert response.characteristics[0].value == 'Apple'


@pytest.mark.anyio
async def test_seller_id_taken_from_jwt():
    categories = FakeCategoryRepository()
    category_id = categories.add()
    products = FakeProductRepository()
    use_case = CreateProductUseCase(
        product_repository=products,
        image_repository=FakeProductImageRepository(),
        characteristic_repository=FakeCharacteristicValueRepository(),
        category_repository=categories,
    )
    user = make_authenticated_user()

    response = await use_case(make_request(category_id=category_id), user)

    # response.seller_id is the JWT user id, NOT something from body
    assert response.seller_id == user.id
    # repository also receives the JWT seller_id
    assert products.created[0].seller_id == user.id


@pytest.mark.anyio
async def test_missing_images_returns_400():
    categories = FakeCategoryRepository()
    category_id = categories.add()
    use_case = make_use_case(categories)
    user = make_authenticated_user()

    with pytest.raises(ImagesRequiredError):
        await use_case(make_request(category_id=category_id, images=[]), user)


@pytest.mark.anyio
async def test_missing_category_returns_400():
    # When `category_id` is missing from the payload entirely, pydantic raises ValidationError (FastAPI returns 400).
    with pytest.raises(ValidationError):
        ProductCreateRequestSchema(
            title='Title',
            description='Description',
            images=[ProductImageCreateRequestSchema(url='/img.jpg', ordering=0)],
        )


@pytest.mark.anyio
async def test_invalid_category_id_returns_400():
    categories = FakeCategoryRepository()
    # do not add any category — fake says it doesn't exist
    use_case = make_use_case(categories)
    user = make_authenticated_user()

    with pytest.raises(CategoryNotFoundError):
        await use_case(make_request(category_id=uuid4()), user)
