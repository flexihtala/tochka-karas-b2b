"""DoD-тесты US-B2B-07: use-case'ы batch / detail / similar / sku."""

from uuid import uuid4

import pytest

from apps.products.enums import ProductStatus
from apps.public.errors import PublicProductNotFoundError, PublicSKUNotFoundError
from apps.public.use_cases import (
    BatchProductsUseCase,
    GetPublicProductUseCase,
    GetPublicSKUUseCase,
    GetSimilarProductsUseCase,
)
from tests.public.fakes import FakePublicCatalogRepository, _make_sku


# --- batch -----------------------------------------------------------------


@pytest.mark.anyio
async def test_batch_post_returns_full_visible_subset():
    """POST /batch отдаёт ПОЛНЫЕ карточки только видимых; missing/hidden молча опущены."""
    repo = FakePublicCatalogRepository()
    visible_a = repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=10)
    visible_b = repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=5)
    hidden_blocked = repo.add_product(status=ProductStatus.HARD_BLOCKED, with_sku_active_quantity=10)
    hidden_no_stock = repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=0)
    missing_id = uuid4()

    use_case = BatchProductsUseCase(repository=repo)
    result = await use_case(product_ids=[visible_a.id, hidden_blocked.id, hidden_no_stock.id, missing_id, visible_b.id])

    returned_ids = {p.id for p in result}
    assert returned_ids == {visible_a.id, visible_b.id}
    # Это полные карточки — есть skus и description.
    assert all(hasattr(p, 'skus') for p in result)
    assert all(p.description for p in result)


@pytest.mark.anyio
async def test_batch_empty_returns_empty():
    repo = FakePublicCatalogRepository()
    repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=10)

    result = await BatchProductsUseCase(repository=repo)(product_ids=[])

    assert result == []


@pytest.mark.anyio
async def test_sku_public_has_no_cost_price_no_reserved_quantity():
    """ProductPublicResponse → SKUPublicResponse: нет cost_price/reserved_quantity, есть stock_quantity."""
    repo = FakePublicCatalogRepository()
    product = repo.add_product(
        status=ProductStatus.MODERATED,
        skus=[_make_sku(product_id=uuid4(), active_quantity=5, cost_price=9_500_000, reserved_quantity=3)],
    )

    result = await BatchProductsUseCase(repository=repo)(product_ids=[product.id])

    assert len(result) == 1
    sku = result[0].skus[0]
    dump = sku.model_dump()
    assert 'cost_price' not in dump
    assert 'reserved_quantity' not in dump
    assert 'cost_price' not in sku.model_dump_json()
    assert 'reserved_quantity' not in sku.model_dump_json()
    # stock_quantity присутствует и = active + reserved.
    assert dump['stock_quantity'] == 5 + 3
    assert dump['active_quantity'] == 5


# --- detail ----------------------------------------------------------------


@pytest.mark.anyio
async def test_get_public_product_detail_returns_full():
    repo = FakePublicCatalogRepository()
    product = repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=7)

    result = await GetPublicProductUseCase(repository=repo)(product.id)

    assert result.id == product.id
    assert len(result.skus) == 1


@pytest.mark.anyio
async def test_get_public_product_detail_404_when_not_visible():
    repo = FakePublicCatalogRepository()
    blocked = repo.add_product(status=ProductStatus.HARD_BLOCKED, with_sku_active_quantity=10)
    no_stock = repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=0)

    use_case = GetPublicProductUseCase(repository=repo)
    for pid in (blocked.id, no_stock.id, uuid4()):
        with pytest.raises(PublicProductNotFoundError):
            await use_case(pid)


# --- similar ---------------------------------------------------------------


@pytest.mark.anyio
async def test_similar_returns_same_category_excluding_self():
    repo = FakePublicCatalogRepository()
    cat = uuid4()
    other = uuid4()
    source = repo.add_product(category_id=cat, with_sku_active_quantity=5)
    sib_a = repo.add_product(category_id=cat, with_sku_active_quantity=5)
    sib_b = repo.add_product(category_id=cat, with_sku_active_quantity=5)
    repo.add_product(category_id=other, with_sku_active_quantity=5)  # другая категория
    repo.add_product(category_id=cat, status=ProductStatus.HARD_BLOCKED, with_sku_active_quantity=5)  # не видим

    result = await GetSimilarProductsUseCase(repository=repo)(source.id, limit=10)

    ids = {p.id for p in result}
    assert ids == {sib_a.id, sib_b.id}
    assert source.id not in ids


@pytest.mark.anyio
async def test_similar_respects_limit():
    repo = FakePublicCatalogRepository()
    cat = uuid4()
    source = repo.add_product(category_id=cat, with_sku_active_quantity=5)
    for _ in range(5):
        repo.add_product(category_id=cat, with_sku_active_quantity=5)

    result = await GetSimilarProductsUseCase(repository=repo)(source.id, limit=2)

    assert len(result) == 2


@pytest.mark.anyio
async def test_similar_empty_when_source_missing():
    repo = FakePublicCatalogRepository()
    result = await GetSimilarProductsUseCase(repository=repo)(uuid4(), limit=10)
    assert result == []


# --- sku -------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_public_sku_returns_sku_when_product_visible():
    repo = FakePublicCatalogRepository()
    pid = uuid4()
    sku = _make_sku(product_id=pid, active_quantity=5)
    repo.add_product(status=ProductStatus.MODERATED, skus=[sku])

    result = await GetPublicSKUUseCase(repository=repo)(sku.id)

    assert result.id == sku.id
    assert 'cost_price' not in result.model_dump()


@pytest.mark.anyio
async def test_get_public_sku_404_when_product_not_visible():
    repo = FakePublicCatalogRepository()
    pid = uuid4()
    sku = _make_sku(product_id=pid, active_quantity=10)
    repo.add_product(status=ProductStatus.HARD_BLOCKED, skus=[sku])

    use_case = GetPublicSKUUseCase(repository=repo)
    with pytest.raises(PublicSKUNotFoundError):
        await use_case(sku.id)
    # Несуществующий SKU — тоже 404.
    with pytest.raises(PublicSKUNotFoundError):
        await use_case(uuid4())
