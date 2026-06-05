"""Router-тесты cart — проверка HTTP-слоя через TestClient."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.cart.errors import CartItemNotFoundError
from apps.cart.routers import router as cart_router
from apps.cart.schemas.db import CartItemReadSchema
from apps.cart.schemas.request import CartItemAddRequestSchema, CartItemUpdateRequestSchema
from apps.cart.schemas.response import CartItemResponseSchema, CartResponseSchema
from apps.cart.use_cases import (
    AddItemUseCase,
    GetCartUseCase,
    MergeCartUseCase,
    RemoveItemUseCase,
    UpdateItemUseCase,
)
from apps.cart.use_cases.add_item import AddItemResult
from apps.errors import setup_error_handlers
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _empty_response(user_id: UUID | None = None, session_id: str | None = None) -> CartResponseSchema:
    return CartResponseSchema(
        id=uuid4(),
        user_id=user_id,
        session_id=session_id,
        items=[],
        total_amount=0,
        items_count=0,
        updated_at=datetime.now(UTC),
    )


class StubAddItem:
    def __init__(self):
        self.calls: list[tuple[CartItemAddRequestSchema, UUID | None, str | None]] = []
        self.created: bool = True
        self.error: Exception | None = None

    async def __call__(
        self,
        data: CartItemAddRequestSchema,
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> AddItemResult:
        self.calls.append((data, user_id, session_id))
        if self.error:
            raise self.error
        now = datetime.now(UTC)
        item = CartItemReadSchema(
            id=uuid4(),
            cart_id=uuid4(),
            sku_id=data.sku_id,
            quantity=data.quantity,
            created_at=now,
            updated_at=now,
        )
        return AddItemResult(item=item, created=self.created)


class StubUpdateItem:
    def __init__(self):
        self.calls: list[tuple[UUID, CartItemUpdateRequestSchema, UUID | None, str | None]] = []
        self.error: Exception | None = None

    async def __call__(
        self,
        item_id: UUID,
        data: CartItemUpdateRequestSchema,
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> CartItemReadSchema:
        self.calls.append((item_id, data, user_id, session_id))
        if self.error:
            raise self.error
        now = datetime.now(UTC)
        return CartItemReadSchema(
            id=item_id,
            cart_id=uuid4(),
            sku_id=uuid4(),
            quantity=data.quantity,
            created_at=now,
            updated_at=now,
        )


class StubRemoveItem:
    def __init__(self):
        self.calls: list[tuple[UUID, UUID | None, str | None]] = []
        self.error: Exception | None = None

    async def __call__(
        self,
        item_id: UUID,
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> None:
        self.calls.append((item_id, user_id, session_id))
        if self.error:
            raise self.error


class StubGetCart:
    def __init__(self):
        self.calls: list[tuple[UUID | None, str | None]] = []
        self.response: CartResponseSchema | None = None

    async def __call__(
        self,
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> CartResponseSchema:
        self.calls.append((user_id, session_id))
        return self.response or _empty_response(user_id=user_id, session_id=session_id)


class StubMergeCart:
    def __init__(self):
        self.calls: list[tuple[UUID, str]] = []
        self.error: Exception | None = None

    async def __call__(self, *, user_id: UUID, session_id: str) -> None:
        self.calls.append((user_id, session_id))
        if self.error:
            raise self.error


class CartRouteProvider(Provider):
    def __init__(
        self,
        add_stub: StubAddItem,
        update_stub: StubUpdateItem,
        remove_stub: StubRemoveItem,
        get_stub: StubGetCart,
        merge_stub: StubMergeCart,
    ):
        super().__init__()
        self.add_stub = add_stub
        self.update_stub = update_stub
        self.remove_stub = remove_stub
        self.get_stub = get_stub
        self.merge_stub = merge_stub

    @provide(scope=Scope.REQUEST)
    def get_add(self) -> AddItemUseCase:
        return self.add_stub

    @provide(scope=Scope.REQUEST)
    def get_update(self) -> UpdateItemUseCase:
        return self.update_stub

    @provide(scope=Scope.REQUEST)
    def get_remove(self) -> RemoveItemUseCase:
        return self.remove_stub

    @provide(scope=Scope.REQUEST)
    def get_get(self) -> GetCartUseCase:
        return self.get_stub

    @provide(scope=Scope.REQUEST)
    def get_merge(self) -> MergeCartUseCase:
        return self.merge_stub


def _make_app(
    add_stub: StubAddItem,
    update_stub: StubUpdateItem,
    remove_stub: StubRemoveItem,
    get_stub: StubGetCart,
    merge_stub: StubMergeCart,
    user: AuthenticatedUserSchema | None,
) -> FastAPI:
    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(cart_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        CartRouteProvider(add_stub, update_stub, remove_stub, get_stub, merge_stub),
    )
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs():
    return (
        StubAddItem(),
        StubUpdateItem(),
        StubRemoveItem(),
        StubGetCart(),
        StubMergeCart(),
    )


def test_get_cart_returns_200_for_authenticated_buyer(stubs):
    add_stub, update_stub, remove_stub, get_stub, merge_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.get('/api/v1/cart')

    assert response.status_code == 200
    assert get_stub.calls == [(user.id, None)]


def test_get_cart_returns_200_for_guest_with_session_id(stubs):
    add_stub, update_stub, remove_stub, get_stub, merge_stub = stubs
    session_id = str(uuid4())
    client = TestClient(_make_app(*stubs, user=None))

    response = client.get('/api/v1/cart', headers={'X-Session-Id': session_id})

    assert response.status_code == 200
    assert get_stub.calls == [(None, session_id)]


def test_get_cart_returns_400_without_identity(stubs):
    client = TestClient(_make_app(*stubs, user=None))

    response = client.get('/api/v1/cart')

    assert response.status_code == 400
    assert response.json()['code'] == 'MISSING_CART_IDENTITY'


def test_get_cart_ignores_session_id_when_authenticated(stubs):
    add_stub, update_stub, remove_stub, get_stub, merge_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.get('/api/v1/cart', headers={'X-Session-Id': str(uuid4())})

    assert response.status_code == 200
    # Session ID должен игнорироваться — see Flow B2C-8, §IDOR
    assert get_stub.calls == [(user.id, None)]


def test_add_item_returns_201_when_created(stubs):
    add_stub, update_stub, remove_stub, get_stub, merge_stub = stubs
    add_stub.created = True
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    sku_id = uuid4()
    response = client.post('/api/v1/cart/items', json={'sku_id': str(sku_id), 'quantity': 2})

    assert response.status_code == 201
    payload, _, _ = add_stub.calls[0]
    assert payload.sku_id == sku_id
    assert payload.quantity == 2


def test_add_item_returns_200_when_incremented(stubs):
    add_stub, update_stub, remove_stub, get_stub, merge_stub = stubs
    add_stub.created = False  # SKU уже был — инкремент
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.post('/api/v1/cart/items', json={'sku_id': str(uuid4()), 'quantity': 1})

    assert response.status_code == 200


def test_add_item_validation_error_for_zero_quantity(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.post('/api/v1/cart/items', json={'sku_id': str(uuid4()), 'quantity': 0})

    assert response.status_code == 400


def test_patch_item_returns_200_cart(stubs):
    add_stub, update_stub, remove_stub, get_stub, merge_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))
    sku_id = uuid4()

    response = client.patch(f'/api/v1/cart/items/{sku_id}', json={'quantity': 5})

    # Per openapi spec: PATCH returns the full updated cart, not a single item.
    assert response.status_code == 200
    body = response.json()
    assert 'items' in body
    # use-case вызван с sku_id из path
    assert update_stub.calls[0][0] == sku_id
    assert update_stub.calls[0][1].quantity == 5


def test_patch_item_returns_404_when_not_owned(stubs):
    add_stub, update_stub, remove_stub, get_stub, merge_stub = stubs
    update_stub.error = CartItemNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.patch(f'/api/v1/cart/items/{uuid4()}', json={'quantity': 2})

    assert response.status_code == 404
    assert response.json()['code'] == 'NOT_FOUND'


def test_delete_item_returns_200_cart(stubs):
    add_stub, update_stub, remove_stub, get_stub, merge_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))
    sku_id = uuid4()

    response = client.delete(f'/api/v1/cart/items/{sku_id}')

    # Per openapi spec: DELETE returns the full updated cart (200), not 204.
    assert response.status_code == 200
    body = response.json()
    assert 'items' in body
    assert remove_stub.calls[0][0] == sku_id


def test_delete_item_returns_404_for_foreign(stubs):
    add_stub, update_stub, remove_stub, get_stub, merge_stub = stubs
    remove_stub.error = CartItemNotFoundError()
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.delete(f'/api/v1/cart/items/{uuid4()}')

    assert response.status_code == 404


def test_merge_cart_requires_jwt(stubs):
    client = TestClient(_make_app(*stubs, user=None))

    response = client.post('/api/v1/cart/merge', headers={'X-Session-Id': str(uuid4())})

    # Без JWT — нет auth-корзины, в которую сливать
    assert response.status_code == 400
    assert response.json()['code'] == 'MISSING_CART_IDENTITY'


def test_merge_cart_requires_session_id(stubs):
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(*stubs, user=user))

    response = client.post('/api/v1/cart/merge')

    assert response.status_code == 400
    assert response.json()['code'] == 'MISSING_SESSION_ID'


def test_merge_cart_returns_200(stubs):
    add_stub, update_stub, remove_stub, get_stub, merge_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    session_id = str(uuid4())
    client = TestClient(_make_app(*stubs, user=user))

    response = client.post('/api/v1/cart/merge', headers={'X-Session-Id': session_id})

    assert response.status_code == 200
    assert merge_stub.calls == [(user.id, session_id)]
    # Возвращаем уже обновлённую корзину
    assert get_stub.calls == [(user.id, None)]


def test_response_model_contract():
    """Sanity check для контракта response — поля и их типы."""
    response = CartItemResponseSchema(
        id=uuid4(),
        sku_id=uuid4(),
        quantity=2,
        title='X',
        unit_price=100,
        available_quantity=10,
        line_total=200,
        unavailable_reason=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert response.unavailable_reason is None
    assert response.line_total == 200
