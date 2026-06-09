from uuid import UUID

from sqlalchemy import delete, select

from apps.cart.models import Cart
from apps.cart.schemas.db import CartCreateSchema, CartReadSchema, CartUpdateSchema
from shared.db import DBCrudRepository


class CartRepository(DBCrudRepository[Cart, CartCreateSchema, CartReadSchema, CartUpdateSchema]):
    async def get_by_user(self, user_id: UUID) -> CartReadSchema | None:
        query = select(Cart).where(Cart.user_id == user_id)

        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()

        return self.model_validate(model) if model else None

    async def get_by_session(self, session_id: str) -> CartReadSchema | None:
        query = select(Cart).where(Cart.session_id == session_id)

        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()

        return self.model_validate(model) if model else None

    async def delete_by_session(self, session_id: str) -> None:
        """Удаление гостевой корзины целиком — каскадно удалит cart_items."""
        query = delete(Cart).where(Cart.session_id == session_id)

        async with self.session_manager.get_session() as session:
            await session.execute(query)
