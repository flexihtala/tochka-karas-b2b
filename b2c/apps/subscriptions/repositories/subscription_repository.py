from uuid import UUID

from sqlalchemy import delete, select

from apps.subscriptions.models import Subscription
from apps.subscriptions.schemas.db import (
    SubscriptionCreateSchema,
    SubscriptionReadSchema,
    SubscriptionUpdateSchema,
)
from shared.db import DBCrudRepository


class SubscriptionRepository(
    DBCrudRepository[Subscription, SubscriptionCreateSchema, SubscriptionReadSchema, SubscriptionUpdateSchema]
):
    async def get_by_user_and_product(self, user_id: UUID, product_id: UUID) -> SubscriptionReadSchema | None:
        query = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.product_id == product_id,
        )

        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()

        return self.model_validate(model) if model else None

    async def delete_by_user_and_product(self, user_id: UUID, product_id: UUID) -> bool:
        query = delete(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.product_id == product_id,
        )

        async with self.session_manager.get_session() as session:
            result = await session.execute(query)
            return bool(result.rowcount and result.rowcount > 0)
