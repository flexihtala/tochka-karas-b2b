"""DoD-тесты US-B2B-07: листинг public-каталога.

Покрывают условия видимости, отсутствие cost_price/reserved_quantity в response
и batch-режим (?ids=...).
"""

from uuid import uuid4

import pytest

from apps.products.enums import ProductStatus
from apps.public.use_cases.list_catalog import ListCatalogUseCase
from tests.public.fakes import (
    FakePublicCatalogRepository,
    _make_sku,
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
    # И для надёжности: ни одного товара со статусом HARD_BLOCKED/BLOCKED
    statuses = {item.status for item in response.items}
    assert ProductStatus.HARD_BLOCKED not in statuses
    assert ProductStatus.BLOCKED not in statuses


@pytest.mark.anyio
async def test_catalog_missing_service_key_returns_401():
    """Router-level тест: без заголовка X-Service-Key endpoint отвечает 401."""
    # Этот тест на use-case уровне не имеет смысла (use-case не знает про auth).
    # Проверяется в test_routers.py: см. test_catalog_missing_service_key_returns_401.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from apps.errors import setup_error_handlers
    from apps.public.routers import router

    app = FastAPI()
    app.include_router(router, prefix='/api/v1')
    setup_error_handlers(app)
    client = TestClient(app)

    response = client.get('/api/v1/public/products')

    assert response.status_code == 401
    body = response.json()
    assert body['code'] == 'INVALID_SERVICE_KEY'


@pytest.mark.anyio
async def test_catalog_response_has_no_cost_price():
    """ProductPublicResponse / SKUPublicResponse НЕ содержат cost_price и reserved_quantity."""
    repo = FakePublicCatalogRepository()
    repo.add_product(
        status=ProductStatus.MODERATED,
        skus=[
            _make_sku(product_id=uuid4(), active_quantity=5, cost_price=9_500_000, reserved_quantity=3),
        ],
    )

    response = await _make_use_case(repo)()

    assert response.total_count == 1
    product = response.items[0]
    assert len(product.skus) == 1
    sku = product.skus[0]

    # cost_price / reserved_quantity отсутствуют в схеме
    sku_dump = sku.model_dump()
    assert 'cost_price' not in sku_dump
    assert 'reserved_quantity' not in sku_dump

    # И в JSON-репрезентации (model_dump_json) тоже
    sku_json = sku.model_dump_json()
    assert 'cost_price' not in sku_json
    assert 'reserved_quantity' not in sku_json

    # А вот active_quantity и price — есть
    assert sku_dump['active_quantity'] == 5
    assert sku_dump['price'] > 0


@pytest.mark.anyio
async def test_batch_ids_returns_visible_subset():
    """?ids=... возвращает подмножество видимых. Отсутствующие/скрытые не дают 404."""
    repo = FakePublicCatalogRepository()
    visible_a = repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=10)
    visible_b = repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=5)
    hidden_blocked = repo.add_product(status=ProductStatus.HARD_BLOCKED, with_sku_active_quantity=10)
    hidden_no_stock = repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=0)
    missing_id = uuid4()

    response = await _make_use_case(repo)(
        ids=[visible_a.id, hidden_blocked.id, hidden_no_stock.id, missing_id, visible_b.id],
    )

    returned_ids = {item.id for item in response.items}
    assert returned_ids == {visible_a.id, visible_b.id}
    assert response.total_count == 2
    # Подтверждаем: 404 не выкидывался — просто отсутствуют в ответе
    assert all(item.id in {visible_a.id, visible_b.id} for item in response.items)


@pytest.mark.anyio
async def test_batch_empty_ids_returns_empty_immediately():
    """Пустой ids=[] (после парсинга ?ids=) возвращает пустую выдачу без запроса в репозиторий."""
    repo = FakePublicCatalogRepository()
    repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=10)

    response = await _make_use_case(repo)(ids=[])

    assert response.total_count == 0
    assert response.items == []
    # Репозиторий не вызывался
    assert repo.list_calls == []


@pytest.mark.anyio
async def test_pagination_limit_and_offset():
    """limit/offset работают корректно. total_count — общее количество видимых."""
    repo = FakePublicCatalogRepository()
    for _ in range(5):
        repo.add_product(status=ProductStatus.MODERATED, with_sku_active_quantity=10)

    response = await _make_use_case(repo)(limit=2, offset=1)

    assert response.total_count == 5
    assert response.limit == 2
    assert response.offset == 1
    assert len(response.items) == 2
