from uuid import UUID

from sqlalchemy import select

from apps.orders.models import OrderItem
from apps.orders.schemas.db import OrderItemCreateSchema, OrderItemReadSchema, OrderItemUpdateSchema
from shared.db import DBCrudRepository


class OrderItemRepository(
    DBCrudRepository[OrderItem, OrderItemCreateSchema, OrderItemReadSchema, OrderItemUpdateSchema]
):
    async def list_for_order(self, order_id: UUID) -> list[OrderItemReadSchema]:
        query = select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.created_at.asc())
        async with self.session_manager.get_session() as session:
            rows = (await session.execute(query)).scalars().all()
        return [self.model_validate(row) for row in rows]
