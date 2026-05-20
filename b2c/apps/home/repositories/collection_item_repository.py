from uuid import UUID

from sqlalchemy import select

from apps.home.models import CollectionItem
from apps.home.schemas.db import (
    CollectionItemCreateSchema,
    CollectionItemReadSchema,
    CollectionItemUpdateSchema,
)
from shared.db import DBCrudRepository


class CollectionItemRepository(
    DBCrudRepository[
        CollectionItem,
        CollectionItemCreateSchema,
        CollectionItemReadSchema,
        CollectionItemUpdateSchema,
    ]
):
    async def list_by_collection(self, collection_id: UUID) -> list[CollectionItemReadSchema]:
        """Привязки товаров к подборке, отсортированы по ordering ASC."""
        query = (
            select(CollectionItem)
            .where(CollectionItem.collection_id == collection_id)
            .order_by(CollectionItem.ordering.asc(), CollectionItem.created_at.asc())
        )

        async with self.session_manager.get_session() as session:
            models = (await session.execute(query)).scalars().all()

        return [self.model_validate(model) for model in models]
