"""US-ORD-03: POST /api/v1/orders/{id}/cancel — отмена заказа.

Бизнес-правила (см. neomarket-canon/flows/b2c-orders-flows.md#b2c-11-cancel-order):

- Auth: BUYER. user_id из JWT.
- Отменять можно только из CREATED/PAID/ASSEMBLING (per spec b2c openapi.yaml).
  Иначе 409 CANCEL_NOT_ALLOWED с полем `current_status`.
- Чужой заказ → 404 ORDER_NOT_FOUND (IDOR).
- Вызов B2B unreserve через ServiceClient (X-Service-Key b2c_to_b2b).
- На успех → Order.status = CANCELLED.
- На сбой (5xx/timeout) → Order.status = CANCEL_PENDING + outbox-задача
  UNRESERVE_ORDER (target=b2b) для асинхронного ретрая. Воркер позже
  переведёт CANCEL_PENDING → CANCELLED.
- Pydantic-схема ответа OrderResponseSchema — даже при CANCEL_PENDING.
- Optional `reason` (str <=500) принимается из body per spec; пробрасывается
  в outbox payload для аудита (БД-колонки cancel_reason пока нет).

ADR: см. b2c/docs/adr/0003-cancel-retry-outbox.md.
"""

from uuid import UUID, uuid4

from apps.orders.b2b_client import B2BInventoryClient
from apps.orders.enums import OrderStatus
from apps.orders.errors import B2BUnavailableError, CancelNotAllowedError, OrderNotFoundError
from apps.orders.repositories import OrderItemRepository, OrderRepository
from apps.orders.schemas.db import OrderUpdateSchema
from apps.orders.schemas.response import OrderItemResponseSchema, OrderResponseSchema
from apps.outbox.enums import OutboxEventType
from apps.outbox.repositories import B2COutboxRepository
from shared.auth_lib import AuthenticatedUserSchema
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName

CANCELABLE_STATUSES = frozenset(
    {
        OrderStatus.CREATED.value,
        OrderStatus.PAID.value,
        OrderStatus.ASSEMBLING.value,
    }
)


class CancelOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        order_item_repository: OrderItemRepository,
        b2b_client: B2BInventoryClient,
        outbox_repository: B2COutboxRepository,
    ):
        self.order_repository = order_repository
        self.order_item_repository = order_item_repository
        self.b2b_client = b2b_client
        self.outbox_repository = outbox_repository

    async def __call__(
        self,
        order_id: UUID,
        current_user: AuthenticatedUserSchema,
        *,
        reason: str | None = None,
    ) -> OrderResponseSchema:
        order = await self.order_repository.get_for_user(order_id, current_user.id)
        if order is None:
            raise OrderNotFoundError()

        if order.status not in CANCELABLE_STATUSES:
            raise CancelNotAllowedError(current_status=order.status)

        items = await self.order_item_repository.list_for_order(order.id)
        unreserve_payload_items = [{'sku_id': str(it.sku_id), 'quantity': it.quantity} for it in items]

        try:
            await self.b2b_client.unreserve(
                idempotency_key=order.id,  # order_id-based idempotency на стороне B2B
                items=unreserve_payload_items,
            )
            new_status = OrderStatus.CANCELLED.value
        except B2BUnavailableError:
            # Переходим в CANCEL_PENDING + enqueue в outbox.
            new_status = OrderStatus.CANCEL_PENDING.value
            outbox_payload: dict[str, object] = {
                'order_id': str(order.id),
                'items': unreserve_payload_items,
            }
            if reason is not None:
                outbox_payload['reason'] = reason
            await self.outbox_repository.enqueue_in_new_transaction(
                OutboxEnqueueSchema(
                    idempotency_key=uuid4(),
                    event_type=OutboxEventType.UNRESERVE_ORDER.value,
                    target_service=ServiceName.B2B,
                    payload=outbox_payload,
                )
            )

        updated = await self.order_repository.update(OrderUpdateSchema(id=order.id, status=new_status))
        assert updated is not None, 'Order disappeared between fetch and update'

        return OrderResponseSchema(
            id=updated.id,
            user_id=updated.user_id,
            status=updated.status,
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
            total_amount=updated.total_amount,
            delivery_address=updated.delivery_address,
            address_id=updated.address_id,
            payment_method_id=updated.payment_method_id,
            cancel_reason=reason,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )
