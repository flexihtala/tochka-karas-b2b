from uuid import uuid4

import pytest

from apps.products.enums import ProductStatus
from apps.products.errors import ProductNotFoundError
from apps.products.use_cases.get_product import GetProductUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.products.fakes import (
    FakeCharacteristicValueRepository,
    FakeProductImageRepository,
    FakeProductRepository,
)


def make_authenticated_user(
    *,
    id_=None,
    role: UserRole = UserRole.SELLER,
) -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=id_ or uuid4(), role=role)


def make_use_case(
    products: FakeProductRepository | None = None,
    images: FakeProductImageRepository | None = None,
    characteristics: FakeCharacteristicValueRepository | None = None,
) -> tuple[
    GetProductUseCase,
    FakeProductRepository,
    FakeProductImageRepository,
    FakeCharacteristicValueRepository,
]:
    products = products or FakeProductRepository()
    images = images or FakeProductImageRepository()
    characteristics = characteristics or FakeCharacteristicValueRepository()
    use_case = GetProductUseCase(
        product_repository=products,
        image_repository=images,
        characteristic_repository=characteristics,
    )
    return use_case, products, images, characteristics


@pytest.mark.anyio
async def test_get_moderated_product_returns_full_payload():
    user = make_authenticated_user()
    use_case, products, images, characteristics = make_use_case()
    product = products.add(
        seller_id=user.id,
        status=ProductStatus.MODERATED,
        title='iPhone 15 Pro Max',
        slug='iphone-15-pro-max',
        description='Флагман Apple',
    )
    images.add(product_id=product.id, url='/s3/iphone15-front.jpg', ordering=0)
    images.add(product_id=product.id, url='/s3/iphone15-back.jpg', ordering=1)
    characteristics.add(product_id=product.id, name='Бренд', value='Apple')

    response = await use_case(product.id, user)

    assert response.id == product.id
    assert response.seller_id == user.id
    assert response.status == ProductStatus.MODERATED
    assert response.deleted is False
    assert response.blocking_reason_id is None
    assert response.moderator_comment is None
    assert response.title == 'iPhone 15 Pro Max'
    assert response.slug == 'iphone-15-pro-max'
    assert response.description == 'Флагман Apple'
    # images отсортированы по ordering и оба переданы в ответ
    assert [image.url for image in response.images] == [
        '/s3/iphone15-front.jpg',
        '/s3/iphone15-back.jpg',
    ]
    assert len(response.characteristics) == 1
    assert response.characteristics[0].name == 'Бренд'
    assert response.characteristics[0].value == 'Apple'
    # SKU модель не в main → пустой список (placeholder, см. PR body)
    assert response.skus == []


@pytest.mark.anyio
async def test_get_blocked_product_returns_blocking_reason_and_field_reports():
    """BLOCKED товар собственного продавца.

    Адаптация per US-spec: field_reports пока нет в модели Product (PR #?),
    поэтому проверяем blocking_reason_id и moderator_comment. Когда
    добавим ProductFieldReport — расширим этот тест полем response.field_reports.
    """
    user = make_authenticated_user()
    blocking_reason_id = uuid4()
    use_case, products, _, _ = make_use_case()
    product = products.add(
        seller_id=user.id,
        status=ProductStatus.BLOCKED,
        blocking_reason_id=blocking_reason_id,
        moderator_comment='Несоответствие описания и фотографий',
    )

    response = await use_case(product.id, user)

    assert response.status == ProductStatus.BLOCKED
    assert response.blocking_reason_id == blocking_reason_id
    assert response.moderator_comment == 'Несоответствие описания и фотографий'


@pytest.mark.anyio
async def test_get_others_product_returns_404():
    """Чужой товар → 404 NOT_FOUND, НЕ 403 (canon: защита от IDOR-by-discovery).

    Это сознательное решение: 403 раскрыл бы факт существования чужого
    товара, и клиент мог бы перебором UUID составить карту принадлежности.
    """
    seller = make_authenticated_user()
    another_seller_id = uuid4()
    use_case, products, _, _ = make_use_case()
    other_product = products.add(seller_id=another_seller_id, status=ProductStatus.MODERATED)

    with pytest.raises(ProductNotFoundError) as exc_info:
        await use_case(other_product.id, seller)

    assert exc_info.value.code == 'NOT_FOUND'
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_get_nonexistent_returns_404():
    user = make_authenticated_user()
    use_case, _, _, _ = make_use_case()

    with pytest.raises(ProductNotFoundError) as exc_info:
        await use_case(uuid4(), user)

    assert exc_info.value.code == 'NOT_FOUND'
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_soft_deleted_product_visible_to_owner_with_deleted_flag():
    """Soft-deleted товар продолжает быть виден владельцу (deleted=true в ответе).

    Согласно спеку: владелец видит свой удалённый товар без extra-флагов —
    данные принадлежат ему. B2C-режим фильтрует deleted=true отдельно.
    """
    user = make_authenticated_user()
    use_case, products, _, _ = make_use_case()
    product = products.add(seller_id=user.id, status=ProductStatus.MODERATED, deleted=True)

    response = await use_case(product.id, user)

    assert response.id == product.id
    assert response.deleted is True


@pytest.mark.anyio
async def test_get_returns_only_own_product_images_and_characteristics():
    """Защита от утечки данных: возвращаются только изображения/характеристики
    запрашиваемого товара, даже если в репозитории есть данные других товаров."""
    user = make_authenticated_user()
    use_case, products, images, characteristics = make_use_case()
    product = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    other_product = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    images.add(product_id=product.id, url='/s3/own.jpg', ordering=0)
    images.add(product_id=other_product.id, url='/s3/other.jpg', ordering=0)
    characteristics.add(product_id=product.id, name='Бренд', value='Apple')
    characteristics.add(product_id=other_product.id, name='Бренд', value='Samsung')

    response = await use_case(product.id, user)

    assert [image.url for image in response.images] == ['/s3/own.jpg']
    assert [c.value for c in response.characteristics] == ['Apple']
