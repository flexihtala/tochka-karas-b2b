"""US-ORD-02: GET /api/v1/orders — постраничный список заказов покупателя.

Бизнес-правила (см. neomarket-canon/flows/b2c-orders-flows.md#b2c-10-view-orders):
- user_id всегда берётся из JWT (защита от подделки).
- Optional `?status=` фильтр.
- В списке items НЕ разворачиваются — только items_count (см. канон).
"""

from apps.orders.repositories import OrderRepository
from apps.orders.schemas.response import OrderListItemResponseSchema, OrderListResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class ListOrdersUseCase:
    def __init__(self, order_repository: OrderRepository):
        self.order_repository = order_repository

    async def __call__(
        self,
        current_user: AuthenticatedUserSchema,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> OrderListResponseSchema:
        orders, total_count = await self.order_repository.list_for_user(
            current_user.id,
            status=status,
            limit=limit,
            offset=offset,
        )
        items_count_map = await self.order_repository.items_count_map([o.id for o in orders])

        return OrderListResponseSchema(
            items=[
                OrderListItemResponseSchema(
                    id=order.id,
                    status=order.status,
                    total_amount=order.total_amount,
                    items_count=items_count_map.get(order.id, 0),
                    created_at=order.created_at,
                    updated_at=order.updated_at,
                )
                for order in orders
            ],
            total_count=total_count,
            limit=limit,
            offset=offset,
        )
