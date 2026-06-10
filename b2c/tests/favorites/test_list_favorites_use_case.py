from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.favorites.schemas.db import FavoriteReadSchema
from apps.favorites.use_cases import ListFavoritesUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from shared.http_clients import ServiceClientError
from tests.favorites.fakes import FakeB2BProductsClient, FakeFavoriteRepository


def _user() -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)


def _favorite(user_id, product_id):
    now = datetime.now(UTC)
    return FavoriteReadSchema(
        id=uuid4(),
        user_id=user_id,
        product_id=product_id,
        created_at=now,
        updated_at=now,
    )


def _use_case(repo: FakeFavoriteRepository, b2b: FakeB2BProductsClient) -> ListFavoritesUseCase:
    return ListFavoritesUseCase(favorite_repository=repo, b2b_products_client=b2b)  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_blocked_product_excluded_from_list():
    """DoD: товар, который B2B не вернул (заблокирован/удалён),
    исключается из items GET /favorites — это не 404 и не ошибка.
    total_count при этом считает ВСЁ избранное (до обогащения).
    """
    user = _user()
    repo = FakeFavoriteRepository()
    visible_id = uuid4()
    blocked_id = uuid4()
    repo.add(_favorite(user.id, visible_id))
    repo.add(_favorite(user.id, blocked_id))

    b2b = FakeB2BProductsClient()
    b2b.add_product(visible_id, title='Visible product')
    # blocked_id не добавляем — B2B как будто его отфильтровал

    result = await _use_case(repo, b2b)(user)

    returned_ids = {item.id for item in result.items}
    assert visible_id in returned_ids
    assert blocked_id not in returned_ids
    assert result.total_count == 2


@pytest.mark.anyio
async def test_list_only_returns_current_user_favorites():
    """user_id из JWT — чужие избранные не утекают наружу."""
    user = _user()
    other = _user()
    repo = FakeFavoriteRepository()

    own = uuid4()
    foreign = uuid4()
    repo.add(_favorite(user.id, own))
    repo.add(_favorite(other.id, foreign))

    b2b = FakeB2BProductsClient()
    b2b.add_product(own, title='Own')
    b2b.add_product(foreign, title='Foreign')

    result = await _use_case(repo, b2b)(user)

    assert {item.id for item in result.items} == {own}
    assert result.total_count == 1
    # И в B2B мы спрашиваем только про свои id
    assert b2b.calls[0] == [own]


@pytest.mark.anyio
async def test_list_empty_for_user_without_favorites():
    """Пустое избранное → {items: [], total_count: 0} + echo limit/offset, B2B даже не дёргаем."""
    user = _user()
    repo = FakeFavoriteRepository()
    b2b = FakeB2BProductsClient()

    result = await _use_case(repo, b2b)(user)

    assert result.items == []
    assert result.total_count == 0
    assert result.limit == 20
    assert result.offset == 0
    assert b2b.calls == []


@pytest.mark.anyio
async def test_list_returns_paginated_catalog_cards():
    """DoD: items — карточки CatalogProductCard, маппинг B2B payload → card
    зеркалирует каталог: name←title, images←[cover_image], min_price, has_stock, slug.
    """
    user = _user()
    repo = FakeFavoriteRepository()
    product_id = uuid4()
    repo.add(_favorite(user.id, product_id))

    b2b = FakeB2BProductsClient()
    b2b.add_product(
        product_id,
        title='Cool product',
        slug='cool-product',
        min_price=12900,
        cover_image='https://cdn.example.com/cool.jpg',
    )

    result = await _use_case(repo, b2b)(user, limit=10, offset=0)

    assert result.total_count == 1
    assert result.limit == 10
    assert result.offset == 0

    card = result.items[0]
    assert card.id == product_id
    assert card.name == 'Cool product'
    assert card.slug == 'cool-product'
    assert card.min_price == 12900
    assert card.has_stock is True
    assert len(card.images) == 1
    assert card.images[0].url == 'https://cdn.example.com/cool.jpg'
    assert card.images[0].id == product_id
    assert card.images[0].is_main is True


@pytest.mark.anyio
async def test_list_product_without_cover_image_has_empty_images():
    """Нет cover_image у B2B — images: [] (как в каталожном маппинге), не ошибка."""
    user = _user()
    repo = FakeFavoriteRepository()
    product_id = uuid4()
    repo.add(_favorite(user.id, product_id))

    b2b = FakeB2BProductsClient()
    b2b.add_product(product_id, title='No cover', min_price=100)

    result = await _use_case(repo, b2b)(user)

    assert result.items[0].images == []


@pytest.mark.anyio
async def test_list_pagination_respects_limit_offset():
    """DoD: limit/offset режут страницу избранного, total_count — общее число,
    в B2B уходит batch ТОЛЬКО по товарам страницы.
    """
    user = _user()
    repo = FakeFavoriteRepository()
    b2b = FakeB2BProductsClient()

    product_ids = [uuid4(), uuid4(), uuid4()]
    for product_id in product_ids:
        repo.add(_favorite(user.id, product_id))
        b2b.add_product(product_id, title=f'Product {product_id}')

    result = await _use_case(repo, b2b)(user, limit=1, offset=1)

    assert [item.id for item in result.items] == [product_ids[1]]
    assert result.total_count == 3
    assert result.limit == 1
    assert result.offset == 1
    # Обогащаем именно страницу, а не всё избранное
    assert b2b.calls == [[product_ids[1]]]


@pytest.mark.anyio
async def test_list_offset_beyond_total_returns_empty_page():
    user = _user()
    repo = FakeFavoriteRepository()
    b2b = FakeB2BProductsClient()
    repo.add(_favorite(user.id, uuid4()))

    result = await _use_case(repo, b2b)(user, limit=20, offset=100)

    assert result.items == []
    assert result.total_count == 1
    assert b2b.calls == []


@pytest.mark.anyio
async def test_b2b_failure_degrades_to_partial_list():
    """DoD: ServiceClientError от B2B при обогащении НЕ всплывает (никаких 5xx):
    необогащённые товары исключаются из items, total_count — реальное число избранного.
    """
    user = _user()
    repo = FakeFavoriteRepository()
    repo.add(_favorite(user.id, uuid4()))

    b2b = FakeB2BProductsClient()
    b2b.error = ServiceClientError(status_code=503, message='GET /api/v1/products failed')

    result = await _use_case(repo, b2b)(user)  # никаких exceptions

    assert result.items == []
    assert result.total_count == 1
    assert result.limit == 20
    assert result.offset == 0
