from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from apps.orders.b2b_client import B2BInventoryClient
from apps.orders.errors import B2BUnavailableError, ReserveFailedError
from apps.orders.models import OrderItem
from apps.orders.schemas.db import OrderCreateSchema, OrderItemCreateSchema, OrderItemReadSchema, OrderReadSchema


class FakeOrderRepository:
    """In-memory заместитель OrderRepository.

    Симулирует UNIQUE(idempotency_key) — повторный create_with_items с тем же
    ключом бросает IntegrityError, чтобы use-case мог проверить race-логику.
    """

    def __init__(self):
        self.by_id: dict[UUID, OrderReadSchema] = {}
        self.by_idempotency_key: dict[UUID, UUID] = {}
        self.items_by_order: dict[UUID, list[OrderItem]] = {}
        self.create_calls: list[OrderCreateSchema] = []

    async def get_by_idempotency_key(self, idempotency_key: UUID) -> OrderReadSchema | None:
        order_id = self.by_idempotency_key.get(idempotency_key)
        if order_id is None:
            return None
        return self.by_id.get(order_id)

    async def get_for_user(self, order_id: UUID, user_id: UUID) -> OrderReadSchema | None:
        order = self.by_id.get(order_id)
        if order is None or order.user_id != user_id:
            return None
        return order

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[OrderReadSchema], int]:
        rows = [o for o in self.by_id.values() if o.user_id == user_id]
        if status is not None:
            rows = [o for o in rows if o.status == status]
        rows.sort(key=lambda o: o.created_at, reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total

    async def items_count_map(self, order_ids: list[UUID]) -> dict[UUID, int]:
        return {oid: len(self.items_by_order.get(oid, [])) for oid in order_ids}

    async def update(self, data):
        existing = self.by_id.get(data.id)
        if existing is None:
            return None
        payload = data.model_dump(exclude_unset=True, exclude={'id'})
        merged = existing.model_dump()
        merged.update(payload)
        merged['updated_at'] = datetime.now(UTC)
        updated = OrderReadSchema.model_validate(merged)
        self.by_id[data.id] = updated
        return updated

    async def create_with_items(
        self,
        order_data: OrderCreateSchema,
        item_data_list: list[OrderItemCreateSchema],
    ) -> tuple[OrderReadSchema, list[OrderItem]]:
        if order_data.idempotency_key in self.by_idempotency_key:
            raise IntegrityError('mock unique violation', {}, Exception('uniq'))
        self.create_calls.append(order_data)
        now = datetime.now(UTC)
        order_id = order_data.id or uuid4()
        order = OrderReadSchema(
            id=order_id,
            user_id=order_data.user_id,
            status=order_data.status,
            total_amount=order_data.total_amount,
            idempotency_key=order_data.idempotency_key,
            delivery_address=order_data.delivery_address,
            address_id=order_data.address_id,
            payment_method_id=order_data.payment_method_id,
            created_at=now,
            updated_at=now,
        )
        item_models: list[OrderItem] = []
        for it in item_data_list:
            im = OrderItem(
                id=uuid4(),
                order_id=order_id,
                sku_id=it.sku_id,
                product_id=it.product_id,
                product_title=it.product_title,
                sku_name=it.sku_name,
                quantity=it.quantity,
                unit_price=it.unit_price,
                line_total=it.line_total,
            )
            # mimic alembic server-default timestamps for tests reading from model
            im.created_at = now  # type: ignore[attr-defined]
            im.updated_at = now  # type: ignore[attr-defined]
            item_models.append(im)
        self.by_id[order_id] = order
        self.by_idempotency_key[order_data.idempotency_key] = order_id
        self.items_by_order[order_id] = item_models
        return order, item_models

    def seed_order(self, order: OrderReadSchema, items: list[OrderItem]) -> None:
        self.by_id[order.id] = order
        self.by_idempotency_key[order.idempotency_key] = order.id
        self.items_by_order[order.id] = items


class FakeOrderItemRepository:
    def __init__(self, parent: FakeOrderRepository):
        self.parent = parent

    async def list_for_order(self, order_id: UUID) -> list[OrderItemReadSchema]:
        items = self.parent.items_by_order.get(order_id, [])
        return [
            OrderItemReadSchema(
                id=it.id,
                order_id=it.order_id,
                sku_id=it.sku_id,
                product_id=it.product_id,
                product_title=it.product_title,
                sku_name=it.sku_name,
                quantity=it.quantity,
                unit_price=it.unit_price,
                line_total=it.line_total,
                created_at=getattr(it, 'created_at', datetime.now(UTC)),
                updated_at=getattr(it, 'updated_at', datetime.now(UTC)),
            )
            for it in items
        ]


class FakeB2BInventoryClient(B2BInventoryClient):
    """Заместитель B2BInventoryClient — не вызывает реальный HTTP.

    Поля настройки:
        sku_info: dict[sku_id, dict] — что вернёт get_skus_info().
        reserve_response: dict | None — ответ reserve. None → бросить b2b_503.
        reserve_failed_items: list | None — если задан, бросит ReserveFailedError.
        b2b_503: bool — если True, любой reserve бросит B2BUnavailableError.
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        self.sku_info: dict[UUID, dict[str, Any]] = {}
        self.reserve_response: dict[str, Any] | None = {'reserved': True, 'items': []}
        self.reserve_failed_items: list[dict[str, Any]] | None = None
        self.b2b_503: bool = False
        self.reserve_calls: list[dict[str, Any]] = []
        self.unreserve_calls: list[dict[str, Any]] = []
        self.fulfill_calls: list[dict[str, Any]] = []
        self.unreserve_b2b_503: bool = False
        self.fulfill_b2b_503: bool = False

    async def get_skus_info(self, sku_ids: list[UUID]) -> dict[UUID, dict[str, Any]]:
        return {sid: self.sku_info[sid] for sid in sku_ids if sid in self.sku_info}

    async def reserve(self, idempotency_key: UUID, items: list[dict[str, Any]]) -> dict[str, Any]:
        self.reserve_calls.append({'idempotency_key': idempotency_key, 'items': items})
        if self.b2b_503:
            raise B2BUnavailableError()
        if self.reserve_failed_items is not None:
            raise ReserveFailedError(failed_items=self.reserve_failed_items)
        assert self.reserve_response is not None
        return self.reserve_response

    async def unreserve(self, idempotency_key: UUID, items: list[dict[str, Any]]) -> dict[str, Any]:
        self.unreserve_calls.append({'idempotency_key': idempotency_key, 'items': items})
        if self.unreserve_b2b_503:
            raise B2BUnavailableError()
        return {'ok': True}

    async def fulfill(self, order_id: UUID, items: list[dict[str, Any]]) -> dict[str, Any]:
        self.fulfill_calls.append({'order_id': order_id, 'items': items})
        if self.fulfill_b2b_503:
            raise B2BUnavailableError()
        return {'fulfilled': True}


def make_sku_payload(
    sku_id: UUID | None = None,
    product_id: UUID | None = None,
    product_title: str = 'iPhone 15 Pro Max',
    sku_name: str = '256GB Black',
    price: int = 12_999_000,
) -> tuple[UUID, dict[str, Any]]:
    sid = sku_id or uuid4()
    pid = product_id or uuid4()
    return sid, {
        'id': str(sid),
        'product_id': str(pid),
        'product_title': product_title,
        'sku_name': sku_name,
        'name': sku_name,
        'price': price,
        'available_quantity': 100,
    }
