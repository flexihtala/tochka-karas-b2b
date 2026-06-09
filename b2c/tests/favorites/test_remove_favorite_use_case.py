from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.favorites.schemas.db import FavoriteReadSchema
from apps.favorites.use_cases import RemoveFavoriteUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.favorites.fakes import FakeFavoriteRepository


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
async def test_remove_existing_favorite_deletes_it():
    user = _user()
    product_id = uuid4()
    repo = FakeFavoriteRepository()
    repo.add(_favorite(user.id, product_id))

    use_case = RemoveFavoriteUseCase(favorite_repository=repo)
    await use_case(product_id, user)

    assert await repo.get_by_user_and_product(user.id, product_id) is None
    assert repo.deleted == [(user.id, product_id)]


@pytest.mark.anyio
async def test_remove_nonexistent_favorite_is_idempotent():
    """Удаление того, чего нет, не падает — это нормальный 204."""
    user = _user()
    repo = FakeFavoriteRepository()
    use_case = RemoveFavoriteUseCase(favorite_repository=repo)

    await use_case(uuid4(), user)  # никаких exceptions

    # Удалить чужое физически невозможно — repo вызвалась с current_user.id
    assert all(call[0] == user.id for call in repo.deleted)


@pytest.mark.anyio
async def test_remove_cannot_affect_other_users_favorite():
    """user_id из JWT защищает от IDOR: чужие записи остаются нетронутыми."""
    attacker = _user()
    victim = _user()
    product_id = uuid4()
    repo = FakeFavoriteRepository()
    victims_favorite = _favorite(victim.id, product_id)
    repo.add(victims_favorite)

    use_case = RemoveFavoriteUseCase(favorite_repository=repo)
    await use_case(product_id, attacker)

    # Жертва всё ещё имеет своё избранное
    still_there = await repo.get_by_user_and_product(victim.id, product_id)
    assert still_there is not None
    assert still_there.id == victims_favorite.id
