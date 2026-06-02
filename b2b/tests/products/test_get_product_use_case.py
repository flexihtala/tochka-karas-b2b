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
    FakeSKUCharacteristicValueRepository,
    FakeSKUImageRepository,
    FakeSKURepositoryForGet,
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
    skus: FakeSKURepositoryForGet | None = None,
    sku_images: FakeSKUImageRepository | None = None,
    sku_characteristics: FakeSKUCharacteristicValueRepository | None = None,
) -> tuple[
    GetProductUseCase,
    FakeProductRepository,
    FakeProductImageRepository,
    FakeCharacteristicValueRepository,
    FakeSKURepositoryForGet,
    FakeSKUImageRepository,
    FakeSKUCharacteristicValueRepository,
]:
    products = products or FakeProductRepository()
    images = images or FakeProductImageRepository()
    characteristics = characteristics or FakeCharacteristicValueRepository()
    skus = skus or FakeSKURepositoryForGet()
    sku_images = sku_images or FakeSKUImageRepository()
    sku_characteristics = sku_characteristics or FakeSKUCharacteristicValueRepository()
    use_case = GetProductUseCase(
        product_repository=products,
        image_repository=images,
        characteristic_repository=characteristics,
        sku_repository=skus,
        sku_image_repository=sku_images,
        sku_characteristic_repository=sku_characteristics,
    )
    return use_case, products, images, characteristics, skus, sku_images, sku_characteristics


@pytest.mark.anyio
async def test_get_moderated_product_returns_full_payload():
    user = make_authenticated_user()
    use_case, products, images, characteristics, skus, sku_images, sku_characteristics = make_use_case()
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
    sku = skus.add(
        product_id=product.id,
        name='iPhone 15 Pro Max 256GB',
        price=9990000,
        cost_price=7000000,
        active_quantity=5,
        reserved_quantity=2,
        article='IP15PM-256',
    )
    sku_images.add(sku_id=sku.id, url='/s3/sku-256-front.jpg', ordering=0)
    sku_characteristics.add(sku_id=sku.id, name='Память', value='256 ГБ')

    response = await use_case(product.id, user)

    assert response.id == product.id
    assert response.seller_id == user.id
    assert response.status == ProductStatus.MODERATED
    assert response.deleted is False
    # ProductDetailResponse: плоских legacy-полей нет, есть blocked/blocking_reason/field_reports
    assert response.blocked is False
    assert response.blocking_reason is None
    assert response.field_reports == []
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
    # SKU подгружены через _load_skus (US-B2B-05 review): продавец видит варианты
    assert len(response.skus) == 1
    sku_response = response.skus[0]
    assert sku_response.id == sku.id
    assert sku_response.product_id == product.id
    assert sku_response.name == 'iPhone 15 Pro Max 256GB'
    assert sku_response.price == 9990000
    assert sku_response.cost_price == 7000000
    assert sku_response.active_quantity == 5
    assert sku_response.reserved_quantity == 2
    # stock_quantity = active + reserved (canonical invariant)
    assert sku_response.stock_quantity == 7
    assert sku_response.article == 'IP15PM-256'
    assert [image.url for image in sku_response.images] == ['/s3/sku-256-front.jpg']
    assert len(sku_response.characteristics) == 1
    assert sku_response.characteristics[0].name == 'Память'
    assert sku_response.characteristics[0].value == '256 ГБ'


@pytest.mark.anyio
async def test_get_blocked_product_returns_blocking_reason_and_field_reports():
    """BLOCKED товар собственного продавца.

    Per openapi ProductDetailResponse: blocked=true, blocking_reason — объект
    {id, title, comment}, field_reports — массив FieldReport. title/field_reports
    заполняются flow модерации (US-B2B-09); тут сидируем их через fake-repo.
    """
    user = make_authenticated_user()
    blocking_reason_id = uuid4()
    sku_id = uuid4()
    use_case, products, _, _, _, _, _ = make_use_case()
    product = products.add(
        seller_id=user.id,
        status=ProductStatus.BLOCKED,
        blocking_reason_id=blocking_reason_id,
        blocking_reason_title='Запрещённый товар',
        moderator_comment='Несоответствие описания и фотографий',
        field_reports=[
            {'field_name': 'title', 'sku_id': None, 'comment': 'Вводит в заблуждение'},
            {'field_name': 'price', 'sku_id': str(sku_id), 'comment': 'Завышена'},
        ],
    )

    response = await use_case(product.id, user)

    assert response.status == ProductStatus.BLOCKED
    assert response.blocked is True
    assert response.blocking_reason is not None
    assert response.blocking_reason.id == blocking_reason_id
    assert response.blocking_reason.title == 'Запрещённый товар'
    assert response.blocking_reason.comment == 'Несоответствие описания и фотографий'
    assert len(response.field_reports) == 2
    assert response.field_reports[0].field_name == 'title'
    assert response.field_reports[0].sku_id is None
    assert response.field_reports[0].comment == 'Вводит в заблуждение'
    assert response.field_reports[1].field_name == 'price'
    assert response.field_reports[1].sku_id == sku_id
    assert response.field_reports[1].comment == 'Завышена'


@pytest.mark.anyio
async def test_get_hard_blocked_product_is_blocked_with_reason():
    """HARD_BLOCKED тоже отдаёт blocked=true и объект blocking_reason."""
    user = make_authenticated_user()
    blocking_reason_id = uuid4()
    use_case, products, _, _, _, _, _ = make_use_case()
    product = products.add(
        seller_id=user.id,
        status=ProductStatus.HARD_BLOCKED,
        blocking_reason_id=blocking_reason_id,
        blocking_reason_title='Контрафакт',
        moderator_comment='Жёсткая блокировка',
    )

    response = await use_case(product.id, user)

    assert response.blocked is True
    assert response.blocking_reason is not None
    assert response.blocking_reason.id == blocking_reason_id
    assert response.blocking_reason.title == 'Контрафакт'


@pytest.mark.anyio
async def test_get_moderated_product_without_skus_returns_empty_list():
    """MODERATED товар без SKU → skus=[] (не None), blocking_reason=None."""
    user = make_authenticated_user()
    use_case, products, _, _, _, _, _ = make_use_case()
    product = products.add(seller_id=user.id, status=ProductStatus.MODERATED)

    response = await use_case(product.id, user)

    assert response.skus == []
    assert response.blocked is False
    assert response.blocking_reason is None


@pytest.mark.anyio
async def test_get_others_product_returns_404():
    """Чужой товар → 404 NOT_FOUND, НЕ 403 (canon: защита от IDOR-by-discovery).

    Это сознательное решение: 403 раскрыл бы факт существования чужого
    товара, и клиент мог бы перебором UUID составить карту принадлежности.
    """
    seller = make_authenticated_user()
    another_seller_id = uuid4()
    use_case, products, _, _, _, _, _ = make_use_case()
    other_product = products.add(seller_id=another_seller_id, status=ProductStatus.MODERATED)

    with pytest.raises(ProductNotFoundError) as exc_info:
        await use_case(other_product.id, seller)

    assert exc_info.value.code == 'NOT_FOUND'
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_get_nonexistent_returns_404():
    user = make_authenticated_user()
    use_case, _, _, _, _, _, _ = make_use_case()

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
    use_case, products, _, _, _, _, _ = make_use_case()
    product = products.add(seller_id=user.id, status=ProductStatus.MODERATED, deleted=True)

    response = await use_case(product.id, user)

    assert response.id == product.id
    assert response.deleted is True


@pytest.mark.anyio
async def test_get_returns_only_own_product_images_and_characteristics():
    """Защита от утечки данных: возвращаются только изображения/характеристики
    запрашиваемого товара, даже если в репозитории есть данные других товаров."""
    user = make_authenticated_user()
    use_case, products, images, characteristics, skus, _, _ = make_use_case()
    product = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    other_product = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    images.add(product_id=product.id, url='/s3/own.jpg', ordering=0)
    images.add(product_id=other_product.id, url='/s3/other.jpg', ordering=0)
    characteristics.add(product_id=product.id, name='Бренд', value='Apple')
    characteristics.add(product_id=other_product.id, name='Бренд', value='Samsung')
    skus.add(product_id=product.id, name='Own SKU')
    skus.add(product_id=other_product.id, name='Other SKU')

    response = await use_case(product.id, user)

    assert [image.url for image in response.images] == ['/s3/own.jpg']
    assert [c.value for c in response.characteristics] == ['Apple']
    assert [sku.name for sku in response.skus] == ['Own SKU']
