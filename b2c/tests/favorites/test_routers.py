"""Роутер-тесты favorites: реальные use-case'ы поверх in-memory фейков (без БД и HTTP).

Контракт US-CART-01 (вердикт ревьюера):
- PUT /api/v1/favorites/{product_id} → 204 No Content без тела (идемпотентно);
- GET /api/v1/favorites → PaginatedCatalogProducts {items, total_count, limit, offset};
- отказ B2B при обогащении — деградация (200, товары без данных исключены), не 5xx.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.errors import setup_error_handlers
from apps.favorites.routers import router as favorites_router
from apps.favorites.schemas.db import FavoriteReadSchema
from apps.favorites.use_cases import (
    AddFavoriteUseCase,
    ListFavoritesUseCase,
    RemoveFavoriteUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from shared.http_clients import ServiceClientError
from tests.favorites.fakes import FakeB2BProductsClient, FakeFavoriteRepository


def _favorite(user_id: UUID, product_id: UUID) -> FavoriteReadSchema:
    now = datetime.now(UTC)
    return FavoriteReadSchema(
        id=uuid4(),
        user_id=user_id,
        product_id=product_id,
        created_at=now,
        updated_at=now,
    )


class FavoritesRouteProvider(Provider):
    """Поднимает реальные use-case'ы на фейках — роутер тестируется end-to-end."""

    def __init__(self, repo: FakeFavoriteRepository, b2b: FakeB2BProductsClient):
        super().__init__()
        self.repo = repo
        self.b2b = b2b

    @provide(scope=Scope.REQUEST)
    def get_add_use_case(self) -> AddFavoriteUseCase:
        return AddFavoriteUseCase(favorite_repository=self.repo, b2b_products_client=self.b2b)  # type: ignore[arg-type]

    @provide(scope=Scope.REQUEST)
    def get_remove_use_case(self) -> RemoveFavoriteUseCase:
        return RemoveFavoriteUseCase(favorite_repository=self.repo)  # type: ignore[arg-type]

    @provide(scope=Scope.REQUEST)
    def get_list_use_case(self) -> ListFavoritesUseCase:
        return ListFavoritesUseCase(favorite_repository=self.repo, b2b_products_client=self.b2b)  # type: ignore[arg-type]


def _make_app(
    repo: FakeFavoriteRepository,
    b2b: FakeB2BProductsClient,
    user: AuthenticatedUserSchema | None,
) -> FastAPI:
    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(favorites_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        FavoritesRouteProvider(repo, b2b),
    )
    setup_dishka(container, app)
    return app


@pytest.fixture
def repo() -> FakeFavoriteRepository:
    return FakeFavoriteRepository()


@pytest.fixture
def b2b() -> FakeB2BProductsClient:
    return FakeB2BProductsClient()


def _buyer() -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)


# ----------------------------- PUT /{product_id} -----------------------------


def test_add_to_favorites_returns_204(repo, b2b):
    """DoD: первое добавление → 204 No Content, тело пустое, в БД одна запись."""
    user = _buyer()
    product_id = uuid4()
    b2b.add_product(product_id, title='Cool')

    client = TestClient(_make_app(repo, b2b, user=user))
    response = client.put(f'/api/v1/favorites/{product_id}')

    assert response.status_code == 204
    assert response.content == b''
    assert len(repo.created) == 1
    assert repo.created[0].user_id == user.id
    assert repo.created[0].product_id == product_id


def test_repeat_add_returns_204_idempotent(repo, b2b):
    """DoD: повторный PUT того же товара → снова 204 без тела, дубль не создаётся."""
    user = _buyer()
    product_id = uuid4()
    b2b.add_product(product_id, title='Cool')

    client = TestClient(_make_app(repo, b2b, user=user))
    first = client.put(f'/api/v1/favorites/{product_id}')
    second = client.put(f'/api/v1/favorites/{product_id}')

    assert first.status_code == 204
    assert second.status_code == 204
    assert first.content == b''
    assert second.content == b''
    assert len(repo.created) == 1, 'второй PUT не должен делать INSERT'
    assert len(repo.by_id) == 1


def test_add_unknown_product_returns_404(repo, b2b):
    """Товар, которого нет в B2B (неизвестный/заблокированный), нельзя добавить — 404."""
    user = _buyer()

    client = TestClient(_make_app(repo, b2b, user=user))
    response = client.put(f'/api/v1/favorites/{uuid4()}')

    assert response.status_code == 404
    assert response.json()['code'] == 'NOT_FOUND'
    assert repo.created == []


def test_add_favorite_unauthorized_returns_401(repo, b2b):
    client = TestClient(_make_app(repo, b2b, user=None))

    response = client.put(f'/api/v1/favorites/{uuid4()}')

    assert response.status_code == 401


def test_add_favorite_non_buyer_returns_403(repo, b2b):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(repo, b2b, user=user))

    response = client.put(f'/api/v1/favorites/{uuid4()}')

    assert response.status_code == 403


def test_add_favorite_invalid_path_returns_400(repo, b2b):
    user = _buyer()
    client = TestClient(_make_app(repo, b2b, user=user))

    response = client.put('/api/v1/favorites/not-a-uuid')

    assert response.status_code == 400
    assert response.json()['code'] == 'INVALID_REQUEST'


def test_user_id_from_query_is_ignored(repo, b2b):
    """DoD: попытка передать чужой user_id (в query) игнорируется,
    запись создаётся строго для user_id из JWT.
    """
    user = _buyer()
    attacker_target = uuid4()
    product_id = uuid4()
    b2b.add_product(product_id, title='Cool')

    client = TestClient(_make_app(repo, b2b, user=user))

    # Попытка передать чужой user_id в query — должна быть проигнорирована
    response = client.put(f'/api/v1/favorites/{product_id}?user_id={attacker_target}')

    assert response.status_code == 204
    assert len(repo.created) == 1
    assert repo.created[0].user_id == user.id
    assert repo.created[0].product_id == product_id


# --------------------------- DELETE /{product_id} ----------------------------


def test_remove_favorite_returns_204(repo, b2b):
    user = _buyer()
    product_id = uuid4()
    repo.add(_favorite(user.id, product_id))

    client = TestClient(_make_app(repo, b2b, user=user))
    response = client.delete(f'/api/v1/favorites/{product_id}')

    assert response.status_code == 204
    assert response.text == ''
    assert repo.deleted == [(user.id, product_id)]


def test_remove_favorite_unauthorized_returns_401(repo, b2b):
    client = TestClient(_make_app(repo, b2b, user=None))
    response = client.delete(f'/api/v1/favorites/{uuid4()}')
    assert response.status_code == 401


def test_remove_favorite_non_buyer_returns_403(repo, b2b):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(repo, b2b, user=user))
    response = client.delete(f'/api/v1/favorites/{uuid4()}')
    assert response.status_code == 403


# --------------------------------- GET список ---------------------------------


def test_list_returns_paginated_catalog_cards(repo, b2b):
    """DoD: GET отдаёт PaginatedCatalogProducts — items это CatalogProductCard
    (id/name/min_price/has_stock/images), echo limit/offset, корректный total_count.
    """
    user = _buyer()
    product_id = uuid4()
    repo.add(_favorite(user.id, product_id))
    b2b.add_product(
        product_id,
        title='Cool product',
        slug='cool-product',
        min_price=12900,
        cover_image='https://cdn.example.com/cool.jpg',
    )

    client = TestClient(_make_app(repo, b2b, user=user))
    response = client.get('/api/v1/favorites?limit=10&offset=0')

    assert response.status_code == 200
    body = response.json()
    assert body['total_count'] == 1
    assert body['limit'] == 10
    assert body['offset'] == 0

    card = body['items'][0]
    assert card['id'] == str(product_id)
    assert card['name'] == 'Cool product'
    assert card['slug'] == 'cool-product'
    assert card['min_price'] == 12900
    assert card['has_stock'] is True
    assert card['images'][0]['url'] == 'https://cdn.example.com/cool.jpg'


def test_list_favorites_unauthorized_returns_401(repo, b2b):
    client = TestClient(_make_app(repo, b2b, user=None))
    response = client.get('/api/v1/favorites')
    assert response.status_code == 401


def test_b2b_failure_degrades_to_partial_list(repo, b2b):
    """DoD: отказ B2B при обогащении — НЕ 5xx. 200, необогащённые товары исключены
    из items (полный отказ batch → items: []), total_count — реальное число избранного.
    """
    user = _buyer()
    repo.add(_favorite(user.id, uuid4()))
    b2b.error = ServiceClientError(status_code=503, message='GET /api/v1/products failed')

    client = TestClient(_make_app(repo, b2b, user=user))
    response = client.get('/api/v1/favorites')

    assert response.status_code == 200
    body = response.json()
    assert body['items'] == []
    assert body['total_count'] == 1
    assert body['limit'] == 20
    assert body['offset'] == 0
