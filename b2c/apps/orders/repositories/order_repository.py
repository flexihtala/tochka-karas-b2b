from uuid import UUID

from sqlalchemy import func, select

from apps.orders.models import Order, OrderItem
from apps.orders.schemas.db import OrderCreateSchema, OrderItemCreateSchema, OrderReadSchema, OrderUpdateSchema
from shared.db import DBCrudRepository


class OrderRepository(DBCrudRepository[Order, OrderCreateSchema, OrderReadSchema, OrderUpdateSchema]):
    async def get_by_idempotency_key(self, idempotency_key: UUID) -> OrderReadSchema | None:
        query = select(Order).where(Order.idempotency_key == idempotency_key)
        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()
        return self.model_validate(model) if model else None

    async def get_for_user(self, order_id: UUID, user_id: UUID) -> OrderReadSchema | None:
        """Возвращает заказ ТОЛЬКО если он принадлежит user_id.

        IDOR-защита: фильтрация по user_id ВНУТРИ запроса, а не отдельной проверкой.
        Канон диктует возврат 404 для чужого заказа, поэтому вызывающему достаточно
        проверять на None.
        """
        query = select(Order).where(Order.id == order_id, Order.user_id == user_id)
        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()
        return self.model_validate(model) if model else None

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[OrderReadSchema], int]:
        """Список заказов пользователя с пагинацией. Возвращает (items, total_count)."""
        base = select(Order).where(Order.user_id == user_id)
        count_base = select(func.count(Order.id)).where(Order.user_id == user_id)
        if status is not None:
            base = base.where(Order.status == status)
            count_base = count_base.where(Order.status == status)

        query = base.order_by(Order.created_at.desc()).limit(limit).offset(offset)

        async with self.session_manager.get_session() as session:
            rows = (await session.execute(query)).scalars().all()
            total = (await session.execute(count_base)).scalar_one()

        return [self.model_validate(row) for row in rows], int(total)

    async def items_count_map(self, order_ids: list[UUID]) -> dict[UUID, int]:
        """Возвращает {order_id: items_count}. Используется в list-views,
        чтобы не делать N+1.
        """
        if not order_ids:
            return {}
        query = (
            select(OrderItem.order_id, func.count(OrderItem.id))
            .where(OrderItem.order_id.in_(order_ids))
            .group_by(OrderItem.order_id)
        )
        async with self.session_manager.get_session() as session:
            rows = (await session.execute(query)).all()
        return {row[0]: int(row[1]) for row in rows}

    async def create_with_items(
        self,
        order_data: OrderCreateSchema,
        item_data_list: list[OrderItemCreateSchema],
    ) -> tuple[OrderReadSchema, list[OrderItem]]:
        """Атомарная вставка Order + OrderItem-ов в одной транзакции.

        Возвращает (order_schema, list[OrderItem]) — сами OrderItem-модели,
        чтобы вызывающему не пришлось делать второй SELECT для сборки ответа.

        IntegrityError по UNIQUE(idempotency_key) пробрасывается выше — use-case
        должен поймать и обработать как "повтор".
        """
        async with self.session_manager.get_session() as session:
            order_payload = order_data.model_dump()
            if order_payload.get('id') is None:
                order_payload.pop('id', None)
            order_model = Order(**{k: v for k, v in order_payload.items() if v is not None or k != 'id'})
            session.add(order_model)
            await session.flush()  # получить order.id

            item_models: list[OrderItem] = []
            for item in item_data_list:
                payload = item.model_dump()
                payload.pop('id', None)
                payload['order_id'] = order_model.id
                item_models.append(OrderItem(**payload))
            session.add_all(item_models)
            await session.flush()

        return self.model_validate(order_model), item_models
