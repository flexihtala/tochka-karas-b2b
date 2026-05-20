from dataclasses import dataclass
from uuid import UUID

from apps.cart.repositories import CartItemRepository, CartRepository
from apps.cart.schemas.db import (
    CartCreateSchema,
    CartItemCreateSchema,
    CartItemReadSchema,
    CartItemUpdateSchema,
)
from apps.cart.schemas.request import CartItemAddRequestSchema


@dataclass
class AddItemResult:
    """Результат AddItemUseCase: позиция + флаг "была ли уже"."""

    item: CartItemReadSchema
    created: bool


class AddItemUseCase:
    """POST /api/v1/cart/items — добавить SKU в корзину.

    Бизнес-правила (см. b2c-cart-flows.md, Flow B2C-8, edge case #8):
    - Если SKU уже есть в корзине — quantity += body.quantity (created=False, 200).
    - Если нет — создаётся новая позиция (created=True, 201).
    - Корзина создаётся лениво, если её ещё не существует для данной идентичности.
    - Lazy reserve: на этом шаге НЕ резервируем остатки в B2B.
    - Идентификация: user_id из JWT ИЛИ session_id из X-Session-Id (взаимоисключающе).
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
        data: CartItemAddRequestSchema,
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> AddItemResult:
        cart = await self._get_or_create_cart(user_id=user_id, session_id=session_id)

        existing = await self.cart_item_repository.get_by_cart_and_sku(cart.id, data.sku_id)
        if existing is not None:
            updated = await self.cart_item_repository.update(
                CartItemUpdateSchema(
                    id=existing.id,
                    quantity=existing.quantity + data.quantity,
                )
            )
            assert updated is not None
            return AddItemResult(item=updated, created=False)

        created = await self.cart_item_repository.create(
            CartItemCreateSchema(
                cart_id=cart.id,
                sku_id=data.sku_id,
                quantity=data.quantity,
            )
        )
        return AddItemResult(item=created, created=True)

    async def _get_or_create_cart(self, *, user_id: UUID | None, session_id: str | None):
        if user_id is not None:
            cart = await self.cart_repository.get_by_user(user_id)
            if cart is not None:
                return cart
            return await self.cart_repository.create(CartCreateSchema(user_id=user_id))

        assert session_id is not None
        cart = await self.cart_repository.get_by_session(session_id)
        if cart is not None:
            return cart
        return await self.cart_repository.create(CartCreateSchema(session_id=session_id))
