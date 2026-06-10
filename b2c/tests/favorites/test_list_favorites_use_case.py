from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.favorites.errors import B2BUnavailableError
from apps.favorites.schemas.db import FavoriteReadSchema
from apps.favorites.use_cases import ListFavoritesUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
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


@pytest.mark.anyio
async def test_blocked_product_excluded_from_list():
    """DoD: товар, который B2B не вернул (заблокирован/удалён),
    исключается из ответа GET /favorites — это не 404 и не ошибка.
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

    use_case = ListFavoritesUseCase(favorite_repository=repo, b2b_products_client=b2b)
    result = await use_case(user)

    returned_ids = {item.product_id for item in result.items}
    assert visible_id in returned_ids
    assert blocked_id not in returned_ids
    assert result.total == 1


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

    use_case = ListFavoritesUseCase(favorite_repository=repo, b2b_products_client=b2b)
    result = await use_case(user)

    assert {item.product_id for item in result.items} == {own}
    # И в B2B мы спрашиваем только про свои id
    assert b2b.calls[0] == [own]


@pytest.mark.anyio
async def test_list_empty_for_user_without_favorites():
    """Пустое избранное → 200 {items: [], total: 0}, B2B даже не дёргаем."""
    user = _user()
    repo = FakeFavoriteRepository()
    b2b = FakeB2BProductsClient()

    use_case = ListFavoritesUseCase(favorite_repository=repo, b2b_products_client=b2b)
    result = await use_case(user)

    assert result.items == []
    assert result.total == 0
    assert b2b.calls == []


@pytest.mark.anyio
async def test_list_propagates_b2b_unavailable_error():
    """Если ServiceClient упал, list_favorites должен поднять B2BUnavailableError (503)."""
    user = _user()
    repo = FakeFavoriteRepository()
    repo.add(_favorite(user.id, uuid4()))

    b2b = FakeB2BProductsClient()
    b2b.error = B2BUnavailableError()

    use_case = ListFavoritesUseCase(favorite_repository=repo, b2b_products_client=b2b)

    with pytest.raises(B2BUnavailableError):
        await use_case(user)


@pytest.mark.anyio
async def test_list_enriches_with_product_payload():
    """В items.product попадает то, что вернул B2B (title, images и т.п.)."""
    user = _user()
    repo = FakeFavoriteRepository()
    product_id = uuid4()
    repo.add(_favorite(user.id, product_id))

    b2b = FakeB2BProductsClient()
    b2b.add_product(product_id, title='Cool', skus=[{'id': str(uuid4())}])

    use_case = ListFavoritesUseCase(favorite_repository=repo, b2b_products_client=b2b)
    result = await use_case(user)

    assert len(result.items) == 1
    assert result.items[0].product['title'] == 'Cool'
    assert isinstance(result.items[0].product['skus'], list)
