"""US-ORD-02: GET /api/v1/orders/{id} — детали заказа.

IDOR-prevention:
- user_id берётся из JWT.
- Запрос в репозитории фильтрует по (id, user_id) — чужой заказ невидим.
- Если не нашли — 404 ORDER_NOT_FOUND (не 403), чтобы не раскрывать существование
  чужих ресурсов (см. канон, §"Authorization (IDOR prevention)").

ADR — см. b2c/docs/adr/0002-list-and-detail-idor.md.
"""

from uuid import UUID

from apps.orders.errors import OrderNotFoundError
from apps.orders.repositories import OrderItemRepository, OrderRepository
from apps.orders.schemas.response import OrderItemResponseSchema, OrderResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class GetOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        order_item_repository: OrderItemRepository,
    ):
        self.order_repository = order_repository
        self.order_item_repository = order_item_repository

    async def __call__(self, order_id: UUID, current_user: AuthenticatedUserSchema) -> OrderResponseSchema:
        order = await self.order_repository.get_for_user(order_id, current_user.id)
        if order is None:
            raise OrderNotFoundError()

        items = await self.order_item_repository.list_for_order(order.id)

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
