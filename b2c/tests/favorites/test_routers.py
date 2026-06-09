from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.errors import setup_error_handlers
from apps.favorites.errors import B2BUnavailableError
from apps.favorites.routers import router as favorites_router
from apps.favorites.schemas.request import AddFavoriteRequestSchema
from apps.favorites.schemas.response import (
    FavoriteListResponseSchema,
    FavoriteProductSchema,
    FavoriteResponseSchema,
)
from apps.favorites.use_cases import (
    AddFavoriteUseCase,
    FavoriteCreatedResult,
    ListFavoritesUseCase,
    RemoveFavoriteUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _make_favorite(user_id: UUID, product_id: UUID, favorite_id: UUID | None = None) -> FavoriteResponseSchema:
    now = datetime.now(UTC)
    return FavoriteResponseSchema(
        id=favorite_id or uuid4(),
        user_id=user_id,
        product_id=product_id,
        created_at=now,
        updated_at=now,
    )


class StubAddFavorite:
    def __init__(self):
        self.calls: list[tuple[AddFavoriteRequestSchema, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None
        self.result: FavoriteCreatedResult | None = None

    async def __call__(
        self,
        data: AddFavoriteRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> FavoriteCreatedResult:
        self.calls.append((data, current_user))
        if self.error:
            raise self.error
        if self.result is not None:
            return self.result
        return FavoriteCreatedResult(
            favorite=_make_favorite(current_user.id, data.product_id),
            created=True,
        )


class StubRemoveFavorite:
    def __init__(self):
        self.calls: list[tuple[UUID, AuthenticatedUserSchema]] = []
        self.error: Exception | None = None

    async def __call__(self, product_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        self.calls.append((product_id, current_user))
        if self.error:
            raise self.error


class StubListFavorites:
    def __init__(self):
        self.calls: list[AuthenticatedUserSchema] = []
        self.error: Exception | None = None
        self.response: FavoriteListResponseSchema = FavoriteListResponseSchema(items=[], total=0)

    async def __call__(self, current_user: AuthenticatedUserSchema) -> FavoriteListResponseSchema:
        self.calls.append(current_user)
        if self.error:
            raise self.error
        return self.response


class FavoritesRouteProvider(Provider):
    def __init__(self, add_stub: StubAddFavorite, remove_stub: StubRemoveFavorite, list_stub: StubListFavorites):
        super().__init__()
        self.add_stub = add_stub
        self.remove_stub = remove_stub
        self.list_stub = list_stub

    @provide(scope=Scope.REQUEST)
    def get_add_use_case(self) -> AddFavoriteUseCase:
        return self.add_stub  # type: ignore[return-value]

    @provide(scope=Scope.REQUEST)
    def get_remove_use_case(self) -> RemoveFavoriteUseCase:
        return self.remove_stub  # type: ignore[return-value]

    @provide(scope=Scope.REQUEST)
    def get_list_use_case(self) -> ListFavoritesUseCase:
        return self.list_stub  # type: ignore[return-value]


def _make_app(
    add_stub: StubAddFavorite,
    remove_stub: StubRemoveFavorite,
    list_stub: StubListFavorites,
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
        FavoritesRouteProvider(add_stub, remove_stub, list_stub),
    )
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs():
    return StubAddFavorite(), StubRemoveFavorite(), StubListFavorites()


def _buyer() -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)


def test_add_favorite_returns_204(stubs):
    add_stub, remove_stub, list_stub = stubs
    user = _buyer()
    product_id = uuid4()
    add_stub.result = FavoriteCreatedResult(
        favorite=_make_favorite(user.id, product_id),
        created=True,
    )

    client = TestClient(_make_app(*stubs, user=user))
    response = client.put(f'/api/v1/favorites/{product_id}')

    assert response.status_code == 204
    assert response.text == ''
    # Use-case был вызван с product_id из path и user_id из JWT
    data, current_user = add_stub.calls[0]
    assert data.product_id == product_id
    assert current_user.id == user.id


def test_add_favorite_idempotent_repeat_returns_204(stubs):
    add_stub, remove_stub, list_stub = stubs
    user = _buyer()
    product_id = uuid4()
    add_stub.result = FavoriteCreatedResult(
        favorite=_make_favorite(user.id, product_id),
        created=False,
    )

    client = TestClient(_make_app(*stubs, user=user))
    response = client.put(f'/api/v1/favorites/{product_id}')

    assert response.status_code == 204


def test_add_favorite_unauthorized_returns_401(stubs):
    client = TestClient(_make_app(*stubs, user=None))

    response = client.put(f'/api/v1/favorites/{uuid4()}')

    assert response.status_code == 401


def test_add_favorite_non_buyer_returns_403(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.put(f'/api/v1/favorites/{uuid4()}')

    assert response.status_code == 403


def test_add_favorite_invalid_path_returns_400(stubs):
    user = _buyer()
    client = TestClient(_make_app(*stubs, user=user))

    response = client.put('/api/v1/favorites/not-a-uuid')

    assert response.status_code == 400
    assert response.json()['code'] == 'INVALID_REQUEST'


def test_user_id_from_query_is_ignored(stubs):
    """DoD: попытка передать чужой user_id (в query) игнорируется,
    use-case всегда вызывается с user_id из JWT.
    """
    add_stub, remove_stub, list_stub = stubs
    user = _buyer()
    attacker_target = uuid4()
    product_id = uuid4()
    add_stub.result = FavoriteCreatedResult(
        favorite=_make_favorite(user.id, product_id),
        created=True,
    )

    client = TestClient(_make_app(*stubs, user=user))

    # Попытка передать чужой user_id в query — должна быть проигнорирована
    response = client.put(f'/api/v1/favorites/{product_id}?user_id={attacker_target}')

    assert response.status_code == 204

    # Use-case был вызван именно с current_user (JWT), а не с чужим id
    data, current_user = add_stub.calls[0]
    assert current_user.id == user.id
    assert data.product_id == product_id


def test_remove_favorite_returns_204(stubs):
    add_stub, remove_stub, list_stub = stubs
    user = _buyer()
    product_id = uuid4()

    client = TestClient(_make_app(*stubs, user=user))
    response = client.delete(f'/api/v1/favorites/{product_id}')

    assert response.status_code == 204
    assert response.text == ''
    assert remove_stub.calls[0][0] == product_id
    assert remove_stub.calls[0][1].id == user.id


def test_remove_favorite_unauthorized_returns_401(stubs):
    client = TestClient(_make_app(*stubs, user=None))
    response = client.delete(f'/api/v1/favorites/{uuid4()}')
    assert response.status_code == 401


def test_remove_favorite_non_buyer_returns_403(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(*stubs, user=user))
    response = client.delete(f'/api/v1/favorites/{uuid4()}')
    assert response.status_code == 403


def test_list_favorites_returns_items(stubs):
    add_stub, remove_stub, list_stub = stubs
    user = _buyer()
    product_id = uuid4()
    list_stub.response = FavoriteListResponseSchema(
        items=[
            FavoriteProductSchema(
                favorite_id=uuid4(),
                product_id=product_id,
                created_at=datetime.now(UTC),
                product={'id': str(product_id), 'title': 'Cool'},
            )
        ],
        total=1,
    )

    client = TestClient(_make_app(*stubs, user=user))
    response = client.get('/api/v1/favorites')

    assert response.status_code == 200
    body = response.json()
    assert body['total'] == 1
    assert body['items'][0]['product']['title'] == 'Cool'
    assert list_stub.calls[0].id == user.id


def test_list_favorites_unauthorized_returns_401(stubs):
    client = TestClient(_make_app(*stubs, user=None))
    response = client.get('/api/v1/favorites')
    assert response.status_code == 401


def test_list_favorites_b2b_unavailable_returns_503(stubs):
    add_stub, remove_stub, list_stub = stubs
    user = _buyer()
    list_stub.error = B2BUnavailableError()

    client = TestClient(_make_app(*stubs, user=user))
    response = client.get('/api/v1/favorites')

    assert response.status_code == 503
    assert response.json()['code'] == 'SERVICE_UNAVAILABLE'
