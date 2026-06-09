from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from apps.products.enums import ProductStatus
from apps.products.use_cases.list_seller_products import ListSellerProductsUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.products.fakes import FakeProductImageRepository, FakeProductRepository


def make_user(seller_id=None) -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=seller_id or uuid4(), role=UserRole.SELLER)


def make_use_case(
    products: FakeProductRepository | None = None,
    images: FakeProductImageRepository | None = None,
) -> ListSellerProductsUseCase:
    return ListSellerProductsUseCase(
        product_repository=products or FakeProductRepository(),
        image_repository=images or FakeProductImageRepository(),
    )


@pytest.mark.anyio
async def test_list_returns_only_own_products():
    """Чужие товары не возвращаются даже в одном репозитории."""
    products = FakeProductRepository()
    seller = make_user()
    other_seller_id = uuid4()
    own_a = products.add(seller_id=seller.id, title='Мой товар A')
    own_b = products.add(seller_id=seller.id, title='Мой товар B')
    products.add(seller_id=other_seller_id, title='Чужой товар')

    use_case = make_use_case(products)
    response = await use_case(current_user=seller, limit=20, offset=0)

    returned_ids = {item.id for item in response.items}
    assert returned_ids == {own_a.id, own_b.id}
    assert response.total_count == 2
    assert response.limit == 20
    assert response.offset == 0


@pytest.mark.anyio
async def test_idor_query_param_seller_id_ignored():
    """Use case принимает seller_id ТОЛЬКО из current_user (JWT).

    Query-параметр `seller_id` не объявлен сигнатурой use case → его никак нельзя
    подсунуть, даже если бы он пришёл из роутера. Тест проверяет, что результат
    зависит исключительно от current_user.id и не меняется при попытке "указать"
    seller_id того seller-а, чьи товары мы пытаемся видеть.
    """
    products = FakeProductRepository()
    attacker = make_user()
    victim_id = uuid4()
    products.add(seller_id=victim_id, title='Товар жертвы 1')
    products.add(seller_id=victim_id, title='Товар жертвы 2')

    use_case = make_use_case(products)
    response = await use_case(current_user=attacker, limit=20, offset=0)

    # У атакующего нет товаров → пусто, несмотря на наличие чужих товаров в репозитории.
    assert response.items == []
    assert response.total_count == 0


@pytest.mark.anyio
async def test_deleted_products_visible_with_deleted_flag():
    products = FakeProductRepository()
    seller = make_user()
    products.add(seller_id=seller.id, title='Активный')
    products.add(seller_id=seller.id, title='Удалённый', deleted=True)

    use_case = make_use_case(products)

    # По умолчанию — без удалённых
    default_response = await use_case(current_user=seller, limit=20, offset=0)
    assert {item.title for item in default_response.items} == {'Активный'}
    assert default_response.total_count == 1
    assert all(item.deleted is False for item in default_response.items)

    # include_deleted=true → удалённые тоже видны
    with_deleted = await use_case(current_user=seller, limit=20, offset=0, include_deleted=True)
    assert {item.title for item in with_deleted.items} == {'Активный', 'Удалённый'}
    assert with_deleted.total_count == 2


@pytest.mark.anyio
async def test_status_filter_works_correctly():
    products = FakeProductRepository()
    seller = make_user()
    products.add(seller_id=seller.id, title='Черновик', status=ProductStatus.CREATED)
    products.add(seller_id=seller.id, title='На модерации', status=ProductStatus.ON_MODERATION)
    products.add(seller_id=seller.id, title='Одобрен', status=ProductStatus.MODERATED)

    use_case = make_use_case(products)

    moderated_only = await use_case(current_user=seller, limit=20, offset=0, status=ProductStatus.MODERATED)
    assert {item.title for item in moderated_only.items} == {'Одобрен'}
    assert moderated_only.total_count == 1

    created_only = await use_case(current_user=seller, limit=20, offset=0, status=ProductStatus.CREATED)
    assert {item.title for item in created_only.items} == {'Черновик'}
    assert created_only.total_count == 1


@pytest.mark.anyio
async def test_search_by_title_case_insensitive():
    products = FakeProductRepository()
    seller = make_user()
    products.add(seller_id=seller.id, title='iPhone 15 Pro Max')
    products.add(seller_id=seller.id, title='Samsung Galaxy S24')
    products.add(seller_id=seller.id, title='IPHONE 14')

    use_case = make_use_case(products)

    # lower-case подстрока, разные регистры в titles
    response = await use_case(current_user=seller, limit=20, offset=0, search='iphone')
    titles = {item.title for item in response.items}
    assert titles == {'iPhone 15 Pro Max', 'IPHONE 14'}
    assert response.total_count == 2

    # подстрока другим регистром
    response2 = await use_case(current_user=seller, limit=20, offset=0, search='SAMSUNG')
    assert {item.title for item in response2.items} == {'Samsung Galaxy S24'}


@pytest.mark.anyio
async def test_pagination_metadata_is_correct():
    """limit/offset/total_count отражают полную выборку; страница нужного размера."""
    products = FakeProductRepository()
    seller = make_user()
    now = datetime.now(UTC)
    for i in range(5):
        products.add(seller_id=seller.id, title=f'Продукт {i}', created_at=now + timedelta(seconds=i))

    use_case = make_use_case(products)
    page = await use_case(current_user=seller, limit=2, offset=1)

    assert page.limit == 2
    assert page.offset == 1
    assert page.total_count == 5
    assert len(page.items) == 2


@pytest.mark.anyio
async def test_list_includes_sku_aggregates():
    """DoD «Прочее»: ответ включает реальные skus_count и total_active_quantity по каждому товару.

    Агрегаты считает репозиторий (Count / Sum(active_quantity) подзапросами); use case их
    просто прокидывает. Фейк репозитория возвращает заранее заданные значения, имитируя
    результат подзапросов.
    """
    products = FakeProductRepository()
    seller = make_user()
    products.add(seller_id=seller.id, title='С тремя SKU', skus_count=3, total_active_quantity=42)
    products.add(seller_id=seller.id, title='Без SKU', skus_count=0, total_active_quantity=0)

    use_case = make_use_case(products)
    response = await use_case(current_user=seller, limit=20, offset=0)

    by_title = {item.title: item for item in response.items}
    assert by_title['С тремя SKU'].skus_count == 3
    assert by_title['С тремя SKU'].total_active_quantity == 42
    assert by_title['Без SKU'].skus_count == 0
    assert by_title['Без SKU'].total_active_quantity == 0
