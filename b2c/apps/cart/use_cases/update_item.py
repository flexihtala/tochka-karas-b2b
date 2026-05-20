from uuid import UUID

from apps.cart.errors import CartItemNotFoundError
from apps.cart.repositories import CartItemRepository, CartRepository
from apps.cart.schemas.db import CartItemReadSchema, CartItemUpdateSchema
from apps.cart.schemas.request import CartItemUpdateRequestSchema


class UpdateItemUseCase:
    """PATCH /api/v1/cart/items/{id} — изменить quantity позиции.

    Бизнес-правила:
    - Позиция должна принадлежать корзине текущей идентичности, иначе 404
      (enumeration-защита — не светим существование чужих item_id).
    - quantity >= 1 (для удаления — DELETE).
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
        item_id: UUID,
        data: CartItemUpdateRequestSchema,
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> CartItemReadSchema:
        existing = await self.cart_item_repository.get_or_none(item_id)
        if existing is None:
            raise CartItemNotFoundError()

        if not await self._cart_belongs_to_identity(existing.cart_id, user_id=user_id, session_id=session_id):
            raise CartItemNotFoundError()

        updated = await self.cart_item_repository.update(CartItemUpdateSchema(id=item_id, quantity=data.quantity))
        if updated is None:
            raise CartItemNotFoundError()
        return updated

    async def _cart_belongs_to_identity(
        self,
        cart_id: UUID,
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> bool:
        if user_id is not None:
            cart = await self.cart_repository.get_by_user(user_id)
        else:
            assert session_id is not None
            cart = await self.cart_repository.get_by_session(session_id)
        return cart is not None and cart.id == cart_id
