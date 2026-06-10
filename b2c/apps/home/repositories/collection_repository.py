from sqlalchemy import select

from apps.home.models import Collection
from apps.home.schemas.db import CollectionCreateSchema, CollectionReadSchema, CollectionUpdateSchema
from shared.db import DBCrudRepository


class CollectionRepository(
    DBCrudRepository[Collection, CollectionCreateSchema, CollectionReadSchema, CollectionUpdateSchema]
):
    async def list_active(self) -> list[CollectionReadSchema]:
        """Активные подборки в порядке выдачи: position ASC, created_at ASC."""
        query = (
            select(Collection)
            .where(Collection.is_active.is_(True))
            .order_by(Collection.position.asc(), Collection.created_at.asc())
        )

        async with self.session_manager.get_session() as session:
            models = (await session.execute(query)).scalars().all()

        return [self.model_validate(model) for model in models]
