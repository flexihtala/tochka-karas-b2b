from uuid import UUID, uuid4

import pytest

from apps.favorites.errors import B2BUnavailableError, ProductNotFoundError
from apps.favorites.use_cases import AddFavoriteUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from shared.http_clients import ServiceClientError
from tests.favorites.fakes import FakeB2BProductsClient, FakeFavoriteRepository


def _user() -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)


def _use_case(repo: FakeFavoriteRepository, b2b: FakeB2BProductsClient) -> AddFavoriteUseCase:
    return AddFavoriteUseCase(favorite_repository=repo, b2b_products_client=b2b)  # type: ignore[arg-type]


def _known_product(b2b: FakeB2BProductsClient) -> UUID:
    product_id = uuid4()
    b2b.add_product(product_id, title='Cool')
    return product_id


@pytest.mark.anyio
async def test_add_creates_favorite_and_returns_none():
    """Первое добавление: одна запись в БД, use-case ничего не возвращает (роутер → 204)."""
    user = _user()
    repo = FakeFavoriteRepository()
    b2b = FakeB2BProductsClient()
    product_id = _known_product(b2b)

    result = await _use_case(repo, b2b)(product_id, user)

    assert result is None
    assert len(repo.created) == 1
    assert repo.created[0].user_id == user.id
    assert repo.created[0].product_id == product_id


@pytest.mark.anyio
async def test_repeat_add_is_idempotent_no_duplicate():
    """Повторное добавление того же (user_id, product_id) не создаёт дубль (роутер → 204)."""
    user = _user()
    repo = FakeFavoriteRepository()
    b2b = FakeB2BProductsClient()
    product_id = _known_product(b2b)
    use_case = _use_case(repo, b2b)

    first = await use_case(product_id, user)
    second = await use_case(product_id, user)

    assert first is None
    assert second is None
    assert len(repo.created) == 1, 'второй вызов не должен делать INSERT'
    assert len(repo.by_id) == 1


@pytest.mark.anyio
async def test_add_unknown_product_raises_not_found():
    """Неизвестный товар (B2B его не вернул) → ProductNotFoundError (404)."""
    user = _user()
    repo = FakeFavoriteRepository()
    b2b = FakeB2BProductsClient()  # пустой B2B — товара нет

    with pytest.raises(ProductNotFoundError):
        await _use_case(repo, b2b)(uuid4(), user)

    assert repo.created == []


@pytest.mark.anyio
async def test_add_b2b_unavailable_raises_503():
    """PUT не деградирует: если B2B недоступен, проверка товара отвечает 503."""
    user = _user()
    repo = FakeFavoriteRepository()
    b2b = FakeB2BProductsClient()
    b2b.error = ServiceClientError(status_code=503, message='GET /api/v1/products failed')

    with pytest.raises(B2BUnavailableError):
        await _use_case(repo, b2b)(uuid4(), user)

    assert repo.created == []


@pytest.mark.anyio
async def test_add_uses_jwt_user_id():
    """user_id берётся только из JWT (current_user) — защита от IDOR."""
    user = _user()
    repo = FakeFavoriteRepository()
    b2b = FakeB2BProductsClient()
    product_id = _known_product(b2b)

    await _use_case(repo, b2b)(product_id, user)

    assert repo.created[0].user_id == user.id


@pytest.mark.anyio
async def test_add_separates_favorites_per_user():
    """Разные users могут иметь свой favorite на один product_id."""
    user_a = _user()
    user_b = _user()
    repo = FakeFavoriteRepository()
    b2b = FakeB2BProductsClient()
    product_id = _known_product(b2b)
    use_case = _use_case(repo, b2b)

    await use_case(product_id, user_a)
    await use_case(product_id, user_b)

    assert len(repo.created) == 2
    assert {item.user_id for item in repo.created} == {user_a.id, user_b.id}
