from uuid import UUID

from apps.cart.errors import CartItemNotFoundError
from apps.cart.repositories import CartItemRepository, CartRepository


class RemoveItemUseCase:
    """DELETE /api/v1/cart/items/{sku_id} — удалить позицию из корзины.

    Per openapi spec: path-параметр — sku_id. Позиция уникальна по
    (cart_id, sku_id). Если корзины/позиции нет — 404
    (enumeration-защита, см. flow B2C-8).
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
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> None:
        cart = await self._get_owned_cart(user_id=user_id, session_id=session_id)
        if cart is None:
            raise CartItemNotFoundError()

        existing = await self.cart_item_repository.get_by_cart_and_sku(cart.id, sku_id)
        if existing is None:
            raise CartItemNotFoundError()

        await self.cart_item_repository.delete(existing.id)

    async def _get_owned_cart(self, *, user_id: UUID | None, session_id: str | None):
        if user_id is not None:
            return await self.cart_repository.get_by_user(user_id)
        assert session_id is not None
        return await self.cart_repository.get_by_session(session_id)
