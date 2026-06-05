from uuid import UUID

from apps.cart.errors import CartItemNotFoundError
from apps.cart.repositories import CartItemRepository, CartRepository
from apps.cart.schemas.db import CartItemReadSchema, CartItemUpdateSchema
from apps.cart.schemas.request import CartItemUpdateRequestSchema


class UpdateItemUseCase:
    """PATCH /api/v1/cart/items/{sku_id} — изменить quantity позиции.

    Бизнес-правила (per openapi spec):
    - Path-параметр — sku_id (а не внутренний item_id); позиция уникальна
      в корзине по (cart_id, sku_id).
    - quantity >= 1 (для удаления — DELETE).
    - Если корзины/позиции нет — 404 (enumeration-защита).
    """

    def __init__(
        self,
        cart_repository: CartRepository,
        cart_item_repository: CartItemRepository,
    ):
        self.cart_repository = cart_repository
        self.cart_item_repository = cart_item_repository

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

        updated = await self.cart_item_repository.update(
            CartItemUpdateSchema(id=existing.id, quantity=data.quantity)
        )
        if updated is None:
            raise CartItemNotFoundError()
        return updated

    async def _get_owned_cart(self, *, user_id: UUID | None, session_id: str | None):
        if user_id is not None:
            return await self.cart_repository.get_by_user(user_id)
        assert session_id is not None
        return await self.cart_repository.get_by_session(session_id)
