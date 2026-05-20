"""US-ORD-05: MarkDeliveredUseCase — перевод заказа в DELIVERED + fulfill к B2B.

Бизнес-правила (см. neomarket-canon/flows/b2c-orders-flows.md#b2c-13-fulfill):

- Триггер — явный use-case (см. ADR 0004). Вызывается из Django Admin / оператора;
  внешнего HTTP endpoint в b2c нет (по канону, смена статуса выполняется через
  Admin / management command).
- Допустимый исходный статус — DELIVERING. Любая другая попытка (CREATED, PAID,
  ASSEMBLING, CANCELLED, и т.п.) считается недопустимым переходом и поднимает
  DeliverNotAllowedError 409.
- Если заказ уже DELIVERED — идемпотентный no-op: возвращаем текущий снимок,
  не дублируем событие в outbox.
- Если переход допустим:
  1. INSERT outbox(event_type=FULFILL_ORDER, target=b2b) c payload
     {order_id, items: [{sku_id, quantity}]}.
  2. Order.status -> DELIVERED.
- Outbox-воркер (shared.outbox.OutboxWorker) самостоятельно вызовет
  POST /api/v1/inventory/fulfill в B2B; в случае 5xx/timeout планирует ретрай
  через mark_retry с экспоненциальным backoff. Это означает, что fulfill
  гарантированно происходит асинхронно (см. ADR).

ADR: см. b2c/docs/adr/0004-fulfill-via-outbox.md.
"""

from uuid import UUID, uuid4

from apps.orders.enums import OrderStatus
from apps.orders.errors import DeliverNotAllowedError, OrderNotFoundError
from apps.orders.repositories import OrderItemRepository, OrderRepository
from apps.orders.schemas.db import OrderUpdateSchema
from apps.orders.schemas.response import OrderItemResponseSchema, OrderResponseSchema
from apps.outbox.enums import OutboxEventType
from apps.outbox.repositories import B2COutboxRepository
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName


class MarkDeliveredUseCase:
    """Перевод заказа в DELIVERED + enqueue FULFILL_ORDER в outbox.

    Параметр current_user отсутствует намеренно: use-case вызывается из
    административных каналов (Django Admin, оператор-скрипт), а не от лица
    покупателя. Авторизация (admin-only) — ответственность вызывающего слоя.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        order_item_repository: OrderItemRepository,
        outbox_repository: B2COutboxRepository,
    ):
        self.order_repository = order_repository
        self.order_item_repository = order_item_repository
        self.outbox_repository = outbox_repository

    async def __call__(self, order_id: UUID) -> OrderResponseSchema:
        order = await self.order_repository.get_or_none(order_id)
        if order is None:
            raise OrderNotFoundError()

        items = await self.order_item_repository.list_for_order(order.id)

        # Идемпотентность: если уже DELIVERED — возвращаем текущее состояние,
        # outbox не трогаем (FULFILL уже либо отправлен, либо запланирован).
        if order.status == OrderStatus.DELIVERED.value:
            return self._build_response(order, items)

        # Переход допустим только из DELIVERING.
        if order.status != OrderStatus.DELIVERING.value:
            raise DeliverNotAllowedError(current_status=order.status)

        fulfill_payload_items = [{'sku_id': str(it.sku_id), 'quantity': it.quantity} for it in items]

        await self.outbox_repository.enqueue_in_new_transaction(
            OutboxEnqueueSchema(
                idempotency_key=uuid4(),
                event_type=OutboxEventType.FULFILL_ORDER.value,
                target_service=ServiceName.B2B,
                payload={
                    'order_id': str(order.id),
                    'items': fulfill_payload_items,
                },
            )
        )

        updated = await self.order_repository.update(OrderUpdateSchema(id=order.id, status=OrderStatus.DELIVERED.value))
        assert updated is not None, 'Order disappeared between fetch and update'

        return self._build_response(updated, items)

    @staticmethod
    def _build_response(order, items) -> OrderResponseSchema:  # type: ignore[no-untyped-def]
        return OrderResponseSchema(
            id=order.id,
            status=order.status,
            items=[
                OrderItemResponseSchema(
                    id=it.id,
                    sku_id=it.sku_id,
                    product_id=it.product_id,
                    product_title=it.product_title,
                    sku_name=it.sku_name,
                    quantity=it.quantity,
                    unit_price=it.unit_price,
                    line_total=it.line_total,
                )
                for it in items
            ],
            total_amount=order.total_amount,
            delivery_address=order.delivery_address,
            address_id=order.address_id,
            payment_method_id=order.payment_method_id,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )
