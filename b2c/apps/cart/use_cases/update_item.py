from uuid import UUID

import httpx

from apps.cart.errors import (
    B2BUnavailableError,
    CartItemNotFoundError,
    InsufficientStockError,
    SkuUnavailableError,
)
from apps.cart.repositories import CartItemRepository, CartRepository
from apps.cart.schemas.db import CartItemReadSchema, CartItemUpdateSchema
from apps.cart.schemas.request import CartItemUpdateRequestSchema
from shared.http_clients import ServiceClient, ServiceClientError


class UpdateItemUseCase:
    """PATCH /api/v1/cart/items/{sku_id} — изменить quantity позиции.

    Бизнес-правила (per openapi spec + Flow B2C-8):
    - Path-параметр — sku_id (а не внутренний item_id); позиция уникальна
      в корзине по (cart_id, sku_id).
    - quantity >= 1 (для удаления — DELETE).
    - Если корзины/позиции нет — 404 (enumeration-защита).
    - Перед апдейтом валидируем остаток в B2B `GET /api/v1/public/skus/{sku_id}`:
        - 404 → SkuUnavailableError (404); сеть/5xx → B2BUnavailableError (503).
        - active_quantity < new_quantity → InsufficientStockError (409).
    - Lazy reserve: остаток только читается, ничего не резервируется.
    """

    def __init__(
        self,
        cart_repository: CartRepository,
        cart_item_repository: CartItemRepository,
        b2b_client: ServiceClient,
    ):
        self.cart_repository = cart_repository
        self.cart_item_repository = cart_item_repository
        self.b2b_client = b2b_client

    async def __call__(
        self,
        sku_id: UUID,
        data: CartItemUpdateRequestSchema,
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> CartItemReadSchema:
        cart = await self._get_owned_cart(user_id=user_id, session_id=session_id)
        if cart is None:
            raise CartItemNotFoundError()

        existing = await self.cart_item_repository.get_by_cart_and_sku(cart.id, sku_id)
        if existing is None:
            raise CartItemNotFoundError()

        sku = await self._fetch_sku(sku_id)
        if int(sku.get('active_quantity', 0)) < data.quantity:
            raise InsufficientStockError()

        updated = await self.cart_item_repository.update(CartItemUpdateSchema(id=existing.id, quantity=data.quantity))
        if updated is None:
            raise CartItemNotFoundError()
        return updated

    async def _fetch_sku(self, sku_id: UUID) -> dict:
        try:
            return await self.b2b_client.get(f'/api/v1/public/skus/{sku_id}')
        except ServiceClientError as exc:
            if exc.status_code == 404:
                raise SkuUnavailableError() from exc
            raise B2BUnavailableError() from exc
        except httpx.HTTPError as exc:
            raise B2BUnavailableError() from exc

    async def _get_owned_cart(self, *, user_id: UUID | None, session_id: str | None):
        if user_id is not None:
            return await self.cart_repository.get_by_user(user_id)
        assert session_id is not None
        return await self.cart_repository.get_by_session(session_id)
