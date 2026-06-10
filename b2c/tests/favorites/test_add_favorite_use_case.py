from uuid import uuid4

import pytest

from apps.favorites.schemas.request import AddFavoriteRequestSchema
from apps.favorites.use_cases import AddFavoriteUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.favorites.fakes import FakeFavoriteRepository


def _user() -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)


@pytest.mark.anyio
async def test_add_to_favorites_returns_201():
    """DoD: первое добавление товара даёт created=True (роутер маппит на 201)."""
    user = _user()
    repo = FakeFavoriteRepository()
    use_case = AddFavoriteUseCase(favorite_repository=repo)
    product_id = uuid4()

    result = await use_case(AddFavoriteRequestSchema(product_id=product_id), user)

    assert result.created is True
    assert result.favorite.user_id == user.id
    assert result.favorite.product_id == product_id
    assert len(repo.created) == 1
    assert repo.created[0].user_id == user.id
    assert repo.created[0].product_id == product_id


@pytest.mark.anyio
async def test_repeat_add_returns_200_not_duplicate():
    """DoD: повторное добавление того же (user_id, product_id) не создаёт дубль
    и возвращает created=False (роутер маппит на 200).
    """
    user = _user()
    repo = FakeFavoriteRepository()
    use_case = AddFavoriteUseCase(favorite_repository=repo)
    product_id = uuid4()

    first = await use_case(AddFavoriteRequestSchema(product_id=product_id), user)
    second = await use_case(AddFavoriteRequestSchema(product_id=product_id), user)

    assert first.created is True
    assert second.created is False
    assert second.favorite.id == first.favorite.id
    assert len(repo.created) == 1, 'второй вызов не должен делать INSERT'


@pytest.mark.anyio
async def test_add_uses_jwt_user_id_ignoring_request_extras():
    """user_id берётся только из JWT — даже если клиент пытается передать чужой."""
    user = _user()
    repo = FakeFavoriteRepository()
    use_case = AddFavoriteUseCase(favorite_repository=repo)
    product_id = uuid4()

    # extra='ignore' — лишний user_id из тела не попадёт в схему
    request = AddFavoriteRequestSchema.model_validate({'product_id': str(product_id), 'user_id': str(uuid4())})

    result = await use_case(request, user)

    assert result.favorite.user_id == user.id
    assert repo.created[0].user_id == user.id


@pytest.mark.anyio
async def test_add_separates_favorites_per_user():
    """Разные users могут иметь свой favorite на один product_id."""
    user_a = _user()
    user_b = _user()
    repo = FakeFavoriteRepository()
    use_case = AddFavoriteUseCase(favorite_repository=repo)
    product_id = uuid4()

    res_a = await use_case(AddFavoriteRequestSchema(product_id=product_id), user_a)
    res_b = await use_case(AddFavoriteRequestSchema(product_id=product_id), user_b)

    assert res_a.created is True
    assert res_b.created is True
    assert res_a.favorite.id != res_b.favorite.id
