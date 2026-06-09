from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.subscriptions.schemas.db import (
    SubscriptionCreateSchema,
    SubscriptionReadSchema,
    SubscriptionUpdateSchema,
)


class FakeSubscriptionRepository:
    def __init__(self):
        self.by_id: dict[UUID, SubscriptionReadSchema] = {}
        self.created: list[SubscriptionCreateSchema] = []
        self.deleted: list[tuple[UUID, UUID]] = []

    async def create(self, data: SubscriptionCreateSchema) -> SubscriptionReadSchema:
        self.created.append(data)
        subscription_id = data.id or uuid4()
        now = datetime.now(UTC)
        subscription = SubscriptionReadSchema(
            id=subscription_id,
            user_id=data.user_id,
            product_id=data.product_id,
            notify_on=list(data.notify_on),
            created_at=now,
            updated_at=now,
        )
        self.by_id[subscription_id] = subscription
        return subscription

    async def get_or_none(self, id_: UUID) -> SubscriptionReadSchema | None:
        return self.by_id.get(id_)

    async def update(self, data: SubscriptionUpdateSchema) -> SubscriptionReadSchema | None:
        existing = self.by_id.get(data.id)
        if existing is None:
            return None
        update_payload = data.model_dump(exclude_unset=True, exclude={'id'})
        merged = existing.model_dump()
        merged.update(update_payload)
        merged['updated_at'] = datetime.now(UTC)
        updated = SubscriptionReadSchema.model_validate(merged)
        self.by_id[data.id] = updated
        return updated

    async def delete(self, id_: UUID) -> bool:
        return self.by_id.pop(id_, None) is not None

    async def get_by_user_and_product(self, user_id: UUID, product_id: UUID) -> SubscriptionReadSchema | None:
        for sub in self.by_id.values():
            if sub.user_id == user_id and sub.product_id == product_id:
                return sub
        return None

    async def delete_by_user_and_product(self, user_id: UUID, product_id: UUID) -> bool:
        target_id: UUID | None = None
        for sub_id, sub in self.by_id.items():
            if sub.user_id == user_id and sub.product_id == product_id:
                target_id = sub_id
                break
        if target_id is None:
            return False
        del self.by_id[target_id]
        self.deleted.append((user_id, product_id))
        return True

    def add(self, subscription: SubscriptionReadSchema) -> None:
        self.by_id[subscription.id] = subscription
