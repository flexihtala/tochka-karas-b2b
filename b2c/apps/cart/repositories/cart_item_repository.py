from uuid import UUID

from sqlalchemy import select

from apps.cart.models import CartItem
from apps.cart.schemas.db import (
    CartItemCreateSchema,
    CartItemReadSchema,
    CartItemUpdateSchema,
)
from shared.db import DBCrudRepository


class CartItemRepository(DBCrudRepository[CartItem, CartItemCreateSchema, CartItemReadSchema, CartItemUpdateSchema]):
    async def list_by_cart(self, cart_id: UUID) -> list[CartItemReadSchema]:
        query = select(CartItem).where(CartItem.cart_id == cart_id).order_by(CartItem.created_at.asc())

        async with self.session_manager.get_session() as session:
            models = (await session.execute(query)).scalars().all()

        return [self.model_validate(model) for model in models]

    async def get_by_cart_and_sku(self, cart_id: UUID, sku_id: UUID) -> CartItemReadSchema | None:
        query = select(CartItem).where(CartItem.cart_id == cart_id, CartItem.sku_id == sku_id)

        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()

        return self.model_validate(model) if model else None
