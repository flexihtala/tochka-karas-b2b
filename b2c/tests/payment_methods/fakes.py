from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.payment_methods.schemas.db import (
    PaymentMethodCreateSchema,
    PaymentMethodReadSchema,
    PaymentMethodUpdateSchema,
)


class FakePaymentMethodRepository:
    def __init__(self):
        self.by_id: dict[UUID, PaymentMethodReadSchema] = {}
        self.created: list[PaymentMethodCreateSchema] = []
        self.updated: list[dict] = []
        self.deleted: list[UUID] = []
        self.default_unset_calls: list[tuple[UUID, UUID | None]] = []

    async def create(self, data: PaymentMethodCreateSchema) -> PaymentMethodReadSchema:
        self.created.append(data)
        method_id = data.id or uuid4()
        now = datetime.now(UTC)
        method = PaymentMethodReadSchema(
            id=method_id,
            buyer_id=data.buyer_id,
            brand=data.brand,
            last4=data.last4,
            exp_year=data.exp_year,
            exp_month=data.exp_month,
            is_default=data.is_default,
            created_at=now,
            updated_at=now,
        )
        self.by_id[method_id] = method
        return method

    async def get_or_none(self, id_: UUID) -> PaymentMethodReadSchema | None:
        return self.by_id.get(id_)

    async def update(self, data: PaymentMethodUpdateSchema) -> PaymentMethodReadSchema | None:
        existing = self.by_id.get(data.id)
        if existing is None:
            return None
        update_payload = data.model_dump(exclude_unset=True, exclude={'id'})
        self.updated.append({'id': data.id, **update_payload})
        merged = existing.model_dump()
        merged.update(update_payload)
        merged['updated_at'] = datetime.now(UTC)
        updated = PaymentMethodReadSchema.model_validate(merged)
        self.by_id[data.id] = updated
        return updated

    async def delete(self, id_: UUID) -> bool:
        self.deleted.append(id_)
        return self.by_id.pop(id_, None) is not None

    async def list_by_buyer(self, buyer_id: UUID) -> list[PaymentMethodReadSchema]:
        return sorted(
            (m for m in self.by_id.values() if m.buyer_id == buyer_id),
            key=lambda m: m.created_at,
        )

    async def unset_default_for_buyer(self, buyer_id: UUID, except_id: UUID | None = None) -> None:
        self.default_unset_calls.append((buyer_id, except_id))
        for method_id, method in self.by_id.items():
            if method.buyer_id == buyer_id and method.is_default and method_id != except_id:
                self.by_id[method_id] = method.model_copy(update={'is_default': False})

    def add(self, method: PaymentMethodReadSchema) -> None:
        self.by_id[method.id] = method
