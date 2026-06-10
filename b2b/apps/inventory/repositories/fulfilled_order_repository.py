"""FulfilledOrderRepository — журнал списаний резерва при доставке.

Используется для идемпотентности POST /api/v1/inventory/fulfill по `order_id`.
Перед списанием use-case узнаёт, какие пары `(order_id, sku_id)` уже записаны,
и пропускает их (см. ADR-0002 для обоснования выбора отдельной таблицы вместо
поля `last_fulfilled_order` на SKU).

Use-case передаёт `session: AsyncSession` извне — INSERT в `fulfilled_orders`
и UPDATE `skus.reserved_quantity` происходят в одной транзакции. При гонке
двух fulfill'ов с одним и тем же `order_id` UNIQUE(order_id, sku_id) гарантирует,
что только одна транзакция запишет каждую пару, остальные получат IntegrityError
и откатятся (read-modify-write на SKU остаётся атомарным благодаря
SELECT ... FOR UPDATE в InventoryRepository).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.inventory.models import FulfilledOrder


class FulfilledOrderRepository:
    async def get_fulfilled_sku_ids(
        self,
        session: AsyncSession,
        order_id: UUID,
    ) -> set[UUID]:
        """Список sku_id, для которых уже записан fulfill по этому order_id.

        Use-case использует этот set, чтобы пропустить items, которые уже
        были обработаны при предыдущем (успешном) вызове fulfill — это и есть
        идемпотентность по `order_id`.
        """
        stmt = select(FulfilledOrder.sku_id).where(FulfilledOrder.order_id == order_id)
        result = await session.execute(stmt)
        return set(result.scalars().all())

    async def record(
        self,
        session: AsyncSession,
        order_id: UUID,
        sku_id: UUID,
        quantity: int,
    ) -> None:
        """Зафиксировать факт fulfill'а для пары (order_id, sku_id).

        UNIQUE(order_id, sku_id) — при гонке только одна транзакция пройдёт.
        Вызывающий код должен flush'ить в той же транзакции, что и UPDATE SKU,
        чтобы дать БД защитить нас от двойного списания.
        """
        record = FulfilledOrder(order_id=order_id, sku_id=sku_id, quantity=quantity)
        session.add(record)
