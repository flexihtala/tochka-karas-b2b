from uuid import UUID

from apps.cart.repositories import CartItemRepository, CartRepository
from apps.cart.schemas.db import (
    CartCreateSchema,
    CartItemCreateSchema,
    CartItemUpdateSchema,
)


class MergeCartUseCase:
    """POST /api/v1/cart/merge — слить гостевую корзину в авторизованную.

    Стратегия (см. b2c-cart-flows.md, Flow B2C-8 §"Merge гостевой корзины при логине"):
    1. Загружаем гостевую корзину по session_id.
    2. Загружаем/создаём авторизованную по user_id.
    3. Для каждой guest-позиции:
       - Если такой sku_id уже есть в auth-корзине → quantity = MAX(guest_qty, auth_qty).
       - Иначе создаём новую позицию в auth-корзине.
    4. Удаляем гостевую корзину целиком (cart_items уйдут каскадом).

    Если у гостя пустая корзина / её вовсе нет — это no-op (вернётся текущая
    авторизованная корзина или будет создана пустая).
    """

    def __init__(
        self,
        cart_repository: CartRepository,
        cart_item_repository: CartItemRepository,
    ):
        self.cart_repository = cart_repository
        self.cart_item_repository = cart_item_repository

    async def __call__(self, *, user_id: UUID, session_id: str) -> None:
        guest_cart = await self.cart_repository.get_by_session(session_id)

        auth_cart = await self.cart_repository.get_by_user(user_id)
        if auth_cart is None:
            auth_cart = await self.cart_repository.create(CartCreateSchema(user_id=user_id))

        if guest_cart is None:
            return

        guest_items = await self.cart_item_repository.list_by_cart(guest_cart.id)
        for guest_item in guest_items:
            existing = await self.cart_item_repository.get_by_cart_and_sku(auth_cart.id, guest_item.sku_id)
            if existing is None:
                await self.cart_item_repository.create(
                    CartItemCreateSchema(
                        cart_id=auth_cart.id,
                        sku_id=guest_item.sku_id,
                        product_id=guest_item.product_id,
                        quantity=guest_item.quantity,
                    )
                )
            else:
                merged_quantity = max(existing.quantity, guest_item.quantity)
                if merged_quantity != existing.quantity:
                    await self.cart_item_repository.update(
                        CartItemUpdateSchema(id=existing.id, quantity=merged_quantity)
                    )

        await self.cart_repository.delete_by_session(session_id)
