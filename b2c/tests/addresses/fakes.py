from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.addresses.schemas.db import AddressCreateSchema, AddressReadSchema, AddressUpdateSchema


class FakeAddressRepository:
    def __init__(self):
        self.by_id: dict[UUID, AddressReadSchema] = {}
        self.created: list[AddressCreateSchema] = []
        self.updated: list[dict] = []
        self.deleted: list[UUID] = []
        self.default_unset_calls: list[tuple[UUID, UUID | None]] = []

    async def create(self, data: AddressCreateSchema) -> AddressReadSchema:
        self.created.append(data)
        address_id = data.id or uuid4()
        now = datetime.now(UTC)
        address = AddressReadSchema(
            id=address_id,
            buyer_id=data.buyer_id,
            country=data.country,
            city=data.city,
            street=data.street,
            postal_code=data.postal_code,
            comment=data.comment,
            is_default=data.is_default,
            created_at=now,
            updated_at=now,
        )
        self.by_id[address_id] = address
        return address

    async def get_or_none(self, id_: UUID) -> AddressReadSchema | None:
        return self.by_id.get(id_)

    async def update(self, data: AddressUpdateSchema) -> AddressReadSchema | None:
        existing = self.by_id.get(data.id)
        if existing is None:
            return None
        update_payload = data.model_dump(exclude_unset=True, exclude={'id'})
        self.updated.append({'id': data.id, **update_payload})
        merged = existing.model_dump()
        merged.update(update_payload)
        merged['updated_at'] = datetime.now(UTC)
        updated = AddressReadSchema.model_validate(merged)
        self.by_id[data.id] = updated
        return updated

    async def delete(self, id_: UUID) -> bool:
        self.deleted.append(id_)
        return self.by_id.pop(id_, None) is not None

    async def list_by_buyer(self, buyer_id: UUID) -> list[AddressReadSchema]:
        return sorted(
            (a for a in self.by_id.values() if a.buyer_id == buyer_id),
            key=lambda a: a.created_at,
        )

    async def unset_default_for_buyer(self, buyer_id: UUID, except_id: UUID | None = None) -> None:
        self.default_unset_calls.append((buyer_id, except_id))
        for addr_id, addr in self.by_id.items():
            if addr.buyer_id == buyer_id and addr.is_default and addr_id != except_id:
                self.by_id[addr_id] = addr.model_copy(update={'is_default': False})

    def add(self, address: AddressReadSchema) -> None:
        self.by_id[address.id] = address
