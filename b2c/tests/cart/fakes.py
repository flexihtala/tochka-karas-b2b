from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.cart.schemas.db import (
    CartCreateSchema,
    CartItemCreateSchema,
    CartItemReadSchema,
    CartItemUpdateSchema,
    CartReadSchema,
    CartUpdateSchema,
)


class FakeCartRepository:
    def __init__(self):
        self.by_id: dict[UUID, CartReadSchema] = {}
        self.created: list[CartCreateSchema] = []
        self.updated: list[dict] = []
        self.deleted_by_session: list[str] = []

    async def create(self, data: CartCreateSchema) -> CartReadSchema:
        self.created.append(data)
        cart_id = data.id or uuid4()
        now = datetime.now(UTC)
        cart = CartReadSchema(
            id=cart_id,
            user_id=data.user_id,
            session_id=data.session_id,
            created_at=now,
            updated_at=now,
        )
        self.by_id[cart_id] = cart
        return cart

    async def get_or_none(self, id_: UUID) -> CartReadSchema | None:
        return self.by_id.get(id_)

    async def update(self, data: CartUpdateSchema) -> CartReadSchema | None:
        existing = self.by_id.get(data.id)
        if existing is None:
            return None
        update_payload = data.model_dump(exclude_unset=True, exclude={'id'})
        self.updated.append({'id': data.id, **update_payload})
        merged = existing.model_dump()
        merged.update(update_payload)
        merged['updated_at'] = datetime.now(UTC)
        updated = CartReadSchema.model_validate(merged)
        self.by_id[data.id] = updated
        return updated

    async def delete(self, id_: UUID) -> bool:
        return self.by_id.pop(id_, None) is not None

    async def get_by_user(self, user_id: UUID) -> CartReadSchema | None:
        for cart in self.by_id.values():
            if cart.user_id == user_id:
                return cart
        return None

    async def get_by_session(self, session_id: str) -> CartReadSchema | None:
        for cart in self.by_id.values():
            if cart.session_id == session_id:
                return cart
        return None

    async def delete_by_session(self, session_id: str) -> None:
        self.deleted_by_session.append(session_id)
        targets = [cid for cid, c in self.by_id.items() if c.session_id == session_id]
        for cid in targets:
            self.by_id.pop(cid, None)

    def add(self, cart: CartReadSchema) -> None:
        self.by_id[cart.id] = cart


class FakeCartItemRepository:
    def __init__(self):
        self.by_id: dict[UUID, CartItemReadSchema] = {}
        self.created: list[CartItemCreateSchema] = []
        self.updated: list[dict] = []
        self.deleted: list[UUID] = []

    async def create(self, data: CartItemCreateSchema) -> CartItemReadSchema:
        self.created.append(data)
        item_id = data.id or uuid4()
        now = datetime.now(UTC)
        item = CartItemReadSchema(
            id=item_id,
            cart_id=data.cart_id,
            sku_id=data.sku_id,
            quantity=data.quantity,
            created_at=now,
            updated_at=now,
        )
        self.by_id[item_id] = item
        return item

    async def get_or_none(self, id_: UUID) -> CartItemReadSchema | None:
        return self.by_id.get(id_)

    async def update(self, data: CartItemUpdateSchema) -> CartItemReadSchema | None:
        existing = self.by_id.get(data.id)
        if existing is None:
            return None
        update_payload = data.model_dump(exclude_unset=True, exclude={'id'})
        self.updated.append({'id': data.id, **update_payload})
        merged = existing.model_dump()
        merged.update(update_payload)
        merged['updated_at'] = datetime.now(UTC)
        updated = CartItemReadSchema.model_validate(merged)
        self.by_id[data.id] = updated
        return updated

    async def delete(self, id_: UUID) -> bool:
        self.deleted.append(id_)
        return self.by_id.pop(id_, None) is not None

    async def list_by_cart(self, cart_id: UUID) -> list[CartItemReadSchema]:
        return sorted(
            (i for i in self.by_id.values() if i.cart_id == cart_id),
            key=lambda i: i.created_at,
        )

    async def get_by_cart_and_sku(self, cart_id: UUID, sku_id: UUID) -> CartItemReadSchema | None:
        for item in self.by_id.values():
            if item.cart_id == cart_id and item.sku_id == sku_id:
                return item
        return None

    def add(self, item: CartItemReadSchema) -> None:
        self.by_id[item.id] = item
