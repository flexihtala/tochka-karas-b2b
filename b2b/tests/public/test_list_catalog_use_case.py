"""DoD-тесты US-B2B-07: листинг public-каталога (короткие карточки + фильтры/сортировка).

Покрывают условия видимости, формат коротких карточек (min_price/cover_image),
фильтры (category/price/seller/характеристики) и сортировку.
"""

from uuid import uuid4

import pytest

from apps.products.enums import ProductStatus
from apps.public.enums import CatalogSort
from apps.public.use_cases.list_catalog import ListCatalogUseCase
from tests.public.fakes import (
    FakePublicCatalogRepository,
    _make_sku,
    make_characteristic,
    make_image,
    past,
)


def _make_use_case(repo: FakePublicCatalogRepository | None = None) -> ListCatalogUseCase:
    return ListCatalogUseCase(repository=repo or FakePublicCatalogRepository())


@pytest.mark.anyio
async def test_catalog_returns_moderated_in_stock_products():
    """В выдачу попадают только MODERATED + not deleted + есть SKU active_quantity > 0."""
    repo = FakePublicCatalogRepository()
    visible = repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=10)
    repo.add_product(status=ProductStatus.CREATED, with_sku_active_quantity=10)  # не MODERATED
    repo.add_product(status=ProductStatus.ON_MODERATION, with_sku_active_quantity=10)
    repo.add_product(status=ProductStatus.MODERATED, deleted=True, with_sku_active_quantity=10)  # deleted
    repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=0)  # нет остатка

    response = await _make_use_case(repo)()

    assert response.total_count == 1
    assert len(response.items) == 1
    assert response.items[0].id == visible.id
    assert response.items[0].status == ProductStatus.MODERATED


@pytest.mark.anyio
async def test_catalog_excludes_hard_blocked():
    """HARD_BLOCKED не попадает в каталог (технически отсекается по status != MODERATED)."""
    repo = FakePublicCatalogRepository()
    repo.add_product(status=ProductStatus.HARD_BLOCKED, with_sku_active_quantity=10)
    repo.add_product(status=ProductStatus.BLOCKED, with_sku_active_quantity=10)
    visible = repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=10)

    response = await _make_use_case(repo)()

    assert response.total_count == 1
    assert response.items[0].id == visible.id
    statuses = {item.status for item in response.items}
    assert ProductStatus.HARD_BLOCKED not in statuses
    assert ProductStatus.BLOCKED not in statuses


@pytest.mark.anyio
async def test_list_returns_short_cards_with_min_price():
    """Листинг отдаёт короткие карточки: min_price = min(price видимых SKU), cover_image."""
    repo = FakePublicCatalogRepository()
    pid = uuid4()
    product = repo.add_product(
        status=ProductStatus.MODERATED,
        images=[make_image('/s3/cover-1.jpg', ordering=1), make_image('/s3/cover-0.jpg', ordering=0)],
        skus=[
            _make_sku(product_id=pid, active_quantity=5, price=15_000_000),
            _make_sku(product_id=pid, active_quantity=3, price=9_900_000),  # минимальная
            _make_sku(product_id=pid, active_quantity=0, price=1),  # нет остатка → игнор
        ],
    )

    response = await _make_use_case(repo)()

    assert response.total_count == 1
    item = response.items[0]
    assert item.id == product.id
    assert item.min_price == 9_900_000
    assert item.cover_image == '/s3/cover-0.jpg'  # по ordering
    # Короткая карточка НЕ содержит skus/description/seller_id
    dump = item.model_dump()
    assert 'skus' not in dump
    assert 'description' not in dump
    assert 'seller_id' not in dump


@pytest.mark.anyio
async def test_list_short_card_cover_image_none_when_no_images():
    repo = FakePublicCatalogRepository()
    repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=4)

    response = await _make_use_case(repo)()

    assert response.items[0].cover_image is None


@pytest.mark.anyio
async def test_filters_by_category_and_price_range():
    """category_id + min_price/max_price фильтруют корректно."""
    repo = FakePublicCatalogRepository()
    cat = uuid4()
    other_cat = uuid4()
    cheap = repo.add_product(category_id=cat, skus=[_make_sku(product_id=uuid4(), active_quantity=5, price=5_000)])
    mid = repo.add_product(category_id=cat, skus=[_make_sku(product_id=uuid4(), active_quantity=5, price=50_000)])
    repo.add_product(category_id=cat, skus=[_make_sku(product_id=uuid4(), active_quantity=5, price=500_000)])  # > max
    repo.add_product(category_id=other_cat, skus=[_make_sku(product_id=uuid4(), active_quantity=5, price=50_000)])

    response = await _make_use_case(repo)(category_id=cat, min_price=1_000, max_price=100_000)

    ids = {item.id for item in response.items}
    assert ids == {cheap.id, mid.id}
    assert response.total_count == 2


@pytest.mark.anyio
async def test_filters_by_seller_id():
    repo = FakePublicCatalogRepository()
    seller = uuid4()
    mine_a = repo.add_product(seller_id=seller, with_sku_active_quantity=5)
    mine_b = repo.add_product(seller_id=seller, with_sku_active_quantity=5)
    repo.add_product(seller_id=uuid4(), with_sku_active_quantity=5)

    response = await _make_use_case(repo)(seller_id=seller)

    ids = {item.id for item in response.items}
    assert ids == {mine_a.id, mine_b.id}
    assert response.total_count == 2


@pytest.mark.anyio
async def test_filters_by_characteristic_attributes():
    """filters[brand]=apple|samsung & filters[memory]=256 — AND по ключам, OR по значениям."""
    repo = FakePublicCatalogRepository()
    apple_256 = repo.add_product(
        with_sku_active_quantity=5,
        characteristics=[make_characteristic('brand', 'apple'), make_characteristic('memory', '256')],
    )
    samsung_256 = repo.add_product(
        with_sku_active_quantity=5,
        characteristics=[make_characteristic('brand', 'samsung'), make_characteristic('memory', '256')],
    )
    apple_128 = repo.add_product(
        with_sku_active_quantity=5,
        characteristics=[make_characteristic('brand', 'apple'), make_characteristic('memory', '128')],
    )
    repo.add_product(
        with_sku_active_quantity=5,
        characteristics=[make_characteristic('brand', 'xiaomi'), make_characteristic('memory', '256')],
    )

    response = await _make_use_case(repo)(filters={'brand': ['apple', 'samsung'], 'memory': ['256']})

    ids = {item.id for item in response.items}
    assert ids == {apple_256.id, samsung_256.id}
    assert apple_128.id not in ids


@pytest.mark.anyio
async def test_sort_price_asc_and_created_desc():
    """sort=price_asc — по возрастанию min_price; created_desc — новые первыми."""
    repo = FakePublicCatalogRepository()
    expensive = repo.add_product(
        created_at=past(30), skus=[_make_sku(product_id=uuid4(), active_quantity=5, price=900_000)]
    )
    cheap = repo.add_product(
        created_at=past(20), skus=[_make_sku(product_id=uuid4(), active_quantity=5, price=100_000)]
    )
    mid = repo.add_product(created_at=past(10), skus=[_make_sku(product_id=uuid4(), active_quantity=5, price=500_000)])

    asc = await _make_use_case(repo)(sort=CatalogSort.PRICE_ASC)
    assert [i.id for i in asc.items] == [cheap.id, mid.id, expensive.id]

    desc = await _make_use_case(repo)(sort=CatalogSort.PRICE_DESC)
    assert [i.id for i in desc.items] == [expensive.id, mid.id, cheap.id]

    by_date = await _make_use_case(repo)(sort=CatalogSort.CREATED_DESC)
    # mid создан последним (past(10)) → первый
    assert [i.id for i in by_date.items] == [mid.id, cheap.id, expensive.id]


@pytest.mark.anyio
async def test_search_matches_title_or_description():
    repo = FakePublicCatalogRepository()
    hit = repo.add_product(title='iPhone 15 Pro', with_sku_active_quantity=5)
    repo.add_product(title='Galaxy S24', description='Samsung flagship', with_sku_active_quantity=5)

    response = await _make_use_case(repo)(search='iphone')

    assert response.total_count == 1
    assert response.items[0].id == hit.id


@pytest.mark.anyio
async def test_pagination_limit_and_offset():
    """limit/offset работают корректно. total_count — общее количество видимых."""
    repo = FakePublicCatalogRepository()
    for i in range(5):
        repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=10, created_at=past(i))

    response = await _make_use_case(repo)(limit=2, offset=1)

    assert response.total_count == 5
    assert response.limit == 2
    assert response.offset == 1
    assert len(response.items) == 2
