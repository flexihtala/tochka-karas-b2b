"""US-ORD-03: POST /api/v1/orders/{order_id}/cancel — отмена заказа (cart-based main).

Бизнес-правила (см. neomarket-canon/flows/b2c-orders-flows.md#b2c-11-cancel-order +
TASK US-ORD-03; правила TASK имеют приоритет над прозой spec, где расходятся):

- Auth: BUYER. user_id берётся ТОЛЬКО из JWT (IDOR-защита).
- Ownership: чужой/несуществующий заказ → 404 ORDER_NOT_FOUND (не 403; маскируем
  существование чужих заказов, ревью Guardian).
- Отменять можно ТОЛЬКО из CREATED/PAID. Любой другой статус (включая ASSEMBLING)
  → 409 CANCEL_NOT_ALLOWED с текущим статусом. (Spec-описание упоминает ASSEMBLING,
  но TASK + DoD-тест cancel_assembling_order_returns_409 требуют ASSEMBLING → 409.)
- B2B unreserve {order_id, items} (идемпотентность B2B — по order_id).
- На успех → status = CANCELLED.
- На сбой (B2B недоступен / timeout / 5xx) → status = CANCEL_PENDING; ошибка
  логируется, заказ ОСТАЁТСЯ в CANCEL_PENDING. Это ПЕРВАЯ итерация — scaffold для
  асинхронного ретрая (без Celery/outbox/cron); выбранный механизм ретрая —
  follow-up (см. ADR в PR). Ответ — 200 с CANCEL_PENDING.
- `reason` (optional, <=500) сохраняется в orders.cancel_reason → попадает в ответ
  и в последующий GET заказа.
- Ответ — общий ассемблер assemble_order_response (та же форма, что у checkout).
"""

import logging
from uuid import UUID

from apps.addresses.repositories import AddressRepository
from apps.orders.b2b_client import B2BInventoryClient
from apps.orders.enums import OrderStatus
from apps.orders.errors import B2BUnavailableError, CancelNotAllowedError, OrderNotFoundError
from apps.orders.repositories import OrderItemRepository, OrderRepository
from apps.orders.schemas.db import OrderUpdateSchema
from apps.orders.schemas.response import OrderResponseSchema
from apps.orders.use_cases.response_assembler import assemble_order_response
from apps.payment_methods.repositories import PaymentMethodRepository
from shared.auth_lib import AuthenticatedUserSchema

logger = logging.getLogger(__name__)

CANCELABLE = frozenset({OrderStatus.CREATED.value, OrderStatus.PAID.value})


class CancelOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        order_item_repository: OrderItemRepository,
        b2b_client: B2BInventoryClient,
        address_repository: AddressRepository,
        payment_method_repository: PaymentMethodRepository,
    ):
        self.order_repository = order_repository
        self.order_item_repository = order_item_repository
        self.b2b_client = b2b_client
        self.address_repository = address_repository
        self.payment_method_repository = payment_method_repository

    async def __call__(
        self,
        order_id: UUID,
        current_user: AuthenticatedUserSchema,
        *,
        reason: str | None = None,
    ) -> OrderResponseSchema:
        # 1. Ownership (IDOR): фильтрация по user_id внутри запроса; чужой → None → 404.
        order = await self.order_repository.get_for_user(order_id, current_user.id)
        if order is None:
            raise OrderNotFoundError()

        # 2. Статус должен допускать отмену (только CREATED/PAID).
        if order.status not in CANCELABLE:
            raise CancelNotAllowedError(current_status=order.status)

        # 3. Снять резерв в B2B (идемпотентно по order_id).
        items = await self.order_item_repository.list_for_order(order.id)
        unreserve_items = [{'sku_id': str(it.sku_id), 'quantity': it.quantity} for it in items]
        try:
            await self.b2b_client.unreserve(order_id=order.id, items=unreserve_items)
            new_status = OrderStatus.CANCELLED.value
        except B2BUnavailableError:
            # Scaffold для async-ретрая: логируем и оставляем CANCEL_PENDING (без воркера).
            logger.warning(
                'unreserve failed for order %s; leaving CANCEL_PENDING (scaffold, no retry yet)',
                order.id,
            )
            new_status = OrderStatus.CANCEL_PENDING.value

        # 4. Зафиксировать новый статус + причину отмены (reason переживёт в ответе/GET).
        updated = await self.order_repository.update(
            OrderUpdateSchema(id=order.id, status=new_status, cancel_reason=reason)
        )
        assert updated is not None, 'Order disappeared between fetch and update'

        return await assemble_order_response(
            updated,
            order_item_repository=self.order_item_repository,
            address_repository=self.address_repository,
            payment_method_repository=self.payment_method_repository,
        )
