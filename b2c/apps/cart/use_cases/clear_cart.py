from uuid import UUID

from apps.cart.repositories import CartItemRepository, CartRepository


class ClearCartUseCase:
    """DELETE /api/v1/cart — очистить корзину целиком (204).

    Находит корзину текущей идентичности и удаляет все её cart_items.
    Сама запись корзины сохраняется (она пустая). Если корзины нет — no-op.
    """

    def __init__(
        self,
        cart_repository: CartRepository,
        cart_item_repository: CartItemRepository,
    ):
        self.cart_repository = cart_repository
        self.cart_item_repository = cart_item_repository

    async def __call__(self, *, user_id: UUID | None, session_id: str | None) -> None:
        cart = await self._get_owned_cart(user_id=user_id, session_id=session_id)
        if cart is None:
            return
        await self.cart_item_repository.delete_by_cart(cart.id)

    async def _get_owned_cart(self, *, user_id: UUID | None, session_id: str | None):
        if user_id is not None:
            return await self.cart_repository.get_by_user(user_id)
        assert session_id is not None
        return await self.cart_repository.get_by_session(session_id)
