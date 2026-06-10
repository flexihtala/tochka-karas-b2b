from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from apps.cart.schemas.db import (
    CartCreateSchema,
    CartItemCreateSchema,
    CartItemReadSchema,
    CartItemUpdateSchema,
    CartReadSchema,
    CartUpdateSchema,
)
from shared.http_clients import ServiceClientError


def make_sku(
    *,
    sku_id: UUID,
    product_id: UUID,
    name: str = 'M',
    price: int = 1000,
    active_quantity: int = 10,
    article: str | None = None,
    images: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Реально-витринная форма SKUPublic (без cost_price/reserved_quantity)."""
    return {
        'id': str(sku_id),
        'product_id': str(product_id),
        'name': name,
        'price': price,
        'discount': 0,
        'stock_quantity': active_quantity,
        'active_quantity': active_quantity,
        'article': article,
        'images': images or [],
        'characteristics': [],
    }


def make_product(
    *,
    product_id: UUID,
    title: str = 'Product',
    skus: list[dict[str, Any]] | None = None,
    images: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Реально-витринная форма ProductPublicResponse с вложенными skus."""
    return {
        'id': str(product_id),
        'seller_id': str(uuid4()),
        'category_id': str(uuid4()),
        'title': title,
        'slug': title.lower().replace(' ', '-'),
        'description': '',
        'status': 'MODERATED',
        'images': images or [],
        'characteristics': [],
        'skus': skus or [],
        'created_at': '2026-06-05T00:00:00Z',
        'updated_at': '2026-06-05T00:00:00Z',
    }


class FakeB2BClient:
    """Тонкий фейк ServiceClient: НЕ мокает бизнес-логику, только HTTP-границу.

    - get('/api/v1/public/skus/{id}') → single SKU dict, либо 404 ServiceClientError.
    - post('/api/v1/public/products/batch', json={'product_ids': [...]}) → JSON-массив
      видимых товаров (только запрошенные id, что присутствуют в self.products).
    """

    def __init__(
        self,
        products: list[dict[str, Any]] | None = None,
        skus: dict[UUID, dict[str, Any]] | None = None,
    ):
        self.products_by_id: dict[str, dict[str, Any]] = {p['id']: p for p in (products or [])}
        self.skus_by_id: dict[str, dict[str, Any]] = {str(k): v for k, v in (skus or {}).items()}
        self.get_calls: list[str] = []
        self.post_calls: list[tuple[str, dict[str, Any] | None]] = []

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.get_calls.append(path)
        sku_id = path.rsplit('/', 1)[-1]
        sku = self.skus_by_id.get(sku_id)
        if sku is None:
            raise ServiceClientError(status_code=404, message='not found', payload={'code': 'NOT_FOUND'})
        return sku

    async def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> list[dict[str, Any]]:
        self.post_calls.append((path, json))
        requested = (json or {}).get('product_ids', [])
        return [self.products_by_id[pid] for pid in requested if pid in self.products_by_id]


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
        self.deleted_by_cart: list[UUID] = []

    async def create(self, data: CartItemCreateSchema) -> CartItemReadSchema:
        self.created.append(data)
        item_id = data.id or uuid4()
        now = datetime.now(UTC)
        item = CartItemReadSchema(
            id=item_id,
            cart_id=data.cart_id,
            sku_id=data.sku_id,
            product_id=data.product_id,
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

    async def delete_by_cart(self, cart_id: UUID) -> None:
        self.deleted_by_cart.append(cart_id)
        targets = [iid for iid, i in self.by_id.items() if i.cart_id == cart_id]
        for iid in targets:
            self.by_id.pop(iid, None)

    def add(self, item: CartItemReadSchema) -> None:
        self.by_id[item.id] = item
