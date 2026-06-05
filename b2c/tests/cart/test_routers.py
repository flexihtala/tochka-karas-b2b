"""Router-тесты cart — проверка HTTP-слоя через TestClient."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.cart.errors import CartItemNotFoundError, InsufficientStockError, SkuUnavailableError
from apps.cart.routers import router as cart_router
from apps.cart.schemas.db import CartItemReadSchema
from apps.cart.schemas.request import CartItemAddRequestSchema, CartItemUpdateRequestSchema
from apps.cart.schemas.response import (
    CartItemResponseSchema,
    CartResponseSchema,
    CartValidationResponseSchema,
)
from apps.cart.use_cases import (
    AddItemUseCase,
    ClearCartUseCase,
    GetCartUseCase,
    MergeCartUseCase,
    RemoveItemUseCase,
    UpdateItemUseCase,
    ValidateCartUseCase,
)
from apps.cart.use_cases.add_item import AddItemResult
from apps.errors import setup_error_handlers
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _empty_response() -> CartResponseSchema:
    return CartResponseSchema(id=uuid4(), updated_at=datetime.now(UTC))


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
            product_id=uuid4(),
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
            product_id=uuid4(),
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
        return self.response or _empty_response()


class StubMergeCart:
    def __init__(self):
        self.calls: list[tuple[UUID, str]] = []
        self.error: Exception | None = None

    async def __call__(self, *, user_id: UUID, session_id: str) -> None:
        self.calls.append((user_id, session_id))
        if self.error:
            raise self.error


class StubClearCart:
    def __init__(self):
        self.calls: list[tuple[UUID | None, str | None]] = []

    async def __call__(self, *, user_id: UUID | None, session_id: str | None) -> None:
        self.calls.append((user_id, session_id))


class StubValidateCart:
    def __init__(self):
        self.calls: list[tuple[UUID | None, str | None]] = []
        self.response: CartValidationResponseSchema | None = None

    async def __call__(self, *, user_id: UUID | None, session_id: str | None) -> CartValidationResponseSchema:
        self.calls.append((user_id, session_id))
        return self.response or CartValidationResponseSchema(is_valid=True, cart=_empty_response(), issues=[])


class CartRouteProvider(Provider):
    def __init__(self, stubs: 'Stubs'):
        super().__init__()
        self.stubs = stubs

    @provide(scope=Scope.REQUEST)
    def get_add(self) -> AddItemUseCase:
        return self.stubs.add

    @provide(scope=Scope.REQUEST)
    def get_update(self) -> UpdateItemUseCase:
        return self.stubs.update

    @provide(scope=Scope.REQUEST)
    def get_remove(self) -> RemoveItemUseCase:
        return self.stubs.remove

    @provide(scope=Scope.REQUEST)
    def get_get(self) -> GetCartUseCase:
        return self.stubs.get

    @provide(scope=Scope.REQUEST)
    def get_merge(self) -> MergeCartUseCase:
        return self.stubs.merge

    @provide(scope=Scope.REQUEST)
    def get_clear(self) -> ClearCartUseCase:
        return self.stubs.clear

    @provide(scope=Scope.REQUEST)
    def get_validate(self) -> ValidateCartUseCase:
        return self.stubs.validate


class Stubs:
    def __init__(self):
        self.add = StubAddItem()
        self.update = StubUpdateItem()
        self.remove = StubRemoveItem()
        self.get = StubGetCart()
        self.merge = StubMergeCart()
        self.clear = StubClearCart()
        self.validate = StubValidateCart()


def _make_app(stubs: Stubs, user: AuthenticatedUserSchema | None) -> FastAPI:
    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(cart_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), CartRouteProvider(stubs))
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs() -> Stubs:
    return Stubs()


def _buyer() -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)


def test_get_cart_returns_200_for_authenticated_buyer(stubs):
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    response = client.get('/api/v1/cart')

    assert response.status_code == 200
    assert stubs.get.calls == [(user.id, None)]


def test_get_cart_returns_200_for_guest_with_session_id(stubs):
    session_id = str(uuid4())
    client = TestClient(_make_app(stubs, user=None))

    response = client.get('/api/v1/cart', headers={'X-Session-Id': session_id})

    assert response.status_code == 200
    assert stubs.get.calls == [(None, session_id)]


def test_get_cart_returns_400_without_identity(stubs):
    client = TestClient(_make_app(stubs, user=None))

    response = client.get('/api/v1/cart')

    assert response.status_code == 400
    assert response.json()['code'] == 'MISSING_CART_IDENTITY'


def test_get_cart_ignores_session_id_when_authenticated(stubs):
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    response = client.get('/api/v1/cart', headers={'X-Session-Id': str(uuid4())})

    assert response.status_code == 200
    # Session ID должен игнорироваться — see Flow B2C-8, §IDOR
    assert stubs.get.calls == [(user.id, None)]


def test_clear_cart_returns_204(stubs):
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    response = client.delete('/api/v1/cart')

    assert response.status_code == 204
    assert response.content == b''
    assert stubs.clear.calls == [(user.id, None)]


def test_clear_cart_guest_uses_session(stubs):
    session_id = str(uuid4())
    client = TestClient(_make_app(stubs, user=None))

    response = client.delete('/api/v1/cart', headers={'X-Session-Id': session_id})

    assert response.status_code == 204
    assert stubs.clear.calls == [(None, session_id)]


def test_clear_cart_requires_identity(stubs):
    client = TestClient(_make_app(stubs, user=None))

    response = client.delete('/api/v1/cart')

    assert response.status_code == 400
    assert response.json()['code'] == 'MISSING_CART_IDENTITY'


def test_add_item_returns_201_when_created(stubs):
    stubs.add.created = True
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    sku_id = uuid4()
    response = client.post('/api/v1/cart/items', json={'sku_id': str(sku_id), 'quantity': 2})

    assert response.status_code == 201
    payload, _, _ = stubs.add.calls[0]
    assert payload.sku_id == sku_id
    assert payload.quantity == 2


def test_add_item_returns_200_when_incremented(stubs):
    stubs.add.created = False  # SKU уже был — инкремент
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    response = client.post('/api/v1/cart/items', json={'sku_id': str(uuid4()), 'quantity': 1})

    assert response.status_code == 200


def test_add_item_validation_error_for_zero_quantity(stubs):
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    response = client.post('/api/v1/cart/items', json={'sku_id': str(uuid4()), 'quantity': 0})

    assert response.status_code == 400


def test_add_item_returns_404_when_sku_unavailable(stubs):
    stubs.add.error = SkuUnavailableError()
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    response = client.post('/api/v1/cart/items', json={'sku_id': str(uuid4()), 'quantity': 1})

    assert response.status_code == 404
    assert response.json()['code'] == 'SKU_NOT_FOUND'


def test_add_item_returns_409_when_insufficient_stock(stubs):
    stubs.add.error = InsufficientStockError()
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    response = client.post('/api/v1/cart/items', json={'sku_id': str(uuid4()), 'quantity': 99})

    assert response.status_code == 409
    assert response.json()['code'] == 'INSUFFICIENT_STOCK'


def test_patch_item_returns_200_cart(stubs):
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))
    sku_id = uuid4()

    response = client.patch(f'/api/v1/cart/items/{sku_id}', json={'quantity': 5})

    # Per openapi spec: PATCH returns the full updated cart, not a single item.
    assert response.status_code == 200
    body = response.json()
    assert 'items' in body
    assert stubs.update.calls[0][0] == sku_id
    assert stubs.update.calls[0][1].quantity == 5


def test_patch_item_returns_404_when_not_owned(stubs):
    stubs.update.error = CartItemNotFoundError()
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    response = client.patch(f'/api/v1/cart/items/{uuid4()}', json={'quantity': 2})

    assert response.status_code == 404
    assert response.json()['code'] == 'NOT_FOUND'


def test_patch_item_returns_409_on_insufficient_stock(stubs):
    stubs.update.error = InsufficientStockError()
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    response = client.patch(f'/api/v1/cart/items/{uuid4()}', json={'quantity': 100})

    assert response.status_code == 409
    assert response.json()['code'] == 'INSUFFICIENT_STOCK'


def test_delete_item_returns_200_cart(stubs):
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))
    sku_id = uuid4()

    response = client.delete(f'/api/v1/cart/items/{sku_id}')

    # Per openapi spec: DELETE returns the full updated cart (200), not 204.
    assert response.status_code == 200
    body = response.json()
    assert 'items' in body
    assert stubs.remove.calls[0][0] == sku_id


def test_delete_item_returns_404_for_foreign(stubs):
    stubs.remove.error = CartItemNotFoundError()
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    response = client.delete(f'/api/v1/cart/items/{uuid4()}')

    assert response.status_code == 404


def test_validate_cart_returns_200(stubs):
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    response = client.post('/api/v1/cart/validate')

    assert response.status_code == 200
    body = response.json()
    assert 'is_valid' in body
    assert 'cart' in body
    assert 'issues' in body
    assert stubs.validate.calls == [(user.id, None)]


def test_validate_cart_requires_identity(stubs):
    client = TestClient(_make_app(stubs, user=None))

    response = client.post('/api/v1/cart/validate')

    assert response.status_code == 400
    assert response.json()['code'] == 'MISSING_CART_IDENTITY'


def test_merge_cart_requires_jwt(stubs):
    client = TestClient(_make_app(stubs, user=None))

    response = client.post('/api/v1/cart/merge', headers={'X-Session-Id': str(uuid4())})

    # Без JWT — нет auth-корзины, в которую сливать
    assert response.status_code == 400
    assert response.json()['code'] == 'MISSING_CART_IDENTITY'


def test_merge_cart_requires_session_id(stubs):
    user = _buyer()
    client = TestClient(_make_app(stubs, user=user))

    response = client.post('/api/v1/cart/merge')

    assert response.status_code == 400
    assert response.json()['code'] == 'MISSING_SESSION_ID'


def test_merge_cart_returns_200(stubs):
    user = _buyer()
    session_id = str(uuid4())
    client = TestClient(_make_app(stubs, user=user))

    response = client.post('/api/v1/cart/merge', headers={'X-Session-Id': session_id})

    assert response.status_code == 200
    assert stubs.merge.calls == [(user.id, session_id)]
    # Возвращаем уже обновлённую корзину
    assert stubs.get.calls == [(user.id, None)]


def test_response_model_contract():
    """Sanity check для контракта response — поля и их типы (OpenAPI CartItem)."""
    item = CartItemResponseSchema(
        sku_id=uuid4(),
        product_id=uuid4(),
        name='Nike 42',
        quantity=2,
        unit_price=100,
        line_total=200,
        available_quantity=10,
        is_available=True,
    )
    assert item.is_available is True
    assert item.line_total == 200
    assert item.unavailable_reason is None
    assert item.sku_code is None

    cart = CartResponseSchema(items=[item], items_count=2, subtotal=200, is_valid=True)
    dumped = cart.model_dump()
    # Поля, которые spec убрал, отсутствуют
    assert 'total_amount' not in dumped
    assert 'user_id' not in dumped
    assert 'session_id' not in dumped
    # Поля, которые spec требует, присутствуют
    assert {'items', 'items_count', 'subtotal', 'is_valid'} <= dumped.keys()
