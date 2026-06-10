from uuid import UUID

from sqlalchemy import delete, select

from apps.favorites.models import Favorite
from apps.favorites.schemas.db import (
    FavoriteCreateSchema,
    FavoriteReadSchema,
    FavoriteUpdateSchema,
)
from shared.db import DBCrudRepository


class FavoriteRepository(
    DBCrudRepository[Favorite, FavoriteCreateSchema, FavoriteReadSchema, FavoriteUpdateSchema],
):
    async def get_by_user_and_product(self, user_id: UUID, product_id: UUID) -> FavoriteReadSchema | None:
        """Возвращает существующее избранное (user_id, product_id) — для идемпотентного POST."""
        query = select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.product_id == product_id,
        )
        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()

        return self.model_validate(model) if model else None

    async def list_by_user(self, user_id: UUID) -> list[FavoriteReadSchema]:
        """Список избранного покупателя, упорядоченный по дате добавления (asc)."""
        query = select(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at.asc())
        async with self.session_manager.get_session() as session:
            models = (await session.execute(query)).scalars().all()

        return [self.model_validate(model) for model in models]

    async def delete_by_user_and_product(self, user_id: UUID, product_id: UUID) -> bool:
        """Идемпотентное удаление (user_id, product_id). True — если что-то удалили."""
        query = delete(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.product_id == product_id,
        )
        async with self.session_manager.get_session() as session:
            result = await session.execute(query)
            return bool(result.rowcount and result.rowcount > 0)
