from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from apps.addresses.schemas.db import AddressReadSchema
from apps.cart.schemas.db import CartItemReadSchema, CartReadSchema
from apps.orders.b2b_client import B2BInventoryClient
from apps.orders.errors import B2BUnavailableError, ReserveFailedError
from apps.orders.models import OrderItem
from apps.orders.schemas.db import (
    OrderCreateSchema,
    OrderItemCreateSchema,
    OrderItemReadSchema,
    OrderReadSchema,
    OrderUpdateSchema,
)
from apps.payment_methods.schemas.db import PaymentMethodReadSchema


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
            comment=order_data.comment,
            cancel_reason=order_data.cancel_reason,
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
            im.created_at = now  # type: ignore[attr-defined]
            im.updated_at = now  # type: ignore[attr-defined]
            item_models.append(im)
        self.by_id[order_id] = order
        self.by_idempotency_key[order_data.idempotency_key] = order_id
        self.items_by_order[order_id] = item_models
        return order, item_models

    async def update(self, data: OrderUpdateSchema) -> OrderReadSchema | None:
        """Мирроринг DBCrudRepository.update: применяет только заданные (set) поля."""
        order = self.by_id.get(data.id)
        if order is None:
            return None
        values = data.model_dump(exclude_unset=True, exclude={'id'})
        updated = order.model_copy(update={**values, 'updated_at': datetime.now(UTC)})
        self.by_id[data.id] = updated
        return updated

    def seed_order(self, order: OrderReadSchema, items: list[OrderItem]) -> None:
        self.by_id[order.id] = order
        self.by_idempotency_key[order.idempotency_key] = order.id
        self.items_by_order[order.id] = items

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[OrderReadSchema], int]:
        """Мирроринг OrderRepository.list_for_user: created_at DESC, ?status, (items, total)."""
        own = [o for o in self.by_id.values() if o.user_id == user_id]
        if status is not None:
            own = [o for o in own if o.status == status]
        own.sort(key=lambda o: o.created_at, reverse=True)
        return own[offset : offset + limit], len(own)

    async def items_count_map(self, order_ids: list[UUID]) -> dict[UUID, int]:
        return {oid: len(self.items_by_order.get(oid, [])) for oid in order_ids}


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


class FakeCartRepository:
    """Минимальный заместитель CartRepository (только get_by_user для checkout)."""

    def __init__(self):
        self.by_user: dict[UUID, CartReadSchema] = {}

    async def get_by_user(self, user_id: UUID) -> CartReadSchema | None:
        return self.by_user.get(user_id)

    def seed(self, cart: CartReadSchema) -> None:
        assert cart.user_id is not None
        self.by_user[cart.user_id] = cart


class FakeCartItemRepository:
    """Минимальный заместитель CartItemRepository (только list_by_cart)."""

    def __init__(self):
        self.by_cart: dict[UUID, list[CartItemReadSchema]] = {}

    async def list_by_cart(self, cart_id: UUID) -> list[CartItemReadSchema]:
        return list(self.by_cart.get(cart_id, []))

    def seed(self, cart_id: UUID, items: list[CartItemReadSchema]) -> None:
        self.by_cart[cart_id] = items


class FakeAddressRepository:
    def __init__(self):
        self.by_id: dict[UUID, AddressReadSchema] = {}

    async def get_or_none(self, id_: UUID) -> AddressReadSchema | None:
        return self.by_id.get(id_)

    def seed(self, address: AddressReadSchema) -> None:
        self.by_id[address.id] = address


class FakePaymentMethodRepository:
    def __init__(self):
        self.by_id: dict[UUID, PaymentMethodReadSchema] = {}

    async def get_or_none(self, id_: UUID) -> PaymentMethodReadSchema | None:
        return self.by_id.get(id_)

    def seed(self, payment_method: PaymentMethodReadSchema) -> None:
        self.by_id[payment_method.id] = payment_method


class FakeB2BInventoryClient(B2BInventoryClient):
    """Заместитель B2BInventoryClient — НЕ вызывает реальный HTTP.

    Возвращает реально-B2B-шейпнутые payload'ы. Поля настройки:
        sku_index: {sku_id: {product_id, product_title, sku_name, price, active_quantity}}
            — что вернёт get_products_batch (как реальный клиент после flatten).
        reserve_response: dict — ответ reserve при успехе.
        reserve_failed_items: list | None — если задан, reserve бросит ReserveFailedError.
        b2b_503: bool — reserve бросит B2BUnavailableError.
        batch_503: bool — get_products_batch бросит B2BUnavailableError.
        unreserve_503: bool — unreserve бросит B2BUnavailableError (B2B недоступен).
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        self.sku_index: dict[UUID, dict[str, Any]] = {}
        self.reserve_response: dict[str, Any] = {'status': 'RESERVED', 'reserved_at': '2026-06-05T00:00:00Z'}
        self.reserve_failed_items: list[dict[str, Any]] | None = None
        self.b2b_503: bool = False
        self.batch_503: bool = False
        self.unreserve_503: bool = False
        self.reserve_calls: list[dict[str, Any]] = []
        self.batch_calls: list[list[UUID]] = []
        self.unreserve_calls: list[dict[str, Any]] = []

    async def get_products_batch(self, product_ids: list[UUID]) -> dict[UUID, dict[str, Any]]:
        self.batch_calls.append(list(product_ids))
        if self.batch_503:
            raise B2BUnavailableError()
        return {sid: raw for sid, raw in self.sku_index.items()}

    async def reserve(
        self,
        *,
        idempotency_key: UUID,
        order_id: UUID,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.reserve_calls.append({'idempotency_key': idempotency_key, 'order_id': order_id, 'items': items})
        if self.b2b_503:
            raise B2BUnavailableError()
        if self.reserve_failed_items is not None:
            raise ReserveFailedError(failed_items=self.reserve_failed_items)
        return {'order_id': str(order_id), **self.reserve_response}

    async def unreserve(
        self,
        *,
        order_id: UUID,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.unreserve_calls.append({'order_id': order_id, 'items': items})
        if self.unreserve_503:
            raise B2BUnavailableError()
        return {'order_id': str(order_id), 'unreserved': True, 'items': items}


def make_sku_entry(
    *,
    sku_id: UUID | None = None,
    product_id: UUID | None = None,
    product_title: str = 'iPhone 15 Pro Max',
    sku_name: str = '256GB Black',
    price: int = 12_999_000,
    active_quantity: int = 100,
) -> tuple[UUID, dict[str, Any]]:
    """Запись индекса, как её вернул бы get_products_batch после flatten."""
    sid = sku_id or uuid4()
    pid = product_id or uuid4()
    return sid, {
        'product_id': pid,
        'product_title': product_title,
        'sku_name': sku_name,
        'price': price,
        'active_quantity': active_quantity,
    }


def make_cart_item(
    *,
    cart_id: UUID,
    sku_id: UUID,
    product_id: UUID,
    quantity: int = 1,
) -> CartItemReadSchema:
    now = datetime.now(UTC)
    return CartItemReadSchema(
        id=uuid4(),
        cart_id=cart_id,
        sku_id=sku_id,
        product_id=product_id,
        quantity=quantity,
        created_at=now,
        updated_at=now,
    )


def make_cart(*, user_id: UUID, cart_id: UUID | None = None) -> CartReadSchema:
    now = datetime.now(UTC)
    return CartReadSchema(
        id=cart_id or uuid4(),
        user_id=user_id,
        session_id=None,
        created_at=now,
        updated_at=now,
    )


def make_address(*, buyer_id: UUID, address_id: UUID | None = None) -> AddressReadSchema:
    now = datetime.now(UTC)
    return AddressReadSchema(
        id=address_id or uuid4(),
        buyer_id=buyer_id,
        country='RU',
        city='Екатеринбург',
        street='ул. Мира 19',
        postal_code='620000',
        comment=None,
        is_default=True,
        created_at=now,
        updated_at=now,
    )


def make_order(
    *,
    user_id: UUID,
    status: str,
    order_id: UUID | None = None,
    total_amount: int = 20_000,
    address_id: UUID | None = None,
    payment_method_id: UUID | None = None,
    comment: str | None = None,
    cancel_reason: str | None = None,
) -> OrderReadSchema:
    """Персистентный заказ для cancel-тестов (как вернул бы OrderRepository)."""
    now = datetime.now(UTC)
    return OrderReadSchema(
        id=order_id or uuid4(),
        user_id=user_id,
        status=status,
        total_amount=total_amount,
        idempotency_key=uuid4(),
        delivery_address=None,
        address_id=address_id,
        payment_method_id=payment_method_id,
        comment=comment,
        cancel_reason=cancel_reason,
        created_at=now,
        updated_at=now,
    )


def make_order_item(
    *,
    order_id: UUID,
    sku_id: UUID | None = None,
    product_id: UUID | None = None,
    product_title: str = 'iPhone 15 Pro Max',
    sku_name: str = '256GB Black',
    quantity: int = 1,
    unit_price: int = 20_000,
) -> OrderItem:
    """OrderItem-модель (снапшот позиции) для seed_order в cancel-тестах."""
    now = datetime.now(UTC)
    item = OrderItem(
        id=uuid4(),
        order_id=order_id,
        sku_id=sku_id or uuid4(),
        product_id=product_id or uuid4(),
        product_title=product_title,
        sku_name=sku_name,
        quantity=quantity,
        unit_price=unit_price,
        line_total=unit_price * quantity,
    )
    item.created_at = now  # type: ignore[attr-defined]
    item.updated_at = now  # type: ignore[attr-defined]
    return item


def make_payment_method(*, buyer_id: UUID, payment_method_id: UUID | None = None) -> PaymentMethodReadSchema:
    now = datetime.now(UTC)
    return PaymentMethodReadSchema(
        id=payment_method_id or uuid4(),
        buyer_id=buyer_id,
        brand='visa',
        last4='4242',
        exp_year=2030,
        exp_month=12,
        is_default=True,
        created_at=now,
        updated_at=now,
    )
