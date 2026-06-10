"""Тесты GET /public/facets: счётчики по характеристикам + видимость + auth.

- Use-case-уровень (FakePublicCatalogRepository): корректность счётчиков и учёт
  видимости (только MODERATED + not deleted + есть SKU active_quantity > 0).
- Router-уровень: без X-Service-Key → 401.
"""

from uuid import uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.errors import setup_error_handlers
from apps.products.enums import ProductStatus
from apps.public.routers import router as public_router
from apps.public.routers import verify_b2c_to_b2b
from apps.public.schemas.response import FacetsPublicResponseSchema
from apps.public.use_cases import GetFacetsUseCase
from shared.inbox.dependencies import make_verify_service_key
from shared.types import ServiceKeyDirection
from tests.public.fakes import (
    FakePublicCatalogRepository,
    _make_sku,
    make_characteristic,
)

TEST_SERVICE_KEY = 'test-b2c-to-b2b-key'
_AUTH = {'X-Service-Key': TEST_SERVICE_KEY}

_verify_with_test_key = make_verify_service_key(ServiceKeyDirection.B2C_TO_B2B, TEST_SERVICE_KEY)


# --- use-case: counts per characteristic ------------------------------------


@pytest.mark.anyio
async def test_facets_return_counts_per_characteristic():
    """Счётчики = число РАЗНЫХ видимых товаров с данной характеристикой-значением."""
    repo = FakePublicCatalogRepository()
    repo.add_product(
        with_sku_active_quantity=5,
        characteristics=[make_characteristic('Бренд', 'Apple'), make_characteristic('Цвет', 'black')],
    )
    repo.add_product(
        with_sku_active_quantity=5,
        characteristics=[make_characteristic('Бренд', 'Apple'), make_characteristic('Цвет', 'white')],
    )
    repo.add_product(
        with_sku_active_quantity=5,
        characteristics=[make_characteristic('Бренд', 'Samsung'), make_characteristic('Цвет', 'black')],
    )

    result: FacetsPublicResponseSchema = await GetFacetsUseCase(repository=repo)()

    facets = {f.name: {v.value: v.count for v in f.values} for f in result.facets}
    assert facets['Бренд'] == {'Apple': 2, 'Samsung': 1}
    assert facets['Цвет'] == {'black': 2, 'white': 1}


@pytest.mark.anyio
async def test_facets_include_price_range():
    """price_range = (min, max) минимальной цены видимых SKU по выборке."""
    repo = FakePublicCatalogRepository()
    repo.add_product(
        skus=[_make_sku(product_id=uuid4(), active_quantity=5, price=9_900_000)],
        characteristics=[make_characteristic('Бренд', 'Apple')],
    )
    repo.add_product(
        skus=[_make_sku(product_id=uuid4(), active_quantity=5, price=15_000_000)],
        characteristics=[make_characteristic('Бренд', 'Samsung')],
    )

    result = await GetFacetsUseCase(repository=repo)()

    assert result.price_range.min == 9_900_000
    assert result.price_range.max == 15_000_000


# --- use-case: visibility ---------------------------------------------------


@pytest.mark.anyio
async def test_facets_respect_visibility():
    """Невидимые товары (не MODERATED / deleted / без остатка) не учитываются в счётчиках."""
    repo = FakePublicCatalogRepository()
    # Видимый — учитывается.
    repo.add_product(
        status=ProductStatus.MODERATED,
        with_sku_active_quantity=5,
        characteristics=[make_characteristic('Бренд', 'Apple')],
    )
    # Не MODERATED — игнор.
    repo.add_product(
        status=ProductStatus.HARD_BLOCKED,
        with_sku_active_quantity=5,
        characteristics=[make_characteristic('Бренд', 'Apple')],
    )
    # deleted — игнор.
    repo.add_product(
        status=ProductStatus.MODERATED,
        deleted=True,
        with_sku_active_quantity=5,
        characteristics=[make_characteristic('Бренд', 'Apple')],
    )
    # Нет SKU с остатком — игнор.
    repo.add_product(
        status=ProductStatus.MODERATED,
        with_sku_active_quantity=0,
        characteristics=[make_characteristic('Бренд', 'Apple')],
    )

    result = await GetFacetsUseCase(repository=repo)()

    facets = {f.name: {v.value: v.count for v in f.values} for f in result.facets}
    # Только один видимый товар c Apple.
    assert facets == {'Бренд': {'Apple': 1}}


@pytest.mark.anyio
async def test_facets_scoped_by_category_filter():
    """category_id сужает выборку, по которой считаются фасеты."""
    repo = FakePublicCatalogRepository()
    cat = uuid4()
    other = uuid4()
    repo.add_product(
        category_id=cat, with_sku_active_quantity=5, characteristics=[make_characteristic('Бренд', 'Apple')]
    )
    repo.add_product(
        category_id=other, with_sku_active_quantity=5, characteristics=[make_characteristic('Бренд', 'Samsung')]
    )

    result = await GetFacetsUseCase(repository=repo)(category_id=cat)

    facets = {f.name: {v.value: v.count for v in f.values} for f in result.facets}
    assert facets == {'Бренд': {'Apple': 1}}


@pytest.mark.anyio
async def test_facets_empty_when_no_visible_products():
    repo = FakePublicCatalogRepository()
    repo.add_product(status=ProductStatus.HARD_BLOCKED, with_sku_active_quantity=5)

    result = await GetFacetsUseCase(repository=repo)()

    assert result.facets == []
    assert result.price_range.min == 0
    assert result.price_range.max == 0


# --- router: auth -----------------------------------------------------------


class _StubFacetsUseCase:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, **kwargs) -> FacetsPublicResponseSchema:
        self.calls.append(kwargs)
        return FacetsPublicResponseSchema()


class _FacetsProvider(Provider):
    def __init__(self, stub: _StubFacetsUseCase):
        super().__init__()
        self._stub = stub

    @provide(scope=Scope.REQUEST)
    def get_facets(self) -> GetFacetsUseCase:
        return self._stub  # type: ignore[return-value]


def _make_app(stub: _StubFacetsUseCase) -> FastAPI:
    app = FastAPI()
    app.include_router(public_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), _FacetsProvider(stub))
    setup_dishka(container, app)
    app.dependency_overrides[verify_b2c_to_b2b] = _verify_with_test_key
    return app


def test_facets_missing_service_key_returns_401():
    stub = _StubFacetsUseCase()
    client = TestClient(_make_app(stub))

    response = client.get('/api/v1/public/facets')

    assert response.status_code == 401
    assert response.json()['code'] == 'INVALID_SERVICE_KEY'
    assert stub.calls == []


def test_facets_with_service_key_returns_200_and_passes_filters():
    stub = _StubFacetsUseCase()
    client = TestClient(_make_app(stub))
    cat = uuid4()

    response = client.get(
        '/api/v1/public/facets',
        params=[('category_id', str(cat)), ('min_price', 1000), ('max_price', 999999)],
        headers=_AUTH,
    )

    assert response.status_code == 200
    body = response.json()
    assert 'facets' in body
    assert 'price_range' in body
    call = stub.calls[0]
    assert call['category_id'] == cat
    assert call['min_price'] == 1000
    assert call['max_price'] == 999999
