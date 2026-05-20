from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.blocking_reasons.schemas.db import (
    BlockingReasonCreateSchema,
    BlockingReasonReadSchema,
    BlockingReasonUpdateSchema,
)


def make_blocking_reason(
    *,
    id: UUID | None = None,
    name: str = 'Test Reason',
    description: str | None = 'Test description',
    hard_block: bool = False,
    is_active: bool = True,
) -> BlockingReasonReadSchema:
    now = datetime.now(UTC)
    return BlockingReasonReadSchema(
        id=id or uuid4(),
        name=name,
        description=description,
        hard_block=hard_block,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


class FakeBlockingReasonRepository:
    def __init__(self):
        self.by_id: dict[UUID, BlockingReasonReadSchema] = {}
        self.by_name: dict[str, BlockingReasonReadSchema] = {}
        self.created: list[BlockingReasonCreateSchema] = []
        self.updated: list[BlockingReasonUpdateSchema] = []

    async def create(self, data: BlockingReasonCreateSchema) -> BlockingReasonReadSchema:
        self.created.append(data)
        reason = make_blocking_reason(
            id=data.id or uuid4(),
            name=data.name,
            description=data.description,
            hard_block=data.hard_block,
            is_active=data.is_active,
        )
        self.add(reason)
        return reason

    async def get_or_none(self, id_: UUID) -> BlockingReasonReadSchema | None:
        return self.by_id.get(id_)

    async def get_by_name(self, name: str) -> BlockingReasonReadSchema | None:
        return self.by_name.get(name)

    async def update(self, data: BlockingReasonUpdateSchema) -> BlockingReasonReadSchema | None:
        existing = self.by_id.get(data.id)
        if existing is None:
            return None
        self.updated.append(data)
        update_payload = data.model_dump(exclude_unset=True, exclude={'id'})
        old_name = existing.name
        for key, value in update_payload.items():
            setattr(existing, key, value)
        self.by_id[data.id] = existing
        # rebuild by_name on rename
        if 'name' in update_payload and update_payload['name'] != old_name:
            self.by_name.pop(old_name, None)
        self.by_name[existing.name] = existing
        return existing

    async def list_(
        self,
        *,
        hard_block: bool | None = None,
        is_active: bool | None = None,
    ) -> list[BlockingReasonReadSchema]:
        items = list(self.by_id.values())
        if hard_block is not None:
            items = [r for r in items if r.hard_block == hard_block]
        if is_active is not None:
            items = [r for r in items if r.is_active == is_active]
        items.sort(key=lambda r: r.name)
        return items

    def add(self, reason: BlockingReasonReadSchema) -> None:
        self.by_id[reason.id] = reason
        self.by_name[reason.name] = reason
